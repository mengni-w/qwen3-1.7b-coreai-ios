import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PIPELINE_PATH = Path(__file__).resolve().parents[1] / "pipeline.py"
PIPELINE_SPEC = importlib.util.spec_from_file_location(
    "paper_analysis_pipeline",
    PIPELINE_PATH,
)
assert PIPELINE_SPEC is not None and PIPELINE_SPEC.loader is not None
pipeline = importlib.util.module_from_spec(PIPELINE_SPEC)
PIPELINE_SPEC.loader.exec_module(pipeline)


class QualityInputValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.sample_path = self.directory / "samples.json"
        self.w8_path = self.directory / "w8.jsonl"
        self.int4_path = self.directory / "int4.jsonl"

        self.samples = []
        for ordinal in range(300):
            stratum = ("short", "medium", "long")[ordinal // 100]
            self.samples.append(
                {
                    "id": f"sample-{ordinal:03d}",
                    "datasetRowIndex": ordinal,
                    "ordinal": ordinal,
                    "stratum": stratum,
                    "contextCharacterCount": 100 + ordinal,
                }
            )
        self.w8_records = [self.make_record(sample, "W8_ANE") for sample in self.samples]
        self.int4_records = [
            self.make_record(sample, "INT4_GPU") for sample in self.samples
        ]
        self.write_inputs()

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def make_record(sample: dict, variant: str) -> dict:
        return {
            "id": sample["id"],
            "variant": variant,
            "datasetRowIndex": sample["datasetRowIndex"],
            "ordinal": sample["ordinal"],
            "stratum": sample["stratum"],
            "contextCharacterCount": sample["contextCharacterCount"],
            "content": "answer",
            "inputTokens": 64,
            "cachedInputTokens": 0,
            "outputTokens": 4,
            "reasoningTokens": 0,
            "error": None,
        }

    @staticmethod
    def write_jsonl(path: Path, records: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )

    def write_inputs(self) -> None:
        self.sample_path.write_text(
            json.dumps({"samples": self.samples}),
            encoding="utf-8",
        )
        self.write_jsonl(self.w8_path, self.w8_records)
        self.write_jsonl(self.int4_path, self.int4_records)

    def validate(self):
        return pipeline.validate_quality_inputs(
            self.sample_path,
            {
                "W8_ANE": (self.w8_path, "W8_ANE"),
                "INT4_GPU": (self.int4_path, "INT4_GPU"),
            },
        )

    def assert_validation_fails(self, expected_message: str) -> None:
        self.write_inputs()
        with self.assertRaisesRegex(pipeline.PipelineError, expected_message):
            self.validate()

    def test_duplicate_result_id_is_rejected(self):
        self.w8_records.append(dict(self.w8_records[0]))
        self.assert_validation_fails(r"Duplicate result ID.*sample-000")

    def test_missing_result_id_is_rejected(self):
        self.w8_records.pop()
        self.assert_validation_fails(r"Result ID set mismatch.*sample-299")

    def test_extra_result_id_is_rejected(self):
        extra = dict(self.w8_records[-1])
        extra["id"] = "sample-extra"
        self.w8_records.append(extra)
        self.assert_validation_fails(r"Result ID set mismatch.*sample-extra")

    def test_variant_mismatch_is_rejected(self):
        self.w8_records[0]["variant"] = "INT4_GPU"
        self.assert_validation_fails(r"Variant mismatch.*sample-000")

    def test_recorded_generation_error_is_rejected(self):
        self.w8_records[0]["error"] = "generation failed"
        self.assert_validation_fails(r"Recorded generation error.*sample-000")

    def test_capped_output_is_rejected(self):
        self.w8_records[0]["outputTokens"] = 128
        self.assert_validation_fails(r"Invalid or capped output-token count.*sample-000")

    def test_cross_profile_input_token_mismatch_is_rejected(self):
        self.int4_records[0]["inputTokens"] = 65
        self.assert_validation_fails(r"Input-token mismatch across profiles.*sample-000")

    def test_missing_input_token_count_is_rejected(self):
        self.w8_records[0]["inputTokens"] = None
        self.assert_validation_fails(r"Invalid input-token count.*sample-000")

    def test_reasoning_output_is_rejected(self):
        self.w8_records[0]["reasoningTokens"] = 1
        self.assert_validation_fails(r"Unexpected reasoning output.*sample-000")

    def test_boolean_zero_token_counts_are_rejected(self):
        for field, message in (
            ("cachedInputTokens", r"Unexpected cached input.*sample-000"),
            ("reasoningTokens", r"Unexpected reasoning output.*sample-000"),
        ):
            with self.subTest(field=field):
                self.w8_records[0][field] = False
                self.assert_validation_fails(message)
                self.w8_records[0][field] = 0

    def test_frozen_stratum_size_change_is_rejected(self):
        self.samples[99]["stratum"] = "medium"
        self.w8_records[99]["stratum"] = "medium"
        self.int4_records[99]["stratum"] = "medium"
        self.assert_validation_fails(r"Frozen CMRC strata changed")


class StratifiedBootstrapValidationTests(unittest.TestCase):
    def test_reanalysis_is_explicitly_post_review(self):
        published = {
            "comparison": {
                "f1WinSignTestPValue": 0.5,
                "emWinSignTestPValue": 0.5,
            }
        }
        rows = [
            {
                "id": sample["id"],
                "f1": 1.0,
                "em": 1.0,
            }
            for sample in self._samples()
        ]
        scorer = {"score_variant": lambda samples, records: {"rows": rows}}
        with mock.patch.object(pipeline, "load_locked_scorer", return_value=scorer):
            analysis = pipeline.build_stratified_quality_analysis(
                Path("locked-scorer.py"),
                {"samples": self._samples()},
                {"W8_ANE": {}, "INT4_GPU": {}},
                published,
            )
        self.assertEqual(
            analysis["analysisProvenance"]["status"],
            "post-review reanalysis",
        )
        self.assertTrue(
            analysis["analysisProvenance"]["publishedScoringReproducedByteIdentically"]
        )

    @staticmethod
    def _samples() -> list[dict]:
        return [
            {
                "id": f"sample-{ordinal:03d}",
                "stratum": ("short", "medium", "long")[ordinal // 100],
            }
            for ordinal in range(300)
        ]

    def test_stratum_size_change_is_rejected(self):
        differences = {
            "short": [0.0] * 99,
            "medium": [0.0] * 100,
            "long": [0.0] * 100,
        }
        with self.assertRaisesRegex(
            pipeline.PipelineError,
            r"Paired bootstrap strata changed",
        ):
            pipeline.stratified_bootstrap_interval(differences, seed=20260828)

    def test_type_seven_quantile_interpolates(self):
        self.assertEqual(pipeline.linear_quantile([0.0, 10.0], 0.25), 2.5)


class PipelineOutputContractTests(unittest.TestCase):
    def test_run_tests_receives_exact_generated_directory(self):
        generated = Path("/tmp/analysis/generated-review").resolve()
        with mock.patch.object(pipeline.subprocess, "run") as run:
            pipeline.run_tests(generated)
        self.assertEqual(
            run.call_args.kwargs["env"]["ANALYSIS_GENERATED_DIR"],
            str(generated),
        )

    def test_manifest_covers_hidden_generated_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary)
            (generated / "visible.json").write_text("{}\n", encoding="utf-8")
            (generated / ".hidden.json").write_text("{}\n", encoding="utf-8")
            pipeline.write_generated_manifest(generated)
            pipeline.validate_generated_manifest(generated)
            manifest = (generated / "MANIFEST.sha256").read_text(encoding="utf-8")
            self.assertIn("  .hidden.json\n", manifest)

    def test_manifest_rejects_file_added_after_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary)
            (generated / "first.json").write_text("{}\n", encoding="utf-8")
            pipeline.write_generated_manifest(generated)
            (generated / ".unlisted.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(pipeline.PipelineError, "file-set mismatch"):
                pipeline.validate_generated_manifest(generated)


if __name__ == "__main__":
    unittest.main()
