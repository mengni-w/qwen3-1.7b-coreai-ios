import hashlib
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = ROOT.parent
FIDELITY_V2_SUMMARY = REPOSITORY_ROOT / "results/fidelity-v2-summary.json"
W8_COMPATIBILITY_EVIDENCE = (
    REPOSITORY_ROOT / "results/w8-aot-compatibility-evidence.json"
)
W8_COMPATIBILITY_EVENTS = (
    ROOT / "evidence" / "w8-compatibility" / "sanitized-load-events.jsonl"
)
W8_COMPATIBILITY_EVIDENCE_DIR = ROOT / "evidence" / "w8-compatibility"
W8_COMPATIBILITY_MANIFEST = W8_COMPATIBILITY_EVIDENCE_DIR / "MANIFEST.sha256"
SOURCE_LOCK = ROOT / "analysis/source-lock.json"
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
        self.assertEqual(
            verification["qualityInputValidation"],
            {
                "sampleIDsUnique": True,
                "resultIDsUnique": True,
                "resultIDSetsExact": True,
                "recordedErrors": 0,
                "maximumResponseTokenHits": 0,
                "inputTokenCountsPositive": True,
                "pairedInputTokenCountsEqual": True,
                "reportedCachedInputTokensNonzero": 0,
                "reasoningTokenCountsNonzero": 0,
                "stratumSampleSizes": {"short": 100, "medium": 100, "long": 100},
            },
        )

    def test_quality_headline_values(self):
        quality = load_json("quality-analysis-v2.json")
        self.assertAlmostEqual(quality["variants"]["W8_ANE"]["summary"]["em"], 59.3333333333)
        self.assertAlmostEqual(quality["variants"]["W8_ANE"]["summary"]["f1"], 81.7024397444)
        self.assertAlmostEqual(quality["variants"]["INT4_GPU"]["summary"]["em"], 57.6666666667)
        self.assertAlmostEqual(quality["variants"]["INT4_GPU"]["summary"]["f1"], 81.4220630420)
        self.assertEqual(quality["comparison"]["pairedSamples"], 300)
        self.assertEqual(quality["comparison"]["identicalPredictions"], 187)

    def test_fidelity_v2_is_the_canonical_t3_source(self):
        fidelity = load_json("tables/t3-w8-fidelity.json")
        source = json.loads(FIDELITY_V2_SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(fidelity["schemaVersion"], 2)
        self.assertEqual(fidelity["runID"], source["run_id"])
        self.assertEqual(
            fidelity["historicalQualitySummary"],
            {
                "path": "results/quality-summary.json",
                "retainedUse": "historical W4 and mixed-W4/W8 selection evidence only",
                "status": "superseded_for_reported_fidelity_metrics",
            },
        )
        self.assertEqual(
            fidelity["evaluations"]["w8_tuning"],
            source["evaluations"]["tuning"],
        )
        self.assertEqual(
            fidelity["evaluations"]["w8_frozen_holdout"],
            source["evaluations"]["holdout"],
        )
        provenance = load_json("provenance.json")
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
        self.assertEqual(provenance["localFileSHA256"], source_lock["localFiles"])
        for relative_path, expected_hash in source_lock["localFiles"].items():
            self.assertEqual(
                hashlib.sha256((REPOSITORY_ROOT / relative_path).read_bytes()).hexdigest(),
                expected_hash,
            )

    def test_w8_compatibility_table_preserves_load_only_boundaries(self):
        compatibility = load_json("tables/t8-w8-compatibility.json")
        old = compatibility["oldPublicArtifact"]
        current = compatibility["currentCandidate"]
        self.assertEqual(old["attempts"], 2)
        self.assertEqual(old["failureStage"], "ANECCompileOffline")
        self.assertTrue(
            old["afterFullRebootRequestAndReconnectAttemptIncluded"]
        )
        self.assertFalse(old["completedRebootDirectlyVerified"])
        self.assertEqual(old["producer"], "coreai-build-3600.75.3")
        self.assertEqual(current["attempts"], 1)
        self.assertEqual(current["producer"], "coreai-build-3600.83.1")
        self.assertAlmostEqual(current["loadSeconds"], 41.931619875)
        self.assertAlmostEqual(current["peakProcessResidentMiB"], 2737.046875)
        self.assertEqual(current["unloadStatus"], "completed")
        self.assertEqual(current["exitCode"], 0)
        self.assertEqual(
            compatibility["claimBoundary"],
            {
                "loadOnly": True,
                "generationPerformed": False,
                "instrumentsTracePerformed": False,
                "coldStartBenchmarkClaimed": False,
                "causeIsolated": False,
                "performanceComparisonClaimed": False,
            },
        )
        exports = compatibility["repeatedAuthoringExports"]
        self.assertFalse(exports["rawByteEquality"])
        self.assertNotEqual(
            exports["firstMainMLIRBSHA256"],
            exports["secondMainMLIRBSHA256"],
        )

    def test_w8_compatibility_sanitized_events_match_summary(self):
        summary = json.loads(W8_COMPATIBILITY_EVIDENCE.read_text(encoding="utf-8"))
        observation_ids = [
            observation["id"]
            for observation in summary["loadCompatibilityObservations"]
        ]
        self.assertEqual(len(observation_ids), len(set(observation_ids)))
        self.assertEqual(
            set(observation_ids),
            {
                "public-w8-old-producer-load-1",
                "public-w8-old-producer-load-2-after-reboot",
                "current-producer-w8-fresh-aot-load-1",
            },
        )
        records = {
            record["id"]: record
            for record in (
                json.loads(line)
                for line in W8_COMPATIBILITY_EVENTS.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            )
        }
        self.assertEqual(
            set(records),
            {
                "public-w8-old-producer-load-1",
                "full-reboot-request-and-reconnect-before-public-w8-load-2",
                "public-w8-old-producer-load-2-after-reboot",
                "current-producer-w8-fresh-aot-load-1",
            },
        )
        public = summary["sanitization"]["publicEventEvidence"]
        self.assertTrue(
            summary["sanitization"]["sanitizedEventEvidenceIncluded"]
        )
        self.assertFalse(
            summary["sanitization"]["unsanitizedOriginalCapturesIncluded"]
        )
        self.assertEqual(public["recordCount"], 4)
        self.assertEqual(
            public["sha256"],
            hashlib.sha256(W8_COMPATIBILITY_EVENTS.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            public["manifestPath"],
            "paper/evidence/w8-compatibility/MANIFEST.sha256",
        )
        self.assertEqual(
            public["manifestSHA256"],
            hashlib.sha256(W8_COMPATIBILITY_MANIFEST.read_bytes()).hexdigest(),
        )
        actual_evidence_files = {
            path.relative_to(W8_COMPATIBILITY_EVIDENCE_DIR).as_posix()
            for path in W8_COMPATIBILITY_EVIDENCE_DIR.rglob("*")
            if path.is_file() and path != W8_COMPATIBILITY_MANIFEST
        }
        self.assertEqual(
            actual_evidence_files,
            {"README.md", "sanitized-load-events.jsonl"},
        )
        manifest_entries = {}
        for line in W8_COMPATIBILITY_MANIFEST.read_text(encoding="utf-8").splitlines():
            expected_hash, relative = line.split("  ", 1)
            manifest_entries[relative] = expected_hash
        self.assertEqual(
            set(manifest_entries),
            {"README.md", "sanitized-load-events.jsonl"},
        )
        for relative, expected_hash in manifest_entries.items():
            self.assertEqual(
                hashlib.sha256(
                    (W8_COMPATIBILITY_EVIDENCE_DIR / relative).read_bytes()
                ).hexdigest(),
                expected_hash,
            )
        expected_environment = {
            "productType": "iPhone16,1",
            "reality": "physical",
            "operatingSystemVersion": "27.0",
            "operatingSystemBuild": "24A5424a",
        }
        for record_id in (
            "public-w8-old-producer-load-1",
            "public-w8-old-producer-load-2-after-reboot",
            "current-producer-w8-fresh-aot-load-1",
        ):
            self.assertEqual(records[record_id]["deviceRef"], "test-device-1")
            self.assertEqual(records[record_id]["environment"], expected_environment)
        transition = records[
            "full-reboot-request-and-reconnect-before-public-w8-load-2"
        ]
        self.assertEqual(transition["deviceRef"], "test-device-1")
        self.assertEqual(transition["request"]["hostOutcome"], "timeout")
        self.assertTrue(
            transition["subsequentObservation"]["lastConnectionChanged"]
        )
        self.assertTrue(
            transition["subsequentObservation"]["tunnelSessionChanged"]
        )
        self.assertFalse(
            transition["evidenceBoundary"]["completedRebootDirectlyVerified"]
        )
        candidate = records["current-producer-w8-fresh-aot-load-1"]
        self.assertFalse(candidate["protocol"]["timedPerformanceSample"])
        self.assertFalse(candidate["protocol"]["aneExecutionMeasured"])
        self.assertIn("source harness", candidate["sourceHarness"]["labelBoundary"])

    def test_quality_uses_stratified_paired_bootstrap(self):
        quality = load_json("quality-analysis-v2.json")
        self.assertEqual(
            quality["analysisProvenance"],
            {
                "status": "post-review reanalysis",
                "publishedScoringReproducedByteIdentically": True,
                "newModelOutputsCreated": False,
                "newDeviceMeasurementsCreated": False,
                "description": (
                    "Paired uncertainty was recomputed after manuscript review from the "
                    "unchanged published predictions and locked scorer."
                ),
            },
        )
        comparison = quality["comparison"]
        f1 = comparison["f1DifferenceFirstMinusSecond"]
        em = comparison["emDifferenceFirstMinusSecond"]
        self.assertEqual(
            f1["method"],
            "paired percentile bootstrap stratified by context-length band",
        )
        self.assertEqual(f1["stratumSampleSizes"], {"short": 100, "medium": 100, "long": 100})
        self.assertEqual(
            f1["quantileDefinition"],
            "Hyndman-Fan type 7 linear interpolation",
        )
        self.assertAlmostEqual(f1["lower95Points"], -2.4659375225371143)
        self.assertAlmostEqual(f1["upper95Points"], 2.956811987287845)
        self.assertAlmostEqual(em["lower95Points"], -3.0)
        self.assertAlmostEqual(em["upper95Points"], 6.333333333333333)
        self.assertTrue(comparison["signTest"]["tiesExcluded"])

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
            "tables/t8-w8-compatibility.json",
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
            if not path.is_file():
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
            if path.is_file() and path != manifest
        }
        self.assertEqual(listed, actual)


if __name__ == "__main__":
    unittest.main()
