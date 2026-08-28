from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluator.contract import CONTRACT, ContractError  # noqa: E402
from evaluator.metrics import aggregate_all, compute_case_metrics  # noqa: E402


class MetricTests(unittest.TestCase):
    def test_identical_logits_have_unit_cosine_agreement_and_zero_delta(self):
        reference = np.array([[2.0, 0.0, -1.0], [0.0, 3.0, 1.0]], dtype=np.float16)
        result = compute_case_metrics(reference, reference.copy(), [0, 1])
        self.assertAlmostEqual(result["meanCosine"], 1.0, places=15)
        self.assertAlmostEqual(result["minimumCosine"], 1.0, places=15)
        self.assertEqual(result["top1Agreement"], 1.0)
        self.assertEqual(result["meanNLLDelta"], 0.0)
        self.assertEqual(result["metricDType"], "IEEE-754 binary64")

    def test_positive_delta_means_candidate_is_worse_on_reference_token(self):
        reference = np.array([[3.0, 0.0]], dtype=np.float32)
        candidate = np.array([[0.0, 3.0]], dtype=np.float32)
        result = compute_case_metrics(reference, candidate, [0])
        self.assertGreater(result["meanNLLDelta"], 0.0)
        self.assertEqual(result["top1Agreement"], 0.0)
        self.assertEqual(result["nllDeltaDirection"], "candidate_minus_reference")

    def test_negative_delta_means_candidate_assigns_more_reference_probability(self):
        reference = np.array([[1.0, 0.0]], dtype=np.float64)
        candidate = np.array([[4.0, 0.0]], dtype=np.float64)
        result = compute_case_metrics(reference, candidate, [0])
        self.assertLess(result["meanNLLDelta"], 0.0)

    def test_nll_is_binary64_max_shifted_log_softmax(self):
        reference = np.array([[2.0, 0.0, -2.0]], dtype=np.float16)
        candidate = np.array([[1.0, -1.0, 0.0]], dtype=np.float16)
        result = compute_case_metrics(reference, candidate, [1])
        expected_reference = 2.0 + math.log(
            math.exp(0.0) + math.exp(-2.0) + math.exp(-4.0)
        )
        expected_candidate = 2.0 + math.log(
            math.exp(0.0) + math.exp(-2.0) + math.exp(-1.0)
        )
        self.assertAlmostEqual(
            result["referenceMeanNLL"], expected_reference, places=15
        )
        self.assertAlmostEqual(
            result["candidateMeanNLL"], expected_candidate, places=15
        )
        self.assertAlmostEqual(
            result["meanNLLDelta"],
            expected_candidate - expected_reference,
            places=15,
        )

    def test_metrics_use_case_positions_not_vocabulary_weighting(self):
        reference = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)
        candidate = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float64)
        result = compute_case_metrics(reference, candidate, [0, 1])
        self.assertAlmostEqual(result["meanCosine"], 0.5)
        self.assertEqual(result["top1Agreement"], 0.5)

    def test_zero_norm_nonfinite_shape_and_token_fail_closed(self):
        with self.assertRaises(ContractError):
            compute_case_metrics([[0.0, 0.0]], [[1.0, 0.0]], [0])
        with self.assertRaises(ContractError):
            compute_case_metrics([[1.0, math.inf]], [[1.0, 0.0]], [0])
        with self.assertRaises(ContractError):
            compute_case_metrics([[1.0, 0.0]], [[1.0, 0.0], [0.0, 1.0]], [0])
        with self.assertRaises(ContractError):
            compute_case_metrics([[1.0, 0.0]], [[1.0, 0.0]], [2])


def _comparison(case_id, split, cosine, minimum, agreement, delta, status="success"):
    record = {"caseID": case_id, "split": split, "status": status}
    if status == "success":
        record["metrics"] = {
            "meanCosine": cosine,
            "minimumCosine": minimum,
            "top1Agreement": agreement,
            "meanNLLDelta": delta,
        }
    return record


class AggregateTests(unittest.TestCase):
    def test_aggregates_are_case_level_macros_and_global_minimum(self):
        comparisons = []
        for index, case_id in enumerate(CONTRACT.tuning_ids):
            comparisons.append(
                _comparison(
                    case_id,
                    "tuning",
                    0.9 + index * 0.01,
                    0.4 + index * 0.01,
                    1.0,
                    index,
                )
            )
        for index, case_id in enumerate(CONTRACT.holdout_ids):
            comparisons.append(
                _comparison(case_id, "holdout", 0.8, 0.3 - index * 0.01, 0.5, -index)
            )
        result = aggregate_all(comparisons)
        tuning, holdout = result["splits"]
        self.assertAlmostEqual(
            tuning["meanCosine"], sum(0.9 + i * 0.01 for i in range(6)) / 6
        )
        self.assertEqual(tuning["minimumCosine"], 0.4)
        self.assertEqual(tuning["meanNLLDelta"], 2.5)
        self.assertEqual(holdout["minimumCosine"], 0.27)
        self.assertEqual(holdout["meanNLLDelta"], -1.5)

    def test_failed_case_prevents_partial_macro(self):
        comparisons = []
        for case_id in CONTRACT.tuning_ids:
            comparisons.append(_comparison(case_id, "tuning", 1.0, 1.0, 1.0, 0.0))
        comparisons[-1] = _comparison(
            CONTRACT.tuning_ids[-1], "tuning", 0, 0, 0, 0, "failed"
        )
        for case_id in CONTRACT.holdout_ids:
            comparisons.append(_comparison(case_id, "holdout", 1.0, 1.0, 1.0, 0.0))
        result = aggregate_all(comparisons)
        tuning = result["splits"][0]
        self.assertEqual(tuning["status"], "failed")
        self.assertNotIn("meanCosine", tuning)
        self.assertEqual(tuning["failedCaseIDs"], [CONTRACT.tuning_ids[-1]])


if __name__ == "__main__":
    unittest.main()
