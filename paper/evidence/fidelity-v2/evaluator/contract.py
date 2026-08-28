"""Frozen identities and validation for the fidelity-v2 experiment."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


class ContractError(RuntimeError):
    """Raised when a preregistered input or environment contract is violated."""


SYSTEM_MESSAGE = (
    "你是 e1 的本地语义引擎。只完成用户要求的书签语义任务，严格遵守输出格式。"
    "不要输出推理过程。/no_think"
)


@dataclass(frozen=True)
class FrozenContract:
    schema: str = "qwen3-coreai-ios-fidelity-evaluator-v1"
    source_model_id: str = "Qwen/Qwen3-1.7B"
    source_model_revision: str = "70d244cc86ccca08cf5af4e1e306ecf908b1ad5e"
    apple_repository: str = "https://github.com/apple/coreai-models.git"
    apple_base_commit: str = "04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a"
    apple_uv_lock_sha256: str = (
        "64228831804cc3444dbb5dc310bff62fe6163b47beca1a3592b5d557dfe846fa"
    )
    protocol_sha256: str = (
        "b7d98264068aad19b950e96af04c52fa027e57afcf67062e06125c9a875cc6b2"
    )
    amendment_1_sha256: str = (
        "07eab8874485e8954ee959d611de302de122ad04c1e5c0fcca6f1e957ab368d3"
    )
    prompt_manifest_file_sha256: str = (
        "59eedc731dab284755a59fc60b548a034a2a657ed8c9998413d58419b5ac1a95"
    )
    prompt_manifest_canonical_sha256: str = (
        "02a02f8141c2fb21f0316593a7b244afa56794490d6ff6ffc0daef38153ea367"
    )
    paper_patch_sha256: str = (
        "bc8f135d5637d629beac727e4d10b0b6e909ebcc77206c39c971d8967d4360d4"
    )
    recipe_sha256: str = (
        "dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72"
    )
    system_message_utf8_sha256: str = (
        "4703112ab40bd8cfb768089c6f98e2161a71346e683b6b6a2585a122f9d236a9"
    )
    seed: int = 0
    max_new_tokens: int = 64
    max_total_context: int = 1024
    target_dtype: str = "float16"
    direction: str = "candidate_minus_reference"
    tuning_ids: tuple[str, ...] = (
        "semantic_zh_01",
        "semantic_zh_02",
        "semantic_en_01",
        "echo_zh_01",
        "retrieval_zh_01",
        "schema_zh_01",
    )
    holdout_ids: tuple[str, ...] = (
        "semantic_zh_holdout",
        "echo_mixed_holdout",
        "selection_holdout",
        "injection_holdout",
    )


CONTRACT = FrozenContract()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def write_json(path: Path, value: Any) -> None:
    """Write deterministic UTF-8 JSON without permitting NaN or Infinity."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    )
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json_bytes(value) + b"\n"
    with path.open("ab") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def canonical_token_bytes(token_ids: Sequence[int]) -> bytes:
    """Encode tokens as u64-be count followed by u32-be token IDs."""

    encoded = bytearray(struct.pack(">Q", len(token_ids)))
    for index, token_id in enumerate(token_ids):
        if isinstance(token_id, bool) or not isinstance(token_id, int):
            raise ContractError(f"token {index} is not an integer: {token_id!r}")
        if not 0 <= token_id <= 0xFFFFFFFF:
            raise ContractError(
                f"token {index} is outside unsigned-32 range: {token_id}"
            )
        encoded.extend(struct.pack(">I", token_id))
    return bytes(encoded)


def token_ids_sha256(token_ids: Sequence[int]) -> str:
    return sha256_bytes(canonical_token_bytes(token_ids))


def run_checked(
    arguments: Sequence[str],
    *,
    cwd: Path | None = None,
    input_bytes: bytes | None = None,
) -> str:
    result = subprocess.run(
        list(arguments),
        cwd=cwd,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise ContractError(f"command failed ({' '.join(arguments)}): {stderr}")
    return result.stdout.decode("utf-8", errors="strict").strip()


def git_patch_id(patch: bytes, *, cwd: Path) -> str:
    output = run_checked(["git", "patch-id", "--stable"], cwd=cwd, input_bytes=patch)
    fields = output.split()
    if len(fields) < 1 or not re.fullmatch(r"[0-9a-f]{40}", fields[0]):
        raise ContractError(f"could not parse stable patch id: {output!r}")
    return fields[0]


def validate_coreai_checkout(
    coreai_repo: Path, paper_patch: Path, recipe: Path
) -> dict[str, Any]:
    coreai_repo = coreai_repo.resolve()
    paper_patch = paper_patch.resolve()
    recipe = recipe.resolve()
    if not (coreai_repo / ".git").exists():
        raise ContractError(f"not a coreai-models Git checkout: {coreai_repo}")

    head = run_checked(["git", "rev-parse", "HEAD"], cwd=coreai_repo)
    if head != CONTRACT.apple_base_commit:
        raise ContractError(
            f"coreai-models HEAD is {head}; expected {CONTRACT.apple_base_commit}"
        )
    if sha256_file(coreai_repo / "uv.lock") != CONTRACT.apple_uv_lock_sha256:
        raise ContractError("pinned coreai-models uv.lock hash does not match")
    if sha256_file(paper_patch) != CONTRACT.paper_patch_sha256:
        raise ContractError("paper patch hash does not match the frozen protocol")
    if sha256_file(recipe) != CONTRACT.recipe_sha256:
        raise ContractError("paper recipe hash does not match the frozen protocol")

    expected_patch = paper_patch.read_bytes()
    unstaged = run_checked(["git", "diff", "--binary"], cwd=coreai_repo)
    if unstaged:
        raise ContractError("coreai-models checkout has unstaged tracked changes")
    actual_patch = subprocess.run(
        [
            "git",
            "-c",
            "core.abbrev=7",
            "-c",
            "diff.algorithm=myers",
            "-c",
            "color.ui=false",
            "diff",
            "--cached",
            "--binary",
            "--no-ext-diff",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--unified=3",
            "--no-renames",
            "HEAD",
        ],
        cwd=coreai_repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if actual_patch.returncode != 0:
        raise ContractError(actual_patch.stderr.decode("utf-8", errors="replace"))
    if not actual_patch.stdout:
        raise ContractError(
            "the frozen paper patch has not been applied with git apply --index"
        )
    actual_patch_sha256 = sha256_bytes(actual_patch.stdout)
    if actual_patch_sha256 != CONTRACT.paper_patch_sha256:
        raise ContractError(
            "coreai-models staged diff bytes are not exactly the frozen paper patch "
            f"(got SHA-256 {actual_patch_sha256})"
        )

    expected_patch_id = git_patch_id(expected_patch, cwd=coreai_repo)
    actual_patch_id = git_patch_id(actual_patch.stdout, cwd=coreai_repo)
    if actual_patch_id != expected_patch_id:
        raise ContractError(
            "coreai-models tracked changes are not exactly the frozen paper patch "
            f"(expected patch-id {expected_patch_id}, got {actual_patch_id})"
        )
    run_checked(
        ["git", "apply", "--reverse", "--check", str(paper_patch)], cwd=coreai_repo
    )

    forbidden_untracked = run_checked(
        [
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            "python/src",
            "models/qwen3",
        ],
        cwd=coreai_repo,
    ).splitlines()
    if forbidden_untracked:
        raise ContractError(
            f"untracked source files in coreai-models: {forbidden_untracked}"
        )

    patched_recipe = coreai_repo / "models/qwen3/qwen3_1_7b_w8_per_tensor.yaml"
    if (
        not patched_recipe.is_file()
        or sha256_file(patched_recipe) != CONTRACT.recipe_sha256
    ):
        raise ContractError(
            "patched coreai-models recipe is absent or differs from paper recipe"
        )

    return {
        "repository": CONTRACT.apple_repository,
        "baseCommit": head,
        "paperPatchSHA256": CONTRACT.paper_patch_sha256,
        "stagedDiffSHA256": actual_patch_sha256,
        "stablePatchID": actual_patch_id,
        "uvLockSHA256": CONTRACT.apple_uv_lock_sha256,
        "recipeSHA256": CONTRACT.recipe_sha256,
    }


def validate_prompt_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if sha256_file(path) != CONTRACT.prompt_manifest_file_sha256:
        raise ContractError(
            "prompt manifest file hash does not match the frozen commit"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "qwen3-coreai-ios-fidelity-prompt-manifest-v1":
        raise ContractError("unexpected prompt manifest schema")
    stored_canonical = manifest.get("canonicalSHA256")
    canonical_payload = {
        key: value for key, value in manifest.items() if key != "canonicalSHA256"
    }
    computed_canonical = sha256_bytes(canonical_json_bytes(canonical_payload))
    if (
        stored_canonical != computed_canonical
        or computed_canonical != CONTRACT.prompt_manifest_canonical_sha256
    ):
        raise ContractError("prompt manifest canonical SHA-256 does not match")

    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 10:
        raise ContractError("prompt manifest must contain exactly ten cases")
    expected_ids = CONTRACT.tuning_ids + CONTRACT.holdout_ids
    actual_ids = tuple(case.get("id") for case in cases)
    if actual_ids != expected_ids:
        raise ContractError(f"case order/identity differs: {actual_ids!r}")
    for case in cases:
        expected_split = "tuning" if case["id"] in CONTRACT.tuning_ids else "holdout"
        if case.get("split") != expected_split:
            raise ContractError(f"split mismatch for {case['id']}")
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ContractError(f"missing prompt text for {case['id']}")
        prompt_hash = sha256_bytes(prompt.encode("utf-8"))
        if case.get("promptUTF8SHA256") != prompt_hash:
            raise ContractError(f"prompt UTF-8 hash mismatch for {case['id']}")
    return manifest, cases


def _manifest_files(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == ".DS_Store" or relative.startswith(".cache/"):
            continue
        entries.append(
            {
                "path": relative,
                "sizeBytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def make_source_model_lock(model_dir: Path) -> dict[str, Any]:
    model_dir = model_dir.resolve()
    files = _manifest_files(model_dir)
    if not files:
        raise ContractError(f"source model directory is empty: {model_dir}")
    payload = {
        "schema": "qwen3-coreai-ios-source-model-lock-v1",
        "repository": CONTRACT.source_model_id,
        "revision": CONTRACT.source_model_revision,
        "acquisition": {
            "method": "huggingface_hub.snapshot_download",
            "requestedRepository": CONTRACT.source_model_id,
            "requestedRevision": CONTRACT.source_model_revision,
        },
        "files": files,
    }
    payload["canonicalSHA256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_source_model_lock(model_dir: Path, lock_path: Path) -> dict[str, Any]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    stored = lock.get("canonicalSHA256")
    unsigned = {key: value for key, value in lock.items() if key != "canonicalSHA256"}
    computed = sha256_bytes(canonical_json_bytes(unsigned))
    if stored != computed:
        raise ContractError("source model lock canonical SHA-256 does not match")
    if lock.get("schema") != "qwen3-coreai-ios-source-model-lock-v1":
        raise ContractError("unexpected source model lock schema")
    if lock.get("repository") != CONTRACT.source_model_id:
        raise ContractError("source model repository mismatch")
    if lock.get("revision") != CONTRACT.source_model_revision:
        raise ContractError("source model revision mismatch")
    if lock.get("acquisition") != {
        "method": "huggingface_hub.snapshot_download",
        "requestedRepository": CONTRACT.source_model_id,
        "requestedRevision": CONTRACT.source_model_revision,
    }:
        raise ContractError("source model lock acquisition record differs")
    actual = make_source_model_lock(model_dir)
    if lock.get("files") != actual.get("files"):
        raise ContractError(
            "source model directory differs from its frozen file manifest"
        )
    return lock


def validate_tokenizer(
    tokenizer: Any, cases: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    if (
        sha256_bytes(SYSTEM_MESSAGE.encode("utf-8"))
        != CONTRACT.system_message_utf8_sha256
    ):
        raise ContractError("system-message constant hash mismatch")
    template = getattr(tokenizer, "chat_template", None)
    if not isinstance(template, str) or "enable_thinking" not in template:
        raise ContractError("pinned tokenizer template does not expose enable_thinking")

    serialized_cases: list[dict[str, Any]] = []
    for case in cases:
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": case["prompt"]},
        ]
        try:
            serialized_false = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            serialized_true = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=True,
            )
            templated_ids = tokenizer.apply_chat_template(
                messages,
                tokenize=True,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except Exception as error:
            raise ContractError(
                f"no-thinking chat template failed for {case['id']}: {type(error).__name__}: {error}"
            ) from error

        if not isinstance(serialized_false, str):
            raise ContractError(f"chat template returned non-text for {case['id']}")
        required_suffix = "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        if not serialized_false.endswith(required_suffix):
            raise ContractError(
                f"no-thinking serialization is not explicit for {case['id']}"
            )
        if serialized_false == serialized_true:
            raise ContractError(
                f"enable_thinking=false had no observable effect for {case['id']}"
            )
        encoded = tokenizer(serialized_false, add_special_tokens=False)
        direct_ids = (
            encoded["input_ids"] if isinstance(encoded, dict) else encoded.input_ids
        )
        direct_ids = [int(value) for value in direct_ids]
        templated_ids = [int(value) for value in templated_ids]
        if direct_ids != templated_ids:
            raise ContractError(
                f"template text and template token IDs disagree for {case['id']}"
            )
        if not direct_ids:
            raise ContractError(f"empty serialized token sequence for {case['id']}")
        if len(direct_ids) + CONTRACT.max_new_tokens > CONTRACT.max_total_context:
            raise ContractError(
                f"{case['id']} cannot fit without truncation: "
                f"{len(direct_ids)} + {CONTRACT.max_new_tokens} > {CONTRACT.max_total_context}"
            )
        serialized_cases.append(
            {
                "id": case["id"],
                "split": case["split"],
                "serializedText": serialized_false,
                "serializedUTF8SHA256": sha256_bytes(serialized_false.encode("utf-8")),
                "inputTokenIDs": direct_ids,
                "inputTokenCount": len(direct_ids),
                "inputTokenIDsSHA256": token_ids_sha256(direct_ids),
                "tokenEncoding": "u64be-count-followed-by-u32be-token-ids",
            }
        )
    return serialized_cases


def source_tree_manifest(paths: Iterable[Path], root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted({path.resolve() for path in paths}):
        records.append(
            {
                "path": path.relative_to(root.resolve()).as_posix(),
                "sizeBytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return records
