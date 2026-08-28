from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import torch
except ImportError:  # pragma: no cover - exercised only outside the frozen env
    torch = None

from evaluator.contract import ContractError  # noqa: E402
from evaluator.runtime import (  # noqa: E402
    _normalise_logits,
    greedy_completion,
    teacher_forced_logits,
)


@unittest.skipIf(torch is None, "Torch is unavailable outside the frozen environment")
class RuntimeTests(unittest.TestCase):
    def test_greedy_completion_updates_absolute_offsets_and_stops_at_eos(self):
        class ScriptedModel:
            def __init__(self):
                self.tokens = [5, 6, 2]
                self.calls = []

            def __call__(
                self,
                input_ids,
                position_ids,
                offset,
                causal_mask,
                key_cache,
                value_cache,
            ):
                del key_cache, value_cache
                self.calls.append(
                    {
                        "input": input_ids.clone(),
                        "positions": position_ids.clone(),
                        "offset": offset.clone(),
                        "mask": causal_mask.clone(),
                    }
                )
                query_length = input_ids.shape[1]
                output = torch.full(
                    (1, 1, query_length, 8),
                    -10.0,
                    dtype=torch.float16,
                )
                output[0, 0, :, 0] = -9.0
                output[0, 0, -1, self.tokens[len(self.calls) - 1]] = 10.0
                return output

        model = ScriptedModel()
        with patch(
            "evaluator.runtime._new_caches",
            return_value=(torch.zeros(1), torch.zeros(1)),
        ):
            result = greedy_completion(model, [10, 11, 12], eos_token_id=2)
        self.assertEqual(result, {"tokenIDs": [5, 6, 2], "termination": "eos"})
        self.assertEqual(
            [int(call["offset"].item()) for call in model.calls], [0, 3, 4]
        )
        self.assertEqual(model.calls[0]["positions"].dtype, torch.uint16)
        self.assertEqual(model.calls[0]["positions"].tolist(), [[0, 1, 2]])
        self.assertEqual(model.calls[1]["positions"].tolist(), [[3]])
        self.assertEqual(model.calls[2]["positions"].tolist(), [[4]])
        self.assertEqual(model.calls[1]["input"].tolist(), [[5]])
        self.assertEqual(model.calls[2]["input"].tolist(), [[6]])
        self.assertTrue(bool(torch.isneginf(model.calls[1]["mask"][0, 4:, 0, 0]).all()))
        self.assertTrue(bool((model.calls[1]["mask"][0, :4, 0, 0] == 0).all()))

    def test_teacher_forcing_selects_last_prompt_row_then_reference_prefix_rows(self):
        class PositionModel:
            def __init__(self):
                self.input_ids = None
                self.positions = None

            def __call__(
                self,
                input_ids,
                position_ids,
                offset,
                causal_mask,
                key_cache,
                value_cache,
            ):
                del offset, causal_mask, key_cache, value_cache
                self.input_ids = input_ids.clone()
                self.positions = position_ids.clone()
                rows = torch.arange(
                    input_ids.shape[1] * 7,
                    dtype=torch.float16,
                ).reshape(input_ids.shape[1], 7)
                return rows.unsqueeze(0).unsqueeze(0)

        model = PositionModel()
        with patch(
            "evaluator.runtime._new_caches",
            return_value=(torch.zeros(1), torch.zeros(1)),
        ):
            selected = teacher_forced_logits(model, [10, 11, 12], [5, 6])
        self.assertEqual(model.input_ids.tolist(), [[10, 11, 12, 5]])
        self.assertEqual(model.positions.dtype, torch.uint16)
        expected = torch.arange(28, dtype=torch.float16).reshape(4, 7)[2:4]
        self.assertTrue(bool(torch.equal(selected, expected)))

    def test_logit_layout_and_dtype_fail_closed(self):
        valid = torch.tensor(
            [[[[1.0, 2.0, 3.0], [-1.0, 0.0, 1.0]]]], dtype=torch.float16
        )
        normalized = _normalise_logits(valid, expected_query_length=2)
        self.assertEqual(tuple(normalized.shape), (2, 3))
        with self.assertRaises(ContractError):
            _normalise_logits(valid.float(), expected_query_length=2)
        with self.assertRaises(ContractError):
            _normalise_logits(
                torch.zeros((1, 2, 3), dtype=torch.float16),
                expected_query_length=2,
            )
        with self.assertRaises(ContractError):
            _normalise_logits(valid, expected_query_length=1)

    def test_logit_gate_rejects_nonfinite_zero_norm_and_zero_range_rows(self):
        invalid_rows = (
            torch.tensor([[[[1.0, float("nan")]]]], dtype=torch.float16),
            torch.zeros((1, 1, 1, 2), dtype=torch.float16),
            torch.ones((1, 1, 1, 2), dtype=torch.float16),
        )
        for output in invalid_rows:
            with self.subTest(output=output):
                with self.assertRaises(ContractError):
                    _normalise_logits(output, expected_query_length=1)


if __name__ == "__main__":
    unittest.main()
