"""Binary64 fidelity metrics specified by EXPERIMENT_PROTOCOL_V1."""

from __future__ import annotations

import math
from typing import Any, Iterable, Sequence

from .contract import CONTRACT, ContractError


def _require_numpy():  # type: ignore[no-untyped-def]
    try:
        import numpy as np
    except (
        ImportError
    ) as error:  # pragma: no cover - exercised by environment validation
        raise ContractError(
            "NumPy is required for binary64 fidelity metrics"
        ) from error
    return np


def compute_case_metrics(
    reference_logits: Any,
    candidate_logits: Any,
    reference_token_ids: Sequence[int],
) -> dict[str, Any]:
    """Compute one case using explicit IEEE-754 binary64 arrays.

    Rows are completion positions, columns are vocabulary logits. The candidate
    and reference rows must be conditioned on the same reference-token history.
    """

    np = _require_numpy()
    reference = np.asarray(reference_logits, dtype=np.float64)
    candidate = np.asarray(candidate_logits, dtype=np.float64)
    if reference.ndim != 2 or candidate.ndim != 2:
        raise ContractError("reference and candidate logits must both be rank two")
    if reference.shape != candidate.shape:
        raise ContractError(
            f"logit shape mismatch: reference {reference.shape}, candidate {candidate.shape}"
        )
    position_count, vocabulary_size = reference.shape
    if position_count == 0 or vocabulary_size == 0:
        raise ContractError("logit matrices must be non-empty")
    if position_count != len(reference_token_ids):
        raise ContractError(
            f"token count {len(reference_token_ids)} != logit rows {position_count}"
        )
    if not bool(np.isfinite(reference).all()) or not bool(np.isfinite(candidate).all()):
        raise ContractError("non-finite logit encountered")

    tokens = np.asarray(reference_token_ids, dtype=np.int64)
    if bool(((tokens < 0) | (tokens >= vocabulary_size)).any()):
        raise ContractError(
            "reference completion token is outside the logit vocabulary"
        )

    cosine_values: list[float] = []
    reference_nll_values: list[float] = []
    candidate_nll_values: list[float] = []
    agreement_count = 0

    for position in range(position_count):
        reference_row = reference[position]
        candidate_row = candidate[position]
        reference_norm = float(np.sqrt(np.dot(reference_row, reference_row)))
        candidate_norm = float(np.sqrt(np.dot(candidate_row, candidate_row)))
        if not math.isfinite(reference_norm) or not math.isfinite(candidate_norm):
            raise ContractError(f"non-finite logit norm at position {position}")
        if reference_norm == 0.0 or candidate_norm == 0.0:
            raise ContractError(f"zero logit norm at position {position}")
        cosine = float(np.dot(candidate_row, reference_row)) / (
            candidate_norm * reference_norm
        )
        if not math.isfinite(cosine):
            raise ContractError(f"non-finite cosine at position {position}")
        cosine_values.append(cosine)

        if int(np.argmax(candidate_row)) == int(np.argmax(reference_row)):
            agreement_count += 1

        target = int(tokens[position])
        for row, destination in (
            (reference_row, reference_nll_values),
            (candidate_row, candidate_nll_values),
        ):
            maximum = float(np.max(row))
            log_sum_exp = maximum + math.log(
                float(np.exp(row - maximum).sum(dtype=np.float64))
            )
            nll = log_sum_exp - float(row[target])
            if not math.isfinite(nll):
                raise ContractError(f"non-finite NLL at position {position}")
            destination.append(nll)

    denominator = float(position_count)
    mean_cosine = math.fsum(cosine_values) / denominator
    reference_nll = math.fsum(reference_nll_values) / denominator
    candidate_nll = math.fsum(candidate_nll_values) / denominator
    delta = candidate_nll - reference_nll
    values = (mean_cosine, min(cosine_values), reference_nll, candidate_nll, delta)
    if not all(math.isfinite(value) for value in values):
        raise ContractError("case metric produced a non-finite result")

    return {
        "evaluatedPositions": position_count,
        "vocabularySize": vocabulary_size,
        "meanCosine": mean_cosine,
        "minimumCosine": min(cosine_values),
        "top1Agreement": agreement_count / denominator,
        "referenceMeanNLL": reference_nll,
        "candidateMeanNLL": candidate_nll,
        "meanNLLDelta": delta,
        "nllDeltaDirection": CONTRACT.direction,
        "metricDType": "IEEE-754 binary64",
    }


def aggregate_split(
    comparisons: Iterable[dict[str, Any]],
    *,
    split: str,
    expected_ids: Sequence[str],
) -> dict[str, Any]:
    selected = [record for record in comparisons if record.get("split") == split]
    by_id = {record.get("caseID"): record for record in selected}
    if len(by_id) != len(selected):
        raise ContractError(f"duplicate comparison case in {split}")
    if tuple(record.get("caseID") for record in selected) != tuple(expected_ids):
        raise ContractError(f"comparison order/identity mismatch in {split}")

    failed = [
        case_id for case_id in expected_ids if by_id[case_id].get("status") != "success"
    ]
    if failed:
        return {
            "split": split,
            "status": "failed",
            "caseCount": len(expected_ids),
            "successfulCaseCount": len(expected_ids) - len(failed),
            "failedCaseIDs": failed,
            "aggregation": "case-level macro; unavailable when any frozen case fails",
        }

    metrics = [by_id[case_id]["metrics"] for case_id in expected_ids]
    denominator = float(len(metrics))
    return {
        "split": split,
        "status": "success",
        "caseCount": len(metrics),
        "successfulCaseCount": len(metrics),
        "failedCaseIDs": [],
        "aggregation": "case-level arithmetic macro; not token weighted",
        "meanCosine": math.fsum(metric["meanCosine"] for metric in metrics)
        / denominator,
        "minimumCosine": min(metric["minimumCosine"] for metric in metrics),
        "top1Agreement": math.fsum(metric["top1Agreement"] for metric in metrics)
        / denominator,
        "meanNLLDelta": math.fsum(metric["meanNLLDelta"] for metric in metrics)
        / denominator,
        "nllDeltaDirection": CONTRACT.direction,
    }


def aggregate_all(comparisons: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if tuple(record.get("caseID") for record in comparisons) != (
        CONTRACT.tuning_ids + CONTRACT.holdout_ids
    ):
        raise ContractError(
            "comparison records do not follow the frozen ten-case order"
        )
    return {
        "schema": "qwen3-coreai-ios-fidelity-aggregates-v1",
        "metricDType": "IEEE-754 binary64",
        "direction": CONTRACT.direction,
        "splits": [
            aggregate_split(
                comparisons, split="tuning", expected_ids=CONTRACT.tuning_ids
            ),
            aggregate_split(
                comparisons, split="holdout", expected_ids=CONTRACT.holdout_ids
            ),
        ],
    }
