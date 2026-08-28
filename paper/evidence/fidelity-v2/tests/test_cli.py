from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evaluator.cli import _sample_process_tree, launch_run  # noqa: E402
from evaluator.contract import ContractError  # noqa: E402


class CLIOrchestrationTests(unittest.TestCase):
    def test_failed_preflight_does_not_begin_or_claim_an_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "not-created"
            with (
                patch(
                    "evaluator.cli.prepare_preflight",
                    side_effect=ContractError("synthetic preflight rejection"),
                ),
                patch("evaluator.cli._claim_run_id") as claim,
            ):
                with self.assertRaises(ContractError):
                    launch_run(
                        run_id="00000000-0000-4000-8000-000000000000",
                        coreai_repo=Path(temporary) / "coreai",
                        model_dir=Path(temporary) / "model",
                        source_lock=Path(temporary) / "source-lock.json",
                        health_probe_dir=Path(temporary) / "health",
                        output_dir=output,
                    )
            claim.assert_not_called()
            self.assertFalse(output.exists())

    def test_process_tree_sampler_sums_unique_observed_resident_sets(self):
        class Process:
            def __init__(self, pid, resident_bytes, descendants=()):
                self.pid = pid
                self.resident_bytes = resident_bytes
                self.descendants = list(descendants)

            def children(self, recursive):
                self.assert_recursive = recursive
                return self.descendants

            def memory_info(self):
                return SimpleNamespace(rss=self.resident_bytes)

        grandchild = Process(3, 300)
        child = Process(2, 200, (grandchild,))
        root = Process(1, 100, (child, grandchild, child))
        self.assertEqual(_sample_process_tree(root), (600, 3))
        self.assertTrue(root.assert_recursive)

    def test_keyboard_interrupt_still_writes_process_result_and_manifest(self):
        class InterruptedChild:
            pid = 12345

            def __init__(self):
                self.poll_count = 0
                self.forwarded = []

            def poll(self):
                self.poll_count += 1
                if self.poll_count == 1:
                    raise KeyboardInterrupt
                return None

            def send_signal(self, signum):
                self.forwarded.append(signum)

            def terminate(self):
                raise AssertionError("graceful interrupt should not require SIGTERM")

            def kill(self):
                raise AssertionError("graceful interrupt should not require SIGKILL")

            def wait(self, timeout=None):
                del timeout
                return -2

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            claim = root / "claim.json"
            claim.write_text('{"runID":"synthetic"}\n', encoding="utf-8")
            health = root / "health"
            health.mkdir()
            output = root / "output"
            child = InterruptedChild()
            with (
                patch(
                    "evaluator.cli.prepare_preflight",
                    return_value=({}, None, [], 0),
                ),
                patch(
                    "evaluator.cli.verify_health_probe",
                    return_value={"status": "success"},
                ),
                patch("evaluator.cli._claim_run_id", return_value=claim),
                patch("evaluator.cli.repository_root", return_value=root),
                patch("evaluator.cli.subprocess.Popen", return_value=child),
                patch("evaluator.cli._sample_process_tree", return_value=(1024, 2)),
                patch("psutil.Process", return_value=object()),
            ):
                status = launch_run(
                    run_id="00000000-0000-4000-8000-000000000000",
                    coreai_repo=root / "coreai",
                    model_dir=root / "model",
                    source_lock=root / "source-lock.json",
                    health_probe_dir=health,
                    output_dir=output,
                )
            self.assertEqual(status, 130)
            process_result = json.loads((output / "process-result.json").read_text())
            self.assertTrue(process_result["orchestratorInterrupted"])
            self.assertEqual(process_result["terminationActions"], ["SIGINT"])
            self.assertEqual(process_result["exitCode"], -2)
            self.assertTrue((output / "MANIFEST.sha256").is_file())
            self.assertTrue((output / "run-id-claim.json").is_file())


if __name__ == "__main__":
    unittest.main()
