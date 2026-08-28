import hashlib
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
GENERATED = Path(
    os.environ.get("ANALYSIS_GENERATED_DIR", ROOT / "analysis/generated")
).resolve()


def load_json(relative_path: str) -> dict:
    return json.loads((GENERATED / relative_path).read_text(encoding="utf-8"))


class GeneratedEvidenceTests(unittest.TestCase):
    def test_quality_is_byte_identical_to_published_result(self):
        verification = load_json("quality-verification.json")
        self.assertTrue(verification["byteIdenticalToPublished"])
        self.assertEqual(
            verification["publishedQualitySHA256"],
            "47bae909fdac3e80996b4042daff173931dec306c6f8a9977189792f4effa171",
        )
        self.assertEqual(
            verification["recomputedQualitySHA256"],
            verification["publishedQualitySHA256"],
        )
        self.assertEqual(
            verification["dataset"]["frozenSampleSHA256"],
            "9fb9d896c96fc2ef0fa9961a5b65d2ac5b8bd09744f717a0a0ecb9f6c9fe05ff",
        )

    def test_quality_headline_values(self):
        quality = load_json("quality-recomputed.json")
        self.assertAlmostEqual(quality["variants"]["W8_ANE"]["summary"]["em"], 59.3333333333)
        self.assertAlmostEqual(quality["variants"]["W8_ANE"]["summary"]["f1"], 81.7024397444)
        self.assertAlmostEqual(quality["variants"]["INT4_GPU"]["summary"]["em"], 57.6666666667)
        self.assertAlmostEqual(quality["variants"]["INT4_GPU"]["summary"]["f1"], 81.4220630420)
        self.assertEqual(quality["comparison"]["pairedSamples"], 300)
        self.assertEqual(quality["comparison"]["identicalPredictions"], 187)

    def test_speed_samples_and_medians(self):
        speed = load_json("speed-normalized.json")
        expected = {
            "business_161_60": {
                "W8_ANE": (0.431, 3.259),
                "INT4_GPU": (1.221, 2.592),
            },
            "near_4k_3790_10": {
                "W8_ANE": (5.647, 6.116),
                "INT4_GPU": (13.522, 13.717),
            },
            "decode_120_256": {
                "W8_ANE": (0.404, 13.292),
                "INT4_GPU": (0.559, 7.159),
            },
        }
        for workload_id, variants in expected.items():
            workload = speed["workloads"][workload_id]
            self.assertEqual(len(workload["acceptedSamples"]), 6)
            for variant, (ttft, total) in variants.items():
                self.assertEqual(workload["medians"][variant]["ttftSeconds"], ttft)
                self.assertEqual(workload["medians"][variant]["totalSeconds"], total)

    def test_all_planned_machine_readable_tables_exist(self):
        expected = [
            "tables/t1-public-status.json",
            "tables/t2-profile-definitions.json",
            "tables/t3-w8-fidelity.json",
            "tables/t4-w8-device-evidence.json",
            "tables/t5-paired-quality.json",
            "tables/t6-size-rss.json",
            "tables/t7-workload-performance.json",
        ]
        for relative_path in expected:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((GENERATED / relative_path).is_file())

    def test_public_status_is_date_stamped_and_bounded(self):
        status = load_json("tables/t1-public-status.json")
        self.assertEqual(status["auditedAt"], "2026-08-28T09:07:26Z")
        self.assertEqual(
            status["officialApple"]["mainCommit"],
            "7062017c8e86c6cf4f49b721ddc3494efcdb7c7d",
        )
        self.assertFalse(status["officialApple"]["qwen3_1_7bRegistered"])
        self.assertEqual(status["officialApple"]["issue116"]["state"], "open")
        self.assertFalse(status["officialApple"]["pullRequest196"]["merged"])

    def test_result_figures_are_svg(self):
        for name in (
            "f3-paired-quality.svg",
            "f4-workload-latency.svg",
            "f5-size-rss.svg",
        ):
            with self.subTest(name=name):
                text = (GENERATED / "figures" / name).read_text(encoding="utf-8")
                self.assertTrue(text.startswith("<svg "))
                self.assertTrue(text.endswith("</svg>\n"))

    def test_generated_outputs_do_not_redistribute_dataset_text(self):
        forbidden = ('"question":', '"answers":', '"context":')
        admitted_text_suffixes = {".json", ".csv", ".svg", ".sha256"}
        for path in GENERATED.rglob("*"):
            relative = path.relative_to(GENERATED)
            if not path.is_file() or any(part.startswith(".") for part in relative.parts):
                continue
            self.assertIn(
                path.suffix,
                admitted_text_suffixes,
                f"unexpected generated file type: {relative}",
            )
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=relative.as_posix(), marker=marker):
                    self.assertNotIn(marker, text)

    def test_manifest_matches_every_generated_file(self):
        manifest = GENERATED / "MANIFEST.sha256"
        listed = set()
        for line in manifest.read_text(encoding="utf-8").splitlines():
            expected, relative_path = line.split("  ", 1)
            self.assertNotIn(relative_path, listed)
            listed.add(relative_path)
            digest = hashlib.sha256((GENERATED / relative_path).read_bytes()).hexdigest()
            self.assertEqual(digest, expected)
        actual = {
            path.relative_to(GENERATED).as_posix()
            for path in GENERATED.rglob("*")
            if path.is_file()
            and path != manifest
            and not any(
                part.startswith(".")
                for part in path.relative_to(GENERATED).parts
            )
        }
        self.assertEqual(listed, actual)


if __name__ == "__main__":
    unittest.main()
