from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluator.runtime import (  # noqa: E402
    NUMERIC_THREAD_ENVIRONMENT,
    _run_synthetic_authoring_smoke,
    repository_root,
)


HAS_AUTHORING_DEPENDENCIES = all(
    importlib.util.find_spec(name) is not None
    for name in ("coreai_models", "coreai_opt", "torch")
)


@unittest.skipUnless(
    HAS_AUTHORING_DEPENDENCIES,
    "Apple authoring dependencies are unavailable outside the frozen environment",
)
class AuthoringIntegrationTests(unittest.TestCase):
    def test_exact_recipe_runs_through_apple_parser_and_coreai_opt_prepare(self):
        os.environ["PYTHONHASHSEED"] = "0"
        os.environ.update(NUMERIC_THREAD_ENVIRONMENT)
        recipe = repository_root() / "recipes/qwen3_1_7b_w8_per_tensor.yaml"
        result = _run_synthetic_authoring_smoke(recipe)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["targetModules"], ["first", "second"])
        self.assertEqual(result["spawnDeterminism"]["observedSpawnProcessCount"], 2)
        self.assertTrue(
            result["spawnDeterminism"]["state"]["torchDeterministicAlgorithmsEnabled"]
        )


if __name__ == "__main__":
    unittest.main()
