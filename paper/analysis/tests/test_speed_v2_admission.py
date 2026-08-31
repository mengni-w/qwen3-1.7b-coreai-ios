import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import statistics
import tempfile
import unittest


PIPELINE_PATH = Path(__file__).resolve().parents[1] / "pipeline.py"
PIPELINE_SPEC = importlib.util.spec_from_file_location(
    "paper_analysis_pipeline_speed_v2",
    PIPELINE_PATH,
)
assert PIPELINE_SPEC is not None and PIPELINE_SPEC.loader is not None
pipeline = importlib.util.module_from_spec(PIPELINE_SPEC)
PIPELINE_SPEC.loader.exec_module(pipeline)
SOURCE_LOCK = json.loads(
    (Path(__file__).resolve().parents[1] / "source-lock.json").read_text(
        encoding="utf-8"
    )
)
EXPECTED = SOURCE_LOCK["speedV2Admission"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def summarized_values(values: list[dict], value_key: str = "value") -> dict:
    numbers = [item[value_key] for item in values]
    return {
        "count": len(values),
        "median": statistics.median(numbers),
        "q1": pipeline.linear_quantile(numbers, 0.25),
        "q3": pipeline.linear_quantile(numbers, 0.75),
        "min": min(numbers),
        "max": max(numbers),
        "values": values,
    }


def metric(values: list[dict]) -> dict:
    numbers = [item["value"] for item in values]
    return {
        "count": len(values),
        "median": statistics.median(numbers),
        "q1": pipeline.linear_quantile(numbers, 0.25),
        "q3": pipeline.linear_quantile(numbers, 0.75),
        "min": min(numbers),
        "max": max(numbers),
        "values": values,
    }


def block_metric(profile_blocks: list[int], base: float) -> dict:
    values = [
        {
            "physicalBlock": physical_block,
            "blockID": f"B{ordinal:02d}",
            "value": base + ordinal,
        }
        for ordinal, physical_block in enumerate(profile_blocks, start=1)
    ]
    return summarized_values(values)


def workload_metrics(
    profile_index: int,
    workload_index: int,
    workload: str,
    physical_blocks: list[int],
) -> dict[str, dict]:
    observations = {name: [] for name in pipeline.SPEED_V2_ALL_METRICS}
    for replicate, physical_block in enumerate(physical_blocks, start=1):
        for attempt in range(1, 6):
            sample_id = f"B{replicate:02d}-{workload}-A{attempt:02d}"
            ordinal = (replicate - 1) * 5 + attempt
            input_tokens = 120 + workload_index
            output_tokens = 20 + profile_index + workload_index
            token_ttft = 0.1 * profile_index + ordinal / 1000
            visible_ttft = token_ttft
            total = token_ttft + 1.0 + ordinal / 100
            visible_decode = (output_tokens - 1) / (total - visible_ttft)
            end_to_end = output_tokens / total
            values = {
                "inputTokens": input_tokens,
                "outputTokens": output_tokens,
                "visibleTokens": output_tokens,
                "firstOutputTokenCount": 1,
                "firstOutputReasoningTokenCount": 0,
                "firstVisibleTokenCount": 1,
                "tokenTTFTSeconds": token_ttft,
                "visibleTTFTSeconds": visible_ttft,
                "totalSeconds": total,
                "visibleDecodeTokensPerSecond": visible_decode,
                "endToEndVisibleTokensPerSecond": end_to_end,
                "responseCharacters": 30 + ordinal,
                "responseUTF8Bytes": 40 + ordinal,
                "memory.availableMiB": 3000.0 - ordinal,
                "memory.residentMiB": 1000.0 * profile_index + ordinal,
                "memory.peakResidentMiB": 1100.0 * profile_index + ordinal,
            }
            for metric_name, value in values.items():
                observations[metric_name].append(
                    {
                        "sampleID": sample_id,
                        "physicalBlock": physical_block,
                        "value": value,
                    }
                )
    return {name: metric(values) for name, values in observations.items()}


def speed_summary(run_id: str) -> dict:
    common = {
        **EXPECTED["commonIdentity"],
        "operatingSystem": "Version 27.0 (Build 24A5424a)",
    }
    profiles = {}
    identities = {}
    for profile_index, profile in enumerate(pipeline.SPEED_V2_PROFILES, start=1):
        physical_blocks = [
            block
            for block, owner in pipeline.SPEED_V2_BLOCK_SCHEDULE
            if owner == profile
        ]
        identities[profile] = copy.deepcopy(EXPECTED["profiles"][profile])
        workloads = {}
        for workload_index, workload in enumerate(
            pipeline.SPEED_V2_WORKLOADS,
            start=1,
        ):
            workloads[workload] = {
                "planned": 20,
                "completed": 20,
                "failed": 0,
                "capped": 0,
                "completionRate": 1.0,
                "metrics": workload_metrics(
                    profile_index,
                    workload_index,
                    workload,
                    physical_blocks,
                ),
            }
        disk_bytes = profile_index * 1024 * 1024
        profiles[profile] = {
            "blocks": [
                {
                    "physicalBlock": physical_block,
                    "blockID": f"B{ordinal:02d}",
                    "profileReplicate": ordinal,
                    "workloadOrder": "forward" if ordinal % 2 else "reverse",
                    "modelLoadSeconds": 1.0 + ordinal,
                    "estimatedDiskBytes": disk_bytes,
                    "memory": {},
                }
                for ordinal, physical_block in enumerate(physical_blocks, start=1)
            ],
            "blockMetrics": {
                "memory.afterUnload.peakResidentMiB": block_metric(
                    physical_blocks,
                    1000.0 * profile_index,
                )
            },
            "workloads": workloads,
        }
    paired = {}
    for workload in pipeline.SPEED_V2_WORKLOADS:
        paired_metrics = {}
        for metric_name in pipeline.SPEED_V2_ALL_METRICS:
            a_values = {
                item["sampleID"]: item["value"]
                for item in profiles["W8_ANE"]["workloads"][workload]["metrics"][
                    metric_name
                ]["values"]
            }
            b_values = {
                item["sampleID"]: item["value"]
                for item in profiles["INT4_GPU"]["workloads"][workload]["metrics"][
                    metric_name
                ]["values"]
            }
            pair_values = [
                {
                    "sampleID": sample_id,
                    "a": a_values[sample_id],
                    "b": b_values[sample_id],
                    "aMinusB": a_values[sample_id] - b_values[sample_id],
                }
                for sample_id in sorted(a_values)
            ]
            paired_metrics[metric_name] = summarized_values(
                pair_values,
                value_key="aMinusB",
            )
        paired[workload] = {
            "plannedPairs": 20,
            "successfulPairs": 20,
            "unpairedFailures": {
                "aFailedOnly": 0,
                "bFailedOnly": 0,
                "bothFailed": 0,
            },
            "metrics": paired_metrics,
        }
    return {
        "schemaVersion": 2,
        "analysis": pipeline.SPEED_V2_ANALYSIS,
        "runID": run_id,
        "conformance": {
            "status": "passed",
            "physicalBlocks": 8,
            "plannedSamples": 120,
            "pairedLogicalSamples": 60,
        },
        "identities": {"common": common, "profiles": identities},
        "profiles": profiles,
        "pairedAMinusB": {
            "a": "W8_ANE",
            "b": "INT4_GPU",
            "workloads": paired,
        },
    }


class PublicationBundle:
    def __init__(self, root: Path):
        self.root = root
        self.run_id = "speed-v2-prospective-fixture"
        self.summary = speed_summary(self.run_id)
        (root / "public").mkdir(parents=True)
        (root / "public/README.md").write_text("public fixture\n", encoding="utf-8")
        self.write_records()
        self.seal()

    def write_records(self) -> None:
        summary_path = self.root / "public/results/speed-v2-summary.json"
        write_json(summary_path, self.summary)
        host = {
            "schemaVersion": 4,
            "experiment": pipeline.SPEED_V2_ANALYSIS,
            "runID": self.run_id,
            "status": "pending-finalization",
            "preFinalizationOutcome": "eligible",
            "conformanceErrors": [],
            **EXPECTED["hostIdentity"],
            "toolchain": copy.deepcopy(EXPECTED["toolchain"]),
            "device": copy.deepcopy(EXPECTED["device"]),
            "blocks": [
                {"physicalBlock": block, "profile": profile}
                for block, profile in pipeline.SPEED_V2_BLOCK_SCHEDULE
            ],
            "analysis": {
                "exitStatus": 0,
                "status": "passed",
                "summary": "speed-v2-summary.json",
                "summaryPresent": True,
                "summarySHA256": sha256(summary_path),
            },
        }
        write_json(self.root / "public/host/host-run-record.json", host)

    def seal(self, *, status: str = "passed") -> None:
        index_path = self.root / "public/evidence-index.json"
        if index_path.exists():
            index_path.unlink()
        public_files = []
        for path in sorted((self.root / "public").rglob("*")):
            if path.is_file():
                public_files.append(
                    {
                        "path": path.relative_to(self.root).as_posix(),
                        "bytes": path.stat().st_size,
                        "sha256": sha256(path),
                        "visibility": "public",
                    }
                )
        public_index = {
            "schemaVersion": 1,
            "runID": self.run_id,
            "generatedAt": "2026-08-31T00:00:00Z",
            "selfExclusion": [
                "host/evidence-index-private.json",
                "public/evidence-index.json",
                "FINALIZED.json",
            ],
            "privateEvidenceIndex": {
                "path": "host/evidence-index-private.json",
                "bytes": 1,
                "sha256": "0" * 64,
            },
            "publicFiles": public_files,
        }
        write_json(index_path, public_index)
        host_entry = next(
            item
            for item in public_files
            if item["path"] == "public/host/host-run-record.json"
        )
        finalization = {
            "schemaVersion": 1,
            "runID": self.run_id,
            "status": status,
            "finalizedAt": "2026-08-31T00:00:01Z",
            "postIndexAcquisitionSeal": {"sealSHA256": "1" * 64},
            "privateEvidenceIndex": {
                "path": "host/evidence-index-private.json",
                "sha256": "0" * 64,
            },
            "publicEvidenceIndex": {
                "path": "public/evidence-index.json",
                "sha256": sha256(index_path),
            },
            "publicHostRecord": {
                key: host_entry[key] for key in ("path", "bytes", "sha256")
            },
        }
        write_json(self.root / "FINALIZED.json", finalization)


class SpeedV2AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name) / "publication"
        self.bundle = PublicationBundle(self.root)
        self.generated = Path(self.temporary.name) / "generated-review"
        self.generated.mkdir()
        self.expected = copy.deepcopy(EXPECTED)
        self.expected["acceptedBundle"] = None

    def tearDown(self):
        self.temporary.cleanup()

    def extract(self) -> dict:
        return pipeline.extract_speed_v2(self.root, self.generated, self.expected)

    def rewrite_summary(self) -> None:
        self.bundle.write_records()
        self.bundle.seal()

    @staticmethod
    def restat(metric_summary: dict, value_key: str = "value") -> None:
        replacement = summarized_values(metric_summary["values"], value_key=value_key)
        metric_summary.update(replacement)

    def test_complete_publication_bundle_is_admitted(self):
        result = self.extract()
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual(result["runID"], self.bundle.run_id)
        self.assertEqual(result["admission"]["physicalBlocks"], 8)
        self.assertEqual(result["admission"]["plannedSamples"], 120)
        self.assertFalse(result["admission"]["privateEvidenceRead"])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(
            result["storageAndMemory"]["compiledModelBundleMiB"],
            {"W8_ANE": 1.0, "INT4_GPU": 2.0},
        )

    def test_aborted_finalization_is_rejected(self):
        self.bundle.seal(status="aborted")
        with self.assertRaisesRegex(pipeline.PipelineError, "status is not passed"):
            self.extract()

    def test_nonconformant_host_is_rejected(self):
        host_path = self.root / "public/host/host-run-record.json"
        host = json.loads(host_path.read_text(encoding="utf-8"))
        host["preFinalizationOutcome"] = "nonconformant"
        host["conformanceErrors"] = ["fixture failure"]
        write_json(host_path, host)
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "not eligible"):
            self.extract()

    def test_incomplete_eight_block_schedule_is_rejected(self):
        host_path = self.root / "public/host/host-run-record.json"
        host = json.loads(host_path.read_text(encoding="utf-8"))
        host["blocks"].pop()
        write_json(host_path, host)
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "eight blocks"):
            self.extract()

    def test_failed_workload_cell_is_rejected(self):
        self.bundle.summary["profiles"]["W8_ANE"]["workloads"]["business_medium"].update(
            {"completed": 19, "failed": 1, "completionRate": 0.95}
        )
        self.bundle.write_records()
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "completion count"):
            self.extract()

    def test_private_acquisition_file_is_rejected(self):
        private = self.root / "host/device-details-private.json"
        write_json(private, {"secret": True})
        with self.assertRaisesRegex(pipeline.PipelineError, "only FINALIZED.json and public"):
            self.extract()

    def test_public_index_must_cover_file_added_after_sealing(self):
        (self.root / "public/unindexed.txt").write_text("late\n", encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "cover exactly every public"):
            self.extract()

    def test_private_local_path_inside_public_file_is_rejected(self):
        (self.root / "public/README.md").write_text(
            "captured at /Users/private/device.log\n",
            encoding="utf-8",
        )
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "private local path"):
            self.extract()

    def test_host_analyzer_summary_hash_must_match_public_summary(self):
        host_path = self.root / "public/host/host-run-record.json"
        host = json.loads(host_path.read_text(encoding="utf-8"))
        host["analysis"]["summarySHA256"] = "0" * 64
        write_json(host_path, host)
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "summary hash"):
            self.extract()

    def test_generic_tmp_path_inside_public_file_is_allowed(self):
        (self.root / "public/README.md").write_text(
            "build description at /tmp/speed-v2-example/build.xcbuilddata\n",
            encoding="utf-8",
        )
        self.bundle.seal()
        self.extract()

    def test_nonfinite_json_value_is_rejected(self):
        self.bundle.summary["profiles"]["W8_ANE"]["workloads"]["business_medium"][
            "metrics"
        ]["totalSeconds"]["median"] = float("nan")
        self.bundle.write_records()
        self.bundle.seal()
        with self.assertRaisesRegex(pipeline.PipelineError, "Non-finite JSON constant"):
            self.extract()

    def test_profile_sample_id_sets_must_match(self):
        cell = self.bundle.summary["profiles"]["W8_ANE"]["workloads"][
            "business_medium"
        ]["metrics"]
        for metric_name in pipeline.SPEED_V2_ALL_METRICS:
            for ordinal, observation in enumerate(cell[metric_name]["values"]):
                observation["sampleID"] = f"W8-only-{ordinal:02d}"
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "profile sample-ID sets differ"):
            self.extract()

    def test_metric_sample_id_sets_within_cell_must_match(self):
        metric_summary = self.bundle.summary["profiles"]["W8_ANE"]["workloads"][
            "business_medium"
        ]["metrics"]["totalSeconds"]
        metric_summary["values"][0]["sampleID"] = "different-logical-sample"
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "metric sample IDs differ"):
            self.extract()

    def test_paired_metric_set_must_be_complete(self):
        paired = self.bundle.summary["pairedAMinusB"]["workloads"][
            "business_medium"
        ]["metrics"]
        paired.pop("totalSeconds")
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "metric set changed"):
            self.extract()

    def test_paired_values_are_recomputed_from_profile_observations(self):
        metric_summary = self.bundle.summary["pairedAMinusB"]["workloads"][
            "business_medium"
        ]["metrics"]["totalSeconds"]
        metric_summary["values"][0]["aMinusB"] += 1.0
        self.restat(metric_summary, value_key="aMinusB")
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "aMinusB.*inconsistent"):
            self.extract()

    def test_impossible_timing_order_is_rejected(self):
        metric_summary = self.bundle.summary["profiles"]["W8_ANE"]["workloads"][
            "business_medium"
        ]["metrics"]["tokenTTFTSeconds"]
        for observation in metric_summary["values"]:
            observation["value"] = 100.0
        self.restat(metric_summary)
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "timing order is invalid"):
            self.extract()

    def test_throughput_must_match_token_and_time_definition(self):
        metric_summary = self.bundle.summary["profiles"]["W8_ANE"]["workloads"][
            "business_medium"
        ]["metrics"]["visibleDecodeTokensPerSecond"]
        for observation in metric_summary["values"]:
            observation["value"] = 999_999.0
        self.restat(metric_summary)
        self.rewrite_summary()
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            "visibleDecodeTokensPerSecond.*inconsistent",
        ):
            self.extract()

    def test_rss_observations_must_match_profile_block_schedule(self):
        metric_summary = self.bundle.summary["profiles"]["W8_ANE"]["blockMetrics"][
            "memory.afterUnload.peakResidentMiB"
        ]
        for observation in metric_summary["values"]:
            observation["physicalBlock"] = 999
            observation["blockID"] = "bogus"
        self.restat(metric_summary)
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "invalid physical block"):
            self.extract()

    def test_reported_median_must_match_public_values(self):
        metric_summary = self.bundle.summary["profiles"]["W8_ANE"]["workloads"][
            "business_medium"
        ]["metrics"]["totalSeconds"]
        metric_summary["median"] += 0.5
        self.rewrite_summary()
        with self.assertRaisesRegex(pipeline.PipelineError, "median does not match"):
            self.extract()

    def test_speed_figures_scale_from_observations_and_dynamic_rss(self):
        speed = self.extract()
        speed["workloads"]["business_medium"]["profiles"]["W8_ANE"]["metrics"][
            "tokenTTFTSeconds"
        ]["values"][0]["value"] = 1000.0
        speed["storageAndMemory"]["peakProcessResidentMiB"]["W8_ANE"] = 5000.0
        interval = {
            "lower95Points": -1.0,
            "upper95Points": 1.0,
            "observedPoints": 0.0,
        }
        quality = {
            "comparison": {
                "f1DifferenceFirstMinusSecond": interval,
                "emDifferenceFirstMinusSecond": interval,
                "f1WinSignTestPValue": 1.0,
                "emWinSignTestPValue": 1.0,
            }
        }
        pipeline.generate_figures(quality, speed, self.generated)

        f4 = (self.generated / "figures/f4-workload-latency.svg").read_text(
            encoding="utf-8"
        )
        circle_y = [float(value) for value in re.findall(r'<circle[^>]+cy="([^"]+)"', f4)]
        self.assertEqual(len(circle_y), 240)
        self.assertGreaterEqual(min(circle_y), 160.0)
        self.assertEqual(f4.count('class="grid"'), 10)

        f5 = (self.generated / "figures/f5-size-rss.svg").read_text(encoding="utf-8")
        bar_y = [
            float(value)
            for value in re.findall(r'<rect x="[^"]+" y="([^"]+)" width="76"', f5)
        ]
        self.assertEqual(len(bar_y), 4)
        self.assertGreaterEqual(min(bar_y), 105.0)
        self.assertEqual(f5.count('class="grid"'), 5)

    def test_accepted_bundle_hashes_and_repository_path_are_enforced(self):
        analysis_dir = pipeline.REPOSITORY_ROOT / "paper/analysis"
        with tempfile.TemporaryDirectory(dir=analysis_dir) as temporary:
            root = Path(temporary) / "publication"
            bundle = PublicationBundle(root)
            generated = Path(temporary) / "generated"
            generated.mkdir()
            host_path = root / "public/host/host-run-record.json"
            summary_path = root / "public/results/speed-v2-summary.json"
            accepted = {
                "relativePath": root.relative_to(pipeline.REPOSITORY_ROOT).as_posix(),
                "runID": bundle.run_id,
                "finalizationSHA256": sha256(root / "FINALIZED.json"),
                "publicEvidenceIndexSHA256": sha256(
                    root / "public/evidence-index.json"
                ),
                "publicHostRecordSHA256": sha256(host_path),
                "analyzerSummarySHA256": sha256(summary_path),
            }
            expected = copy.deepcopy(EXPECTED)
            expected["acceptedBundle"] = accepted
            result = pipeline.extract_speed_v2(root, generated, expected)
            self.assertEqual(result["runID"], bundle.run_id)

            expected["acceptedBundle"]["analyzerSummarySHA256"] = "0" * 64
            with self.assertRaisesRegex(
                pipeline.PipelineError,
                "analyzer-summary SHA-256 mismatch",
            ):
                pipeline.extract_speed_v2(root, generated, expected)


if __name__ == "__main__":
    unittest.main()
