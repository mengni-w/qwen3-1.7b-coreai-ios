from __future__ import annotations

import hashlib
import json
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluator.contract import (  # noqa: E402
    CONTRACT,
    SYSTEM_MESSAGE,
    ContractError,
    canonical_json_bytes,
    canonical_token_bytes,
    make_source_model_lock,
    sha256_bytes,
    token_ids_sha256,
    validate_prompt_manifest,
    validate_source_model_lock,
    validate_tokenizer,
)
from evaluator.cli import _claim_run_id  # noqa: E402
from evaluator.runtime import (  # noqa: E402
    _append_source_model_revalidation,
    _construct_causal_mask,
    _failed_comparison,
    _teacher_forced_slice_bounds,
    _teacher_forced_input_fields,
    _write_preflight_failure_evidence,
    validate_environment,
)


class FakeTokenizer:
    chat_template = "{% if enable_thinking is false %}disabled{% endif %}"

    def _text(self, messages, enable_thinking):
        base = "|".join(
            f"{message['role']}:{message['content']}" for message in messages
        )
        if enable_thinking:
            return base + "<|im_start|>assistant\n"
        return base + "<|im_start|>assistant\n<think>\n\n</think>\n\n"

    @staticmethod
    def _tokens(text):
        return [ord(character) for character in text]

    def apply_chat_template(
        self,
        messages,
        *,
        tokenize,
        add_generation_prompt,
        enable_thinking,
    ):
        if not add_generation_prompt:
            raise AssertionError("test tokenizer requires a generation prompt")
        text = self._text(messages, enable_thinking)
        return self._tokens(text) if tokenize else text

    def __call__(self, text, *, add_special_tokens):
        if add_special_tokens:
            raise AssertionError("test tokenizer forbids extra special tokens")
        return {"input_ids": self._tokens(text)}


class NoThinkingIgnoredTokenizer(FakeTokenizer):
    def _text(self, messages, enable_thinking):
        del enable_thinking
        base = "|".join(
            f"{message['role']}:{message['content']}" for message in messages
        )
        return base + "<|im_start|>assistant\n"


class ContractTests(unittest.TestCase):
    def test_environment_rejects_python_outside_pinned_coreai_dot_venv(self):
        with tempfile.TemporaryDirectory() as temporary:
            coreai = Path(temporary) / "coreai"
            coreai.mkdir()
            with (
                patch("evaluator.runtime.platform.system", return_value="Darwin"),
                patch("evaluator.runtime.platform.machine", return_value="arm64"),
                patch("evaluator.runtime.sys.version_info", (3, 12, 0)),
                patch("evaluator.runtime.sys.prefix", str(Path(temporary) / "other")),
                patch(
                    "evaluator.runtime.sys.executable",
                    str(Path(temporary) / "other/bin/python"),
                ),
            ):
                with self.assertRaisesRegex(
                    ContractError, "pinned coreai-models checkout's .venv"
                ):
                    validate_environment(
                        coreai_repo=coreai,
                        model_dir=Path(temporary) / "model",
                        source_lock=Path(temporary) / "source-lock.json",
                    )

    def test_environment_resolves_executable_path_alias_before_dot_venv_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            physical_coreai = root / "physical" / "coreai"
            physical_venv = physical_coreai / ".venv"
            physical_python = physical_venv / "bin/python"
            physical_python.parent.mkdir(parents=True)
            base_python = root / "managed-python/bin/python3.12"
            base_python.parent.mkdir(parents=True)
            base_python.touch()
            physical_python.symlink_to(base_python)
            alias = root / "alias"
            alias.symlink_to(root / "physical", target_is_directory=True)
            aliased_coreai = alias / "coreai"
            aliased_python = aliased_coreai / ".venv/bin/python"
            with (
                patch("evaluator.runtime.platform.system", return_value="Darwin"),
                patch("evaluator.runtime.platform.machine", return_value="arm64"),
                patch("evaluator.runtime.sys.version_info", (3, 12, 0)),
                patch("evaluator.runtime.sys.prefix", str(physical_venv)),
                patch("evaluator.runtime.sys.executable", str(aliased_python)),
                patch(
                    "evaluator.runtime.NUMERIC_THREAD_ENVIRONMENT",
                    {"FROZEN_TEST_THREADS": None},
                ),
            ):
                with self.assertRaisesRegex(
                    ContractError, "environment-lock numeric thread controls differ"
                ):
                    validate_environment(
                        coreai_repo=aliased_coreai,
                        model_dir=root / "model",
                        source_lock=root / "source-lock.json",
                    )

    def test_system_message_hash_is_frozen(self):
        self.assertEqual(
            hashlib.sha256(SYSTEM_MESSAGE.encode("utf-8")).hexdigest(),
            CONTRACT.system_message_utf8_sha256,
        )

    def test_token_encoding_is_count_then_u32_big_endian(self):
        expected = struct.pack(">QIII", 3, 0, 1, 0xFFFFFFFF)
        actual = canonical_token_bytes([0, 1, 0xFFFFFFFF])
        self.assertEqual(actual, expected)
        self.assertEqual(token_ids_sha256([0, 1, 0xFFFFFFFF]), sha256_bytes(expected))

    def test_token_encoding_rejects_bool_and_out_of_range(self):
        with self.assertRaises(ContractError):
            canonical_token_bytes([True])
        with self.assertRaises(ContractError):
            canonical_token_bytes([-1])
        with self.assertRaises(ContractError):
            canonical_token_bytes([0x1_0000_0000])

    def test_committed_prompt_manifest_validates(self):
        _, cases = validate_prompt_manifest(ROOT / "prompt-manifest.json")
        self.assertEqual(len(cases), 10)
        self.assertEqual(
            tuple(case["id"] for case in cases),
            CONTRACT.tuning_ids + CONTRACT.holdout_ids,
        )

    def test_no_thinking_serialization_is_fail_closed(self):
        case = {"id": "synthetic", "split": "tuning", "prompt": "hello"}
        serialized = validate_tokenizer(FakeTokenizer(), [case])
        self.assertEqual(len(serialized), 1)
        self.assertTrue(
            serialized[0]["serializedText"].endswith(
                "<|im_start|>assistant\n<think>\n\n</think>\n\n"
            )
        )
        with self.assertRaises(ContractError):
            validate_tokenizer(NoThinkingIgnoredTokenizer(), [case])

    def test_source_model_lock_detects_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "model"
            model.mkdir()
            (model / "config.json").write_text("{}\n", encoding="utf-8")
            lock = make_source_model_lock(model)
            lock_path = root / "source-lock.json"
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            validate_source_model_lock(model, lock_path)
            (model / "config.json").write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaises(ContractError):
                validate_source_model_lock(model, lock_path)

    def test_phase_revalidation_records_identity_and_detects_later_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "model"
            model.mkdir()
            payload = model / "config.json"
            payload.write_text("{}\n", encoding="utf-8")
            lock_path = root / "source-lock.json"
            lock_path.write_text(
                json.dumps(make_source_model_lock(model)), encoding="utf-8"
            )
            evidence = root / "revalidations.jsonl"
            _append_source_model_revalidation(
                phase="before_reference_load",
                model_dir=model,
                source_lock=lock_path,
                evidence_path=evidence,
            )
            record = json.loads(evidence.read_text().strip())
            self.assertEqual(record["phase"], "before_reference_load")
            payload.write_text('{"changed":true}\n', encoding="utf-8")
            with self.assertRaises(ContractError):
                _append_source_model_revalidation(
                    phase="after_reference_load",
                    model_dir=model,
                    source_lock=lock_path,
                    evidence_path=evidence,
                )

    def test_canonical_json_is_utf8_sorted_and_compact(self):
        self.assertEqual(
            canonical_json_bytes({"b": "中", "a": 1}), b'{"a":1,"b":"\xe4\xb8\xad"}'
        )

    def test_teacher_forced_input_hash_uses_reference_prefix(self):
        fields = _teacher_forced_input_fields([10, 20], [30, 40])
        self.assertEqual(fields["teacherForcedInputTokenCount"], 3)
        self.assertEqual(
            fields["teacherForcedInputTokenIDsSHA256"],
            token_ids_sha256([10, 20, 30]),
        )

    def test_teacher_forced_slice_starts_at_last_prompt_position(self):
        self.assertEqual(
            _teacher_forced_slice_bounds(
                prompt_length=3,
                completion_length=2,
                available_rows=4,
            ),
            (2, 4),
        )
        with self.assertRaises(ContractError):
            _teacher_forced_slice_bounds(
                prompt_length=3,
                completion_length=2,
                available_rows=3,
            )

    def test_causal_mask_uses_absolute_cache_offset(self):
        class NumpyTorch:
            float16 = np.float16

            @staticmethod
            def zeros(shape, dtype):
                return np.zeros(shape, dtype=dtype)

        mask = _construct_causal_mask(6, 2, 2, NumpyTorch)
        expected = np.array(
            [
                [0.0, 0.0],
                [0.0, 0.0],
                [0.0, 0.0],
                [-np.inf, 0.0],
                [-np.inf, -np.inf],
                [-np.inf, -np.inf],
            ],
            dtype=np.float16,
        )
        np.testing.assert_array_equal(mask[0, :, 0, :], expected)

    def test_failed_comparison_keeps_required_fields_without_partial_metrics(self):
        case = {
            "id": "synthetic",
            "split": "holdout",
            "serializedUTF8SHA256": "a" * 64,
            "inputTokenIDsSHA256": "b" * 64,
        }
        shared_history = "c" * 64
        reference = {
            "status": "success",
            "completionTokenCount": 2,
            "completionTokenIDsSHA256": "d" * 64,
            "teacherForcedInputTokenCount": 5,
            "teacherForcedInputTokenIDsSHA256": shared_history,
        }
        candidate = {
            "status": "failed",
            "completionTokenCount": 1,
            "completionTokenIDsSHA256": "e" * 64,
            "teacherForcedInputTokenCount": 5,
            "teacherForcedInputTokenIDsSHA256": shared_history,
        }
        record = _failed_comparison(
            case=case,
            reference_record=reference,
            candidate_record=candidate,
            error=RuntimeError("synthetic failure"),
        )
        self.assertIsNone(record["T_i"])
        self.assertEqual(record["intendedPositions"], 2)
        self.assertIsNone(record["C_i"])
        self.assertIsNone(record["NLL_i_candidate"])
        self.assertEqual(record["direction"], CONTRACT.direction)
        self.assertTrue(record["teacherForcedInputTokenIDsElementwiseIdentical"])

    def test_preflight_failure_retains_all_frozen_case_model_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = _write_preflight_failure_evidence(
                run_id="00000000-0000-4000-8000-000000000000",
                output_dir=output,
                error=ContractError("synthetic preflight failure"),
                started_wall=time.time(),
                started_monotonic=time.monotonic(),
            )
            self.assertEqual(result, 2)
            model_runs = [
                json.loads(line)
                for line in (output / "model-runs.jsonl").read_text().splitlines()
            ]
            comparisons = [
                json.loads(line)
                for line in (output / "case-comparisons.jsonl").read_text().splitlines()
            ]
            self.assertEqual(len(model_runs), 20)
            self.assertEqual(len(comparisons), 10)
            self.assertEqual(
                [record["modelRole"] for record in model_runs[:10]],
                ["reference"] * 10,
            )
            self.assertTrue(all(record["T_i"] is None for record in comparisons))
            aggregates = json.loads((output / "aggregates.json").read_text())
            self.assertTrue(
                all(split["status"] == "failed" for split in aggregates["splits"])
            )

    def test_run_id_claim_rejects_cross_directory_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=Fidelity Test",
                    "-c",
                    "user.email=fidelity@example.invalid",
                    "commit",
                    "-q",
                    "--allow-empty",
                    "-m",
                    "initial",
                ],
                cwd=repo,
                check=True,
            )
            run_id = "00000000-0000-4000-8000-000000000000"
            claim = _claim_run_id(
                run_id=run_id,
                output_dir=repo / "first-output",
                repo_root=repo,
            )
            self.assertTrue(claim.is_file())
            with self.assertRaises(ContractError):
                _claim_run_id(
                    run_id=run_id,
                    output_dir=repo / "second-output",
                    repo_root=repo,
                )


if __name__ == "__main__":
    unittest.main()
