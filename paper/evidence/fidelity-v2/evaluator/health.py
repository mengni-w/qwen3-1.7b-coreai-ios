"""One-shot Apple/Hugging Face numerical-parity health probe."""

from __future__ import annotations

import gc
import json
import shutil
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

from .contract import (
    CONTRACT,
    ContractError,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    token_ids_sha256,
    write_json,
)
from .runtime import (
    _append_source_model_revalidation,
    _construct_causal_mask,
    _load_reference,
    _new_caches,
    _normalise_logits,
    _peak_rss_record,
    repository_root,
)


HEALTH_CASE_ID = "semantic_zh_01"
HEALTH_PREFIX_TOKENS = 16
HEALTH_COSINE_FLOOR = 0.99


def _vector_summary(vector: Any, *, label: str) -> dict[str, Any]:
    import torch

    if vector.ndim != 1:
        raise ContractError(f"{label} logit vector is not rank one")
    fp32 = vector.detach().cpu().to(torch.float32)
    if not bool(torch.isfinite(fp32).all()):
        raise ContractError(f"{label} logit vector contains a non-finite value")
    norm = float(torch.linalg.vector_norm(fp32).item())
    minimum = float(fp32.amin().item())
    maximum = float(fp32.amax().item())
    dynamic_range = maximum - minimum
    if norm <= 0:
        raise ContractError(f"{label} logit vector has zero norm")
    if dynamic_range <= 0:
        raise ContractError(f"{label} logit vector has zero dynamic range")
    return {
        "dtype": str(vector.dtype),
        "elementCount": int(vector.numel()),
        "allFinite": True,
        "fp32EuclideanNorm": norm,
        "minimum": minimum,
        "maximum": maximum,
        "dynamicRange": dynamic_range,
        "top1TokenID": int(torch.argmax(fp32).item()),
    }


def _binary64_cosine(left: Any, right: Any) -> float:
    import torch

    if tuple(left.shape) != tuple(right.shape):
        raise ContractError(
            f"health-probe logit shapes differ: {tuple(left.shape)} vs {tuple(right.shape)}"
        )
    left64 = left.detach().cpu().to(torch.float64)
    right64 = right.detach().cpu().to(torch.float64)
    denominator = torch.linalg.vector_norm(left64) * torch.linalg.vector_norm(right64)
    if not bool(torch.isfinite(denominator)) or float(denominator.item()) <= 0:
        raise ContractError("health-probe cosine denominator is invalid")
    cosine = float(torch.dot(left64, right64).item() / denominator.item())
    if not (-1.0 <= cosine <= 1.0):
        raise ContractError(f"health-probe cosine is outside [-1, 1]: {cosine}")
    return cosine


def _selected_prefix(serialized_cases: Sequence[dict[str, Any]]) -> list[int]:
    case = next(
        (item for item in serialized_cases if item["id"] == HEALTH_CASE_ID), None
    )
    if case is None:
        raise ContractError(f"health-probe case is missing: {HEALTH_CASE_ID}")
    prefix = list(case["inputTokenIDs"][:HEALTH_PREFIX_TOKENS])
    if len(prefix) != HEALTH_PREFIX_TOKENS:
        raise ContractError("health-probe input does not contain 16 frozen tokens")
    return prefix


def run_health_probe(
    *,
    probe_id: str,
    coreai_repo: Path,
    model_dir: Path,
    source_lock: Path,
    output_dir: Path,
    preflight: tuple[dict[str, Any], Any, list[dict[str, Any]], int],
) -> int:
    del coreai_repo
    import torch

    environment, _tokenizer, serialized_cases, _eos_token_id = preflight
    started_wall = time.time()
    started_monotonic = time.monotonic()
    prefix = _selected_prefix(serialized_cases)
    prefix_hash = token_ids_sha256(prefix)
    root = repository_root()
    environment = dict(environment)
    environment["probeID"] = probe_id
    environment["startedAtUnixSeconds"] = started_wall
    write_json(output_dir / "environment.json", environment)
    shutil.copyfile(
        root / "paper/evidence/fidelity-v2/environment.lock.json",
        output_dir / "environment.lock.json",
    )
    shutil.copyfile(source_lock, output_dir / "source-model-lock.json")
    write_json(
        output_dir / "health-input.json",
        {
            "schema": "qwen3-coreai-ios-fidelity-health-input-v1",
            "caseID": HEALTH_CASE_ID,
            "prefixTokenCount": HEALTH_PREFIX_TOKENS,
            "inputTokenIDs": prefix,
            "inputTokenIDsSHA256": prefix_hash,
            "tokenEncoding": "u64be-count-followed-by-u32be-token-ids",
        },
    )
    revalidations = output_dir / "source-model-revalidations.jsonl"
    apple_vector = None
    hf_vector = None
    apple_summary = None
    hf_summary = None
    try:
        _append_source_model_revalidation(
            phase="before_health_apple_load",
            model_dir=model_dir,
            source_lock=source_lock,
            evidence_path=revalidations,
        )
        apple_model, apple_identity = _load_reference(model_dir)
        _append_source_model_revalidation(
            phase="after_health_apple_load",
            model_dir=model_dir,
            source_lock=source_lock,
            evidence_path=revalidations,
        )
        try:
            key_cache, value_cache = _new_caches(apple_model, torch)
            input_ids = torch.tensor([prefix], dtype=torch.int32)
            positions = torch.arange(len(prefix)).to(torch.uint16).unsqueeze(0)
            offset = torch.tensor([0], dtype=torch.int32)
            mask = _construct_causal_mask(
                CONTRACT.max_total_context, len(prefix), 0, torch
            )
            with torch.inference_mode():
                output = apple_model(
                    input_ids,
                    positions,
                    offset,
                    mask,
                    key_cache,
                    value_cache,
                )
            apple_vector = (
                _normalise_logits(output, expected_query_length=len(prefix))[-1]
                .detach()
                .cpu()
            )
            apple_summary = _vector_summary(apple_vector, label="Apple")
        finally:
            del apple_model
            gc.collect()

        _append_source_model_revalidation(
            phase="before_health_hf_load",
            model_dir=model_dir,
            source_lock=source_lock,
            evidence_path=revalidations,
        )
        from transformers import AutoModelForCausalLM

        hf_model = AutoModelForCausalLM.from_pretrained(
            str(model_dir),
            local_files_only=True,
            trust_remote_code=False,
            dtype=torch.float16,
            attn_implementation="eager",
        ).eval()
        hf_implementation = f"{type(hf_model).__module__}.{type(hf_model).__name__}"
        _append_source_model_revalidation(
            phase="after_health_hf_load",
            model_dir=model_dir,
            source_lock=source_lock,
            evidence_path=revalidations,
        )
        try:
            if getattr(hf_model.config, "_attn_implementation", None) != "eager":
                raise ContractError(
                    "Hugging Face health reference is not using eager attention"
                )
            with torch.inference_mode():
                hf_output = hf_model(
                    input_ids=torch.tensor([prefix], dtype=torch.long),
                    use_cache=False,
                )
            hf_vector = hf_output.logits[0, -1].detach().cpu()
            hf_summary = _vector_summary(hf_vector, label="Hugging Face")
        finally:
            del hf_model
            gc.collect()

        cosine = _binary64_cosine(apple_vector, hf_vector)
        same_top1 = apple_summary["top1TokenID"] == hf_summary["top1TokenID"]
        if not same_top1:
            raise ContractError(
                "Apple and Hugging Face health logits select different top-1 tokens"
            )
        if cosine < HEALTH_COSINE_FLOOR:
            raise ContractError(
                f"Apple/Hugging Face health cosine {cosine} is below {HEALTH_COSINE_FLOOR}"
            )
        result = {
            "schema": "qwen3-coreai-ios-fidelity-health-probe-v1",
            "probeID": probe_id,
            "status": "success",
            "caseID": HEALTH_CASE_ID,
            "prefixTokenCount": HEALTH_PREFIX_TOKENS,
            "inputTokenIDsSHA256": prefix_hash,
            "serializedInputManifestSHA256": sha256_bytes(
                canonical_json_bytes(serialized_cases)
            ),
            "apple": {"modelIdentity": apple_identity, "vector": apple_summary},
            "huggingFace": {
                "implementation": hf_implementation,
                "dtype": "torch.float16",
                "attentionImplementation": "eager",
                "vector": hf_summary,
            },
            "binary64Cosine": cosine,
            "cosineFloor": HEALTH_COSINE_FLOOR,
            "sameTop1": True,
            "identities": {
                "sourceModelCanonicalSHA256": environment["sourceModel"][
                    "canonicalSHA256"
                ],
                "coreAIModels": environment["coreAIModels"],
                "evaluator": environment["evaluator"],
                "environmentLockSHA256": sha256_file(
                    output_dir / "environment.lock.json"
                ),
            },
            "startedAtUnixSeconds": started_wall,
            "finishedAtUnixSeconds": time.time(),
            "elapsedSeconds": time.monotonic() - started_monotonic,
            "peakMemory": _peak_rss_record(),
        }
    except Exception as error:
        result = {
            "schema": "qwen3-coreai-ios-fidelity-health-probe-v1",
            "probeID": probe_id,
            "status": "failed",
            "caseID": HEALTH_CASE_ID,
            "prefixTokenCount": HEALTH_PREFIX_TOKENS,
            "inputTokenIDsSHA256": prefix_hash,
            "appleVector": apple_summary,
            "huggingFaceVector": hf_summary,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": "".join(traceback.format_exception(error)),
            },
            "startedAtUnixSeconds": started_wall,
            "finishedAtUnixSeconds": time.time(),
            "elapsedSeconds": time.monotonic() - started_monotonic,
            "peakMemory": _peak_rss_record(),
        }
    write_json(output_dir / "health-probe.json", result)
    return 0 if result["status"] == "success" else 2


def verify_health_probe(
    *,
    probe_dir: Path,
    environment: dict[str, Any],
    serialized_cases: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    manifest = probe_dir / "MANIFEST.sha256"
    if not manifest.is_file():
        raise ContractError("health probe has no evidence manifest")
    expected_paths = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if (
            separator != "  "
            or not relative
            or relative.startswith("/")
            or ".." in Path(relative).parts
        ):
            raise ContractError("health-probe evidence manifest is malformed")
        path = probe_dir / relative
        if not path.is_file() or sha256_file(path) != digest:
            raise ContractError(f"health-probe evidence hash mismatch: {relative}")
        expected_paths.add(relative)
    actual_paths = {
        path.relative_to(probe_dir).as_posix()
        for path in probe_dir.rglob("*")
        if path.is_file() and path != manifest
    }
    if actual_paths != expected_paths:
        raise ContractError("health-probe evidence manifest does not cover every file")

    result = json.loads((probe_dir / "health-probe.json").read_text(encoding="utf-8"))
    process = json.loads(
        (probe_dir / "process-result.json").read_text(encoding="utf-8")
    )
    if result.get("status") != "success" or process.get("exitCode") != 0:
        raise ContractError("health probe did not complete successfully")
    prefix = _selected_prefix(serialized_cases)
    if result.get("inputTokenIDsSHA256") != token_ids_sha256(prefix):
        raise ContractError("health-probe frozen prefix differs")
    if result.get("serializedInputManifestSHA256") != sha256_bytes(
        canonical_json_bytes(serialized_cases)
    ):
        raise ContractError("health-probe serialized-input manifest differs")
    if result.get("cosineFloor") != HEALTH_COSINE_FLOOR:
        raise ContractError("health-probe cosine floor differs")
    if (
        result.get("sameTop1") is not True
        or result.get("binary64Cosine", -1) < HEALTH_COSINE_FLOOR
    ):
        raise ContractError("health-probe parity gate is not satisfied")
    identities = result.get("identities", {})
    if (
        identities.get("sourceModelCanonicalSHA256")
        != environment["sourceModel"]["canonicalSHA256"]
    ):
        raise ContractError("health-probe source model differs")
    if identities.get("coreAIModels") != environment["coreAIModels"]:
        raise ContractError("health-probe Apple checkout differs")
    probe_evaluator = identities.get("evaluator", {})
    current_evaluator = environment["evaluator"]
    for key in (
        "protocolCommit",
        "promptManifestCommit",
        "amendmentCommit",
        "evaluatorCommit",
        "sourceFiles",
    ):
        if probe_evaluator.get(key) != current_evaluator.get(key):
            raise ContractError(f"health-probe evaluator identity differs: {key}")
    lock_sha = sha256_file(
        repository_root() / "paper/evidence/fidelity-v2/environment.lock.json"
    )
    if identities.get("environmentLockSHA256") != lock_sha:
        raise ContractError("health-probe environment lock differs")
    return {
        "schema": "qwen3-coreai-ios-fidelity-health-validation-v1",
        "status": "success",
        "probeID": result["probeID"],
        "healthProbeManifestSHA256": sha256_file(manifest),
        "binary64Cosine": result["binary64Cosine"],
        "sameTop1": True,
    }
