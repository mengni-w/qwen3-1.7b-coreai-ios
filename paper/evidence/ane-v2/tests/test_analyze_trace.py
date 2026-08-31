from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


analyzer = load_module("ane_v2_analyze_trace", ROOT / "analyze_trace.py")
canonicalizer = load_module("ane_v2_canonicalize_xctrace", ROOT / "canonicalize_xctrace.py")
exporter = load_module("ane_v2_export_trace", ROOT / "export_trace.py")
extractor = load_module("ane_v2_extract_app_records", ROOT / "extract_app_records.py")
identity_preparer = load_module("ane_v2_prepare_identity", ROOT / "prepare_identity.py")
sealer = load_module("ane_v2_seal_run_metadata", ROOT / "seal_run_metadata.py")
publication = load_module("ane_v2_validate_public_bundle", ROOT / "validate_public_bundle.py")


def read(name: str):
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def fixture_sha256(name: str) -> str:
    return hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest()


def signpost_mapping():
    return {
        "schema": "ane-v2-xctrace-column-map-v1",
        "table_role": "signposts",
        "row_xpath": ".//row",
        "columns": {
            "row_id": {"row_index": True},
            "subsystem": {"index": 0},
            "category": {"index": 1},
            "name": {"index": 2},
            "run_uuid": {"index": 3},
            "pid": {"index": 4, "type": "integer"},
            "start_ns": {"index": 5, "type": "nanoseconds", "unit": "s"},
            "duration_ns": {"index": 6, "type": "nanoseconds", "unit": "us"},
            "terminal_state": {"index": 7},
        },
    }


def interval_mapping(role: str):
    return {
        "schema": "ane-v2-xctrace-column-map-v1",
        "table_role": role,
        "row_xpath": ".//row",
        "native_identifier_name": "program-id",
        "columns": {
            "row_id": {"row_index": True},
            "start_ns": {"index": 0, "type": "nanoseconds", "unit": "ns"},
            "duration_ns": {"index": 1, "type": "nanoseconds", "unit": "ns"},
            "program_label": {"index": 2},
            "channel": {"index": 3},
            "state": {"index": 4},
            "process": {"index": 5},
            "pid": {"index": 6, "type": "integer"},
            "native_identifier": {
                "index": 7,
                "type": "nullable_string",
                "null_values": [""],
            },
        },
    }


def create_bound_source_repository(root: Path) -> dict:
    repo = root / "source-repo"
    required_files = sorted(
        analyzer.REQUIRED_SOURCE_PATHS
        | {
            analyzer.PROJECT_RELATIVE_PATH,
            analyzer.PACKAGE_RESOLVED_RELATIVE_PATH,
            analyzer.PROTOCOL_RELATIVE_PATH,
            identity_preparer.ARTIFACT_AMENDMENT_RELATIVE_PATH,
            identity_preparer.AMENDMENT_RELATIVE_PATH,
            identity_preparer.RUNTIME_PATCH_RELATIVE_PATH,
        }
    )
    for relative in required_files:
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if relative == analyzer.PACKAGE_RESOLVED_RELATIVE_PATH:
            path.write_text(
                json.dumps(
                    {
                        "pins": [
                            {
                                "identity": "coreai-models",
                                "state": {"revision": analyzer.COREAI_SOURCE_REVISION},
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        elif relative == analyzer.PROJECT_RELATIVE_PATH:
            path.write_text(
                f'repositoryURL = "{identity_preparer.COREAI_REPOSITORY}";\n',
                encoding="utf-8",
            )
        elif relative == identity_preparer.RUNTIME_PATCH_RELATIVE_PATH:
            path.write_bytes((REPOSITORY_ROOT / relative).read_bytes())
        else:
            path.write_text(f"fixture bytes for {relative}\n", encoding="utf-8")
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "fixture@example.invalid"],
        ["git", "config", "user.name", "Fixture"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "fixture source"],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    return {"repo": repo, "source": identity_preparer.git_identity(repo)}


def create_patched_runtime_checkout(root: Path) -> dict:
    source_repo = root / "identity-source"
    checkout = root / "runtime-checkout"
    source_repo.mkdir()
    checkout.mkdir()
    paths = ("Sources/One.swift", "Sources/Two.swift")
    base_bytes = {
        paths[0]: b"let one = 1\n",
        paths[1]: b"let two = 2\n",
        "Sources/Three.swift": b"let three = 3\n",
    }
    patched_bytes = {
        paths[0]: b"let one = 10\n",
        paths[1]: b"let two = 20\n",
    }
    for relative, contents in base_bytes.items():
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "fixture@example.invalid"],
        ["git", "config", "user.name", "Fixture"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "runtime base"],
    ):
        subprocess.run(command, cwd=checkout, check=True, capture_output=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    for relative, contents in patched_bytes.items():
        (checkout / relative).write_bytes(contents)
    patch_bytes = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--", *paths],
        cwd=checkout,
        check=True,
        capture_output=True,
    ).stdout
    patch_relative_path = "runtime.patch"
    (source_repo / patch_relative_path).write_bytes(patch_bytes)
    patched_files = tuple(
        {
            "path": relative,
            "base_sha256": hashlib.sha256(base_bytes[relative]).hexdigest(),
            "patched_sha256": hashlib.sha256(patched_bytes[relative]).hexdigest(),
        }
        for relative in paths
    )
    return {
        "source_repo": source_repo,
        "checkout": checkout,
        "head": head,
        "patch_relative_path": patch_relative_path,
        "patch_sha256": hashlib.sha256(patch_bytes).hexdigest(),
        "patched_files": patched_files,
        "base_bytes": base_bytes,
        "patched_bytes": patched_bytes,
    }


def prepare_fixture_runtime_identity(runtime: dict) -> dict:
    with (
        mock.patch.object(identity_preparer, "COREAI_SOURCE_REVISION", runtime["head"]),
        mock.patch.object(
            identity_preparer,
            "RUNTIME_PATCH_RELATIVE_PATH",
            runtime["patch_relative_path"],
        ),
        mock.patch.object(
            identity_preparer,
            "RUNTIME_PATCH_SHA256",
            runtime["patch_sha256"],
        ),
        mock.patch.object(
            identity_preparer,
            "PATCHED_RUNTIME_FILES",
            runtime["patched_files"],
        ),
    ):
        return identity_preparer.runtime_identity(
            runtime["source_repo"], runtime["checkout"]
        )


def valid_inputs():
    return {
        "signposts": read("signposts.json"),
        "mpsgraph": read("mpsgraph.json"),
        "ane": read("ane.json"),
        "identity": read("identity.json"),
        "run_metadata": read("run-metadata.json"),
        "capture_command": read("capture-command.json"),
        "export_command": read("export-command.json"),
        "app_records": read("app-records.json"),
        "input_hashes": {
            "signposts": fixture_sha256("signposts.json"),
            "mpsgraph": fixture_sha256("mpsgraph.json"),
            "ane": fixture_sha256("ane.json"),
            "identity_record": fixture_sha256("identity.json"),
            "run_metadata": fixture_sha256("run-metadata.json"),
            "capture_command": fixture_sha256("capture-command.json"),
            "export_command": fixture_sha256("export-command.json"),
            "app_records": fixture_sha256("app-records.json"),
        },
    }


class AnalyzeTraceTests(unittest.TestCase):
    def test_identity_requires_runtime_patch_binding_v4(self):
        mutations = (
            ("schema", "public-w8-trace-identity-v3"),
            ("repository", "https://example.invalid/coreai-models.git"),
            ("base_revision", "f" * 40),
            ("patch_file", "paper/evidence/ane-v2/other.patch"),
            ("patch_sha256", "f" * 64),
        )
        for field, replacement in mutations:
            identity = read("identity.json")
            if field == "schema":
                identity[field] = replacement
            else:
                identity["runtime"][field] = replacement
            with self.subTest(field=field), self.assertRaises(analyzer.ValidationError):
                analyzer.validate_identity(identity)

    def test_identity_requires_exact_patched_runtime_file_manifest(self):
        identity = read("identity.json")
        identity["runtime"]["patched_files"].pop()
        with self.assertRaises(analyzer.ValidationError):
            analyzer.validate_identity(identity)

        identity = read("identity.json")
        identity["runtime"]["patched_files"].append(
            {
                "path": "swift/Sources/CoreAILanguageModels/Unexpected.swift",
                "base_sha256": "a" * 64,
                "patched_sha256": "b" * 64,
            }
        )
        with self.assertRaises(analyzer.ValidationError):
            analyzer.validate_identity(identity)

    def test_identity_requires_exact_runtime_file_digests(self):
        for index in range(2):
            for field in ("base_sha256", "patched_sha256"):
                identity = read("identity.json")
                identity["runtime"]["patched_files"][index][field] = "f" * 64
                with self.subTest(index=index, field=field), self.assertRaises(
                    analyzer.ValidationError
                ):
                    analyzer.validate_identity(identity)

    def test_identity_source_manifest_binds_the_runtime_patch_bytes(self):
        identity = read("identity.json")
        patch_record = next(
            record
            for record in identity["source"]["source_files"]
            if record["path"] == identity["runtime"]["patch_file"]
        )
        patch_record["sha256"] = "f" * 64
        with self.assertRaises(analyzer.ValidationError):
            analyzer.validate_identity(identity)

    def test_identity_reconstructs_the_frozen_artifact_manifest(self):
        identity = read("identity.json")
        identity["artifact"]["payloads"][-1]["size_bytes"] += 1
        with self.assertRaisesRegex(
            analyzer.ValidationError, "do not reconstruct the frozen benchmark manifest"
        ):
            analyzer.validate_identity(identity)

    def test_identity_rejects_extra_file_and_symbolic_link_payloads(self):
        for kind in ("file", "symlink"):
            identity = read("identity.json")
            identity["artifact"]["payloads"].append(
                {
                    "path": f"unexpected-{kind}",
                    "kind": kind,
                    "size_bytes": 1,
                    "sha256": "a" * 64,
                }
            )
            with self.subTest(kind=kind), self.assertRaises(analyzer.ValidationError):
                analyzer.validate_identity(identity)

    def test_identity_rejects_a_changed_published_sha256s_list(self):
        identity = read("identity.json")
        identity["artifact"]["published_sha256s"].pop()
        with self.assertRaisesRegex(
            analyzer.ValidationError, "published SHA256SUMS must contain"
        ):
            analyzer.validate_identity(identity)

    def test_native_identifier_exact_multiset_join(self):
        result = analyzer.analyze(**valid_inputs())
        self.assertEqual(result["schema"], "public-w8-ane-trace-analysis-v3")
        self.assertEqual(
            result["identity_summary"]["runtime_patch_sha256"],
            identity_preparer.RUNTIME_PATCH_SHA256,
        )
        self.assertEqual(
            result["identity_summary"]["patched_runtime_files"],
            read("identity.json")["runtime"]["patched_files"],
        )
        self.assertEqual(result["selected_key_mode"], "native_identifier_relative_start_duration")
        self.assertEqual(
            result["counts"],
            {
                "mpsgraph_exported": 5,
                "ane_exported": 4,
                "mpsgraph_eligible": 3,
                "ane_eligible": 3,
                "matched": 2,
                "unmatched_mpsgraph": 1,
                "unmatched_ane": 1,
                "excluded_mpsgraph": 2,
                "excluded_ane": 1,
            },
        )
        self.assertEqual(result["permitted_conclusion"], analyzer.PERMITTED_CONCLUSION)
        self.assertEqual(len(result["duplicate_multiplicities"]), 1)
        duplicate = result["duplicate_multiplicities"][0]
        self.assertEqual((duplicate["mpsgraph"], duplicate["ane"], duplicate["matched"]), (2, 2, 2))
        self.assertEqual(
            result["exclusion_reason_counts"],
            {
                "mpsgraph": {"starts_before_run_begin": 1, "wrong_pid": 1},
                "ane": {"ends_after_run_end": 1},
            },
        )
        self.assertNotIn("excluded_mpsgraph_rows", result)
        self.assertNotIn("excluded_ane_rows", result)

    def test_one_nanosecond_difference_is_not_fuzzy_matched(self):
        values = valid_inputs()
        for row in values["ane"]["rows"][:2]:
            row["start_ns"] += 1
        result = analyzer.analyze(**values)
        self.assertEqual(result["counts"]["matched"], 0)
        self.assertIsNone(result["permitted_conclusion"])

    def test_different_native_identifier_names_force_fallback(self):
        values = valid_inputs()
        values["ane"]["native_identifier_name"] = "prediction-id"
        result = analyzer.analyze(**values)
        self.assertEqual(result["selected_key_mode"], "relative_start_duration_fallback")
        self.assertEqual(result["counts"]["matched"], 2)

    def test_missing_native_identifier_forces_fallback(self):
        values = valid_inputs()
        values["ane"]["rows"][0]["native_identifier"] = None
        result = analyzer.analyze(**values)
        self.assertEqual(result["selected_key_mode"], "relative_start_duration_fallback")

    def test_native_identifier_json_types_do_not_compare_equal(self):
        values = valid_inputs()
        values["mpsgraph"]["rows"][0]["native_identifier"] = 7
        values["mpsgraph"]["rows"][1]["native_identifier"] = 7
        result = analyzer.analyze(**values)
        self.assertEqual(result["selected_key_mode"], "native_identifier_relative_start_duration")
        self.assertEqual(result["counts"]["matched"], 0)

    def test_measured_session_readiness_record_is_required(self):
        values = valid_inputs()
        values["app_records"]["records"] = [
            record
            for record in values["app_records"]["records"]
            if record["event"] != "measured_session_ready"
        ]
        with self.assertRaisesRegex(analyzer.ValidationError, "measured_session_ready"):
            analyzer.analyze(**values)

    def test_prerequisite_timestamps_must_precede_the_measured_request(self):
        values = valid_inputs()
        measured_session = next(
            record
            for record in values["app_records"]["records"]
            if record["event"] == "measured_session_ready"
        )
        measured_session["wall_clock_utc"] = "2026-08-28T12:00:41.000Z"
        with self.assertRaisesRegex(analyzer.ValidationError, "timestamps are out of order"):
            analyzer.analyze(**values)

    def test_equal_counts_do_not_substitute_for_exact_matches(self):
        values = valid_inputs()
        values["mpsgraph"]["rows"] = values["mpsgraph"]["rows"][:1]
        values["ane"]["rows"] = values["ane"]["rows"][2:3]
        result = analyzer.analyze(**values)
        self.assertEqual(result["counts"]["mpsgraph_eligible"], 1)
        self.assertEqual(result["counts"]["ane_eligible"], 1)
        self.assertEqual(result["counts"]["matched"], 0)

    def test_a_second_frozen_signpost_is_rejected(self):
        values = valid_inputs()
        second = copy.deepcopy(values["signposts"]["rows"][0])
        second["row_id"] = "sp-2"
        second["run_uuid"] = "22222222-2222-4222-8222-222222222222"
        values["signposts"]["rows"].append(second)
        with self.assertRaisesRegex(analyzer.ValidationError, "exactly one frozen signpost"):
            analyzer.analyze(**values)

    def test_signpost_pid_mismatch_is_rejected(self):
        values = valid_inputs()
        values["signposts"]["rows"][0]["pid"] = 99
        with self.assertRaisesRegex(analyzer.ValidationError, "signpost PID mismatch"):
            analyzer.analyze(**values)

    def test_identity_hash_mismatch_is_rejected(self):
        values = valid_inputs()
        values["run_metadata"]["identity_record_sha256"] = "f" * 64
        with self.assertRaisesRegex(analyzer.ValidationError, "does not identify"):
            analyzer.analyze(**values)

    def test_public_identity_rejects_private_signing_fields(self):
        values = valid_inputs()
        values["identity"]["app"]["code_signing"]["team_identifier"] = "PRIVATE"
        with self.assertRaisesRegex(analyzer.ValidationError, "public allowlist"):
            analyzer.analyze(**values)

    def test_app_record_rejects_free_form_error_or_unknown_fields(self):
        values = valid_inputs()
        terminal = next(
            record for record in values["app_records"]["records"]
            if record["event"] == "measured_request_end"
        )
        terminal["error"] = "private framework error"
        with self.assertRaisesRegex(analyzer.ValidationError, "public allowlist"):
            analyzer.analyze(**values)

    def test_app_record_rejects_string_smuggled_into_numeric_field(self):
        values = valid_inputs()
        smoke = next(
            record
            for record in values["app_records"]["records"]
            if record["event"] == "smoke_complete"
        )
        smoke["cached_input_tokens"] = "raw framework error"
        with self.assertRaisesRegex(analyzer.ValidationError, "must be an integer"):
            analyzer.analyze(**values)

    def test_app_record_rejects_nonfinite_or_inconsistent_time(self):
        values = valid_inputs()
        smoke = next(
            record
            for record in values["app_records"]["records"]
            if record["event"] == "smoke_complete"
        )
        smoke["time_to_first_token_seconds"] = 0.3
        smoke["total_seconds"] = 0.2
        with self.assertRaisesRegex(analyzer.ValidationError, "exceeds total"):
            analyzer.analyze(**values)

    def test_private_public_binding_is_required(self):
        values = valid_inputs()
        values["run_metadata"]["identity_binding_verified"] = False
        with self.assertRaisesRegex(analyzer.ValidationError, "binding"):
            analyzer.analyze(**values)

    def test_capture_record_rejects_real_paths(self):
        values = valid_inputs()
        values["capture_command"]["argv"][4] = "/private/template.tracetemplate"
        with self.assertRaisesRegex(analyzer.ValidationError, "real filesystem path"):
            analyzer.analyze(**values)

    def test_duplicate_source_row_id_is_rejected(self):
        values = valid_inputs()
        values["mpsgraph"]["rows"][1]["row_id"] = "m1"
        with self.assertRaisesRegex(analyzer.ValidationError, "duplicate mpsgraph_program row_id"):
            analyzer.analyze(**values)

    def test_public_interval_table_rejects_other_process_rows(self):
        values = valid_inputs()
        values["mpsgraph"]["rows"][0]["pid"] = 99
        with self.assertRaisesRegex(analyzer.ValidationError, "target PID"):
            analyzer.analyze(**values)

    def test_capture_record_must_attach_the_owned_pid(self):
        values = valid_inputs()
        values["capture_command"]["attached_pid"] = 99
        with self.assertRaisesRegex(analyzer.ValidationError, "different PID"):
            analyzer.analyze(**values)

    def test_capture_toolchain_must_match_the_sealed_identity(self):
        values = valid_inputs()
        values["capture_command"]["xcode_build"] = "different-build"
        with self.assertRaisesRegex(analyzer.ValidationError, "sealed toolchain"):
            analyzer.analyze(**values)

    def test_canonical_table_must_identify_raw_export(self):
        values = valid_inputs()
        values["export_command"]["exports"]["ane"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(analyzer.ValidationError, "raw export"):
            analyzer.analyze(**values)

    def test_metadata_must_identify_retained_odie_profile_export(self):
        values = valid_inputs()
        values["run_metadata"]["odie_profile_export_sha256"] = "f" * 64
        with self.assertRaisesRegex(analyzer.ValidationError, "ODIEProfile export"):
            analyzer.analyze(**values)

    def test_export_toolchain_must_match_the_sealed_identity(self):
        values = valid_inputs()
        values["export_command"]["instruments_build"] = "different-build"
        with self.assertRaisesRegex(analyzer.ValidationError, "sealed toolchain"):
            analyzer.analyze(**values)

    def test_app_terminal_record_must_match_metadata(self):
        values = valid_inputs()
        terminal = next(
            record
            for record in values["app_records"]["records"]
            if record["event"] == "measured_request_end"
        )
        terminal["emitted_tokens"] = 9
        with self.assertRaisesRegex(analyzer.ValidationError, "terminal record differs"):
            analyzer.analyze(**values)

    def test_installed_executable_must_match_the_sealed_release_app(self):
        values = valid_inputs()
        prerequisite = next(
            record
            for record in values["app_records"]["records"]
            if record["event"] == "prerequisites_begin"
        )
        prerequisite["app_executable_sha256"] = "f" * 64
        with self.assertRaisesRegex(analyzer.ValidationError, "installed app executable"):
            analyzer.analyze(**values)

    def test_output_is_byte_deterministic(self):
        first = analyzer.canonical_json_bytes(analyzer.analyze(**valid_inputs()))
        second = analyzer.canonical_json_bytes(analyzer.analyze(**valid_inputs()))
        self.assertEqual(first, second)
        self.assertEqual(hashlib.sha256(first).hexdigest(), hashlib.sha256(second).hexdigest())


class CanonicalizeXctraceTests(unittest.TestCase):
    def signpost_mapping(self):
        return signpost_mapping()

    def test_exact_decimal_unit_conversion(self):
        xml = """<root><row><v>io.massif.qwen3.coreai.trace-confirmation</v><v>inference</v><v>PUBLIC_W8_TRACE_CONFIRMATION_V1</v><v>11111111-1111-4111-8111-111111111111</v><v>42</v><v>1.000000001</v><v>2.5</v><v>completed</v></row></root>"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "signpost.xml"
            path.write_text(xml, encoding="utf-8")
            result = canonicalizer.canonicalize(path, self.signpost_mapping())
        self.assertEqual(result["rows"][0]["start_ns"], 1_000_000_001)
        self.assertEqual(result["rows"][0]["duration_ns"], 2_500)

    def test_subnanosecond_value_is_rejected(self):
        xml = """<root><row><v>io.massif.qwen3.coreai.trace-confirmation</v><v>inference</v><v>PUBLIC_W8_TRACE_CONFIRMATION_V1</v><v>11111111-1111-4111-8111-111111111111</v><v>42</v><v>1.0000000001</v><v>2.5</v><v>completed</v></row></root>"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "signpost.xml"
            path.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(canonicalizer.MappingError, "not exactly representable"):
                canonicalizer.canonicalize(path, self.signpost_mapping())

    def test_xctrace_reference_elements_are_resolved(self):
        xml = """<root><definitions><v id="start">1.000000001</v><v id="duration">2.5</v></definitions><row><v>io.massif.qwen3.coreai.trace-confirmation</v><v>inference</v><v>PUBLIC_W8_TRACE_CONFIRMATION_V1</v><v>11111111-1111-4111-8111-111111111111</v><v>42</v><v ref="start"/><v ref="duration"/><v>completed</v></row></root>"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "signpost.xml"
            path.write_text(xml, encoding="utf-8")
            result = canonicalizer.canonicalize(path, self.signpost_mapping())
        self.assertEqual(result["rows"][0]["start_ns"], 1_000_000_001)
        self.assertEqual(result["rows"][0]["duration_ns"], 2_500)

    def test_mapping_top_level_and_column_specs_are_exact(self):
        mapping = self.signpost_mapping()
        mapping["unknown"] = "private"
        with self.assertRaisesRegex(canonicalizer.MappingError, "exact allowlist"):
            canonicalizer.validate_mapping(mapping)
        mapping = self.signpost_mapping()
        mapping["columns"]["pid"]["unknown"] = "private"
        with self.assertRaisesRegex(canonicalizer.MappingError, "unknown fields"):
            canonicalizer.validate_mapping(mapping)

    def test_public_table_contains_only_target_pid_and_binds_full_table(self):
        full = {
            "schema": "ane-v2-canonical-interval-table-v1",
            "table_role": "mpsgraph_program",
            "native_identifier_name": "program-id",
            "timestamp_unit": "ns",
            "source_export_sha256": "a" * 64,
            "column_mapping_sha256": "b" * 64,
            "rows": [
                {"pid": 42, "row_id": "target"},
                {"pid": 99, "row_id": "other"},
            ],
        }
        public = canonicalizer.publicize_canonical_table(full, 42)
        self.assertEqual([row["row_id"] for row in public["rows"]], ["target"])
        self.assertEqual(public["excluded_other_process_count"], 1)
        self.assertEqual(
            public["full_table_sha256"],
            hashlib.sha256(canonicalizer.canonical_json_bytes(full)).hexdigest(),
        )


class ExportAndIdentityTests(unittest.TestCase):
    def test_runtime_identity_verifies_the_applied_patch_and_both_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            identity = prepare_fixture_runtime_identity(runtime)
            self.assertEqual(identity["base_revision"], runtime["head"])
            self.assertEqual(identity["patch_sha256"], runtime["patch_sha256"])
            self.assertEqual(identity["patched_files"], list(runtime["patched_files"]))

    def test_runtime_identity_rejects_a_missing_or_extra_changed_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            second = runtime["patched_files"][1]["path"]
            (runtime["checkout"] / second).write_bytes(runtime["base_bytes"][second])
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "outside the frozen runtime patch"
            ):
                prepare_fixture_runtime_identity(runtime)

        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            third = "Sources/Three.swift"
            (runtime["checkout"] / third).write_bytes(b"let three = 30\n")
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "outside the frozen runtime patch"
            ):
                prepare_fixture_runtime_identity(runtime)

    def test_runtime_identity_rejects_unpatched_drift_untracked_and_wrong_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            for record in runtime["patched_files"]:
                (runtime["checkout"] / record["path"]).write_bytes(
                    runtime["base_bytes"][record["path"]]
                )
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "outside the frozen runtime patch"
            ):
                prepare_fixture_runtime_identity(runtime)

        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            runtime["patched_files"] = tuple(
                dict(record) for record in runtime["patched_files"]
            )
            runtime["patched_files"][0]["patched_sha256"] = "f" * 64
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "patched source hash mismatch"
            ):
                prepare_fixture_runtime_identity(runtime)

        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            (runtime["checkout"] / "untracked.txt").write_text(
                "not part of the runtime\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "contains untracked files"
            ):
                prepare_fixture_runtime_identity(runtime)

        with tempfile.TemporaryDirectory() as temporary:
            runtime = create_patched_runtime_checkout(Path(temporary))
            runtime["head"] = "f" * 40
            with self.assertRaisesRegex(
                identity_preparer.IdentityError, "checkout revision mismatch"
            ):
                prepare_fixture_runtime_identity(runtime)

    def test_artifact_file_discovery_excludes_only_the_root_generated_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / identity_preparer.BENCHMARK_MANIFEST_NAME).write_text(
                "root generated manifest\n", encoding="utf-8"
            )
            nested = root / "nested" / identity_preparer.BENCHMARK_MANIFEST_NAME
            nested.parent.mkdir()
            nested.write_text("downloaded payload\n", encoding="utf-8")
            (root / "payload.bin").write_bytes(b"payload")

            paths = [record["path"] for record in identity_preparer.artifact_files(root)]
            self.assertNotIn(identity_preparer.BENCHMARK_MANIFEST_NAME, paths)
            self.assertIn(
                f"nested/{identity_preparer.BENCHMARK_MANIFEST_NAME}", paths
            )

    def schemas(self):
        return {
            "signposts": "os-signpost",
            "mpsgraph": "mpsgraph-program",
            "ane": "ane-prediction",
            "process_info": "process-info",
            "odie_profile": "odie-profile",
        }

    def test_export_schemas_must_exist_once_in_the_selected_run(self):
        tables = "".join(
            f'<table schema="{schema}"/>' for schema in self.schemas().values()
        )
        xml = f'<trace-toc><run number="1"><data>{tables}</data></run></trace-toc>'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "toc.xml"
            path.write_text(xml, encoding="utf-8")
            exporter.verify_schemas_in_toc(path, 1, self.schemas())

    def test_duplicate_export_schema_is_rejected(self):
        tables = "".join(
            f'<table schema="{schema}"/>' for schema in self.schemas().values()
        ) + '<table schema="ane-prediction"/>'
        xml = f'<trace-toc><run number="1"><data>{tables}</data></run></trace-toc>'
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "toc.xml"
            path.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "contains 2 tables"):
                exporter.verify_schemas_in_toc(path, 1, self.schemas())

    def test_coreai_build_is_linked_to_the_retained_odie_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "odie.xml"
            path.write_text("<build>CoreAI build 3600.75.3</build>", encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            export = {"exports": {"odie_profile": {"sha256": digest}}}
            self.assertEqual(
                sealer.verify_odie_profile(path, export, "3600.75.3"),
                digest,
            )
            for invalid in ("build", "coreai", ">", "3600.75.30", "600.75.3"):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    sealer.verify_odie_profile(path, export, invalid)

    def test_coreai_build_resolves_xctrace_xml_references(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "odie.xml"
            path.write_text(
                '<root><definitions><v id="label">CoreAI build</v>'
                '<v id="version">3600.75.3</v></definitions>'
                '<row><v ref="label"/><v ref="version"/></row></root>',
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            export = {"exports": {"odie_profile": {"sha256": digest}}}
            self.assertEqual(
                sealer.verify_odie_profile(path, export, "3600.75.3"), digest
            )

    def test_identity_outputs_enforce_public_private_directory_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = (root / "repo").resolve()
            publication = (root / "publication").resolve()
            public = (publication / "identity.json").resolve()
            private = (root / "private" / "identity-private.json").resolve()
            identity_preparer.validate_output_boundaries(
                repo=repo,
                publication_dir=publication,
                public_output=public,
                private_output=private,
            )
            with self.assertRaisesRegex(identity_preparer.IdentityError, "outside the repository"):
                identity_preparer.validate_output_boundaries(
                    repo=repo,
                    publication_dir=publication,
                    public_output=public,
                    private_output=repo / "identity-private.json",
                )

    def test_signed_true_requires_strict_codesign_verification_first(self):
        calls = []

        def fake_run(command, *, cwd=None):
            calls.append(command)
            if "--verbose=4" in command:
                return mock.Mock(
                    stdout=b"",
                    stderr=(
                        b"Identifier=io.massif.PublicW8TraceConfirmation\n"
                        b"TeamIdentifier=TESTTEAM01\n"
                        b"CDHash=0123456789abcdef\n"
                        b"Format=Mach-O thin\n"
                        b"Authority=Apple Development: Test\n"
                    ),
                )
            if "--entitlements" in command:
                return mock.Mock(stdout=b"<plist/>", stderr=b"")
            return mock.Mock(stdout=b"", stderr=b"")

        with mock.patch.object(identity_preparer, "run", side_effect=fake_run):
            public, private = identity_preparer.code_signing_identity(
                Path("Trace.app"), "io.massif.PublicW8TraceConfirmation"
            )
        self.assertEqual(
            calls[0][:4], ["codesign", "--verify", "--deep", "--strict"]
        )
        self.assertIs(public["signed"], True)
        self.assertNotIn("team_identifier", public)
        self.assertEqual(private["team_identifier"], "TESTTEAM01")

    def test_strict_codesign_failure_cannot_emit_signed_true(self):
        with mock.patch.object(
            identity_preparer,
            "run",
            side_effect=identity_preparer.IdentityError("strict verification failed"),
        ):
            with self.assertRaisesRegex(identity_preparer.IdentityError, "strict verification"):
                identity_preparer.code_signing_identity(
                    Path("Trace.app"), "io.massif.PublicW8TraceConfirmation"
                )

    def test_app_identity_reads_actual_release_configuration_from_info_plist(self):
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "Trace.app"
            app.mkdir()
            (app / "Trace").write_bytes(b"executable")

            def write_info(configuration):
                with (app / "Info.plist").open("wb") as handle:
                    plistlib.dump(
                        {
                            "CFBundleExecutable": "Trace",
                            "CFBundleIdentifier": "io.massif.PublicW8TraceConfirmation",
                            "ANETraceBuildConfiguration": configuration,
                        },
                        handle,
                    )

            write_info("Debug")
            with self.assertRaisesRegex(identity_preparer.IdentityError, "Release build"):
                identity_preparer.app_identity(app)
            write_info("Release")
            public_signing = {
                "signed": True,
                "cdhash": "abc",
                "signature_format": "fixture",
                "entitlements_sha256": "a" * 64,
                "codesign_display_sha256": "b" * 64,
            }
            private_signing = {
                "identifier": "io.massif.PublicW8TraceConfirmation",
                "team_identifier": "TEAM",
                "authorities": ["fixture"],
                "verification": {
                    "argv": ["codesign", "--verify", "--deep", "--strict", "${APP_BUNDLE}"],
                    "return_code": 0,
                    "verified": True,
                },
            }
            with mock.patch.object(
                identity_preparer,
                "code_signing_identity",
                return_value=(public_signing, private_signing),
            ):
                public, _private = identity_preparer.app_identity(app)
            self.assertEqual(public["configuration"], "Release")

    def test_private_identity_binding_requires_mode_0600(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "identity.json"
            public.write_bytes((FIXTURE / "identity.json").read_bytes())
            private = root / "identity-private.json"
            private.write_text(
                json.dumps(
                    {
                        "schema": "private-w8-trace-signing-identity-v2",
                        "public_identity_sha256": hashlib.sha256(public.read_bytes()).hexdigest(),
                        "code_signing": {
                            "identifier": "io.massif.PublicW8TraceConfirmation",
                            "team_identifier": "TESTTEAM01",
                            "authorities": ["Apple Development: Test"],
                            "verification": {
                                "argv": [
                                    "codesign", "--verify", "--deep", "--strict",
                                    "${APP_BUNDLE}",
                                ],
                                "return_code": 0,
                                "verified": True,
                            },
                        },
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            private.chmod(0o600)
            sealer.verify_private_identity_binding(private, public)
            private.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "mode 0600"):
                sealer.verify_private_identity_binding(private, public)

    def test_extractor_rejects_unknown_public_app_fields(self):
        record = read("app-records.json")["records"][0]
        record["error"] = "private error"
        with self.assertRaisesRegex(SystemExit, "public allowlist"):
            extractor.validate_public_record(record, 1)

    def test_extractor_rejects_string_smuggled_into_numeric_field(self):
        record = read("app-records.json")["records"][1]
        record["cached_input_tokens"] = "raw stderr"
        with self.assertRaisesRegex(SystemExit, "must be an integer"):
            extractor.validate_public_record(record, 1)

    def test_sealed_source_identity_is_recomputed_from_current_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            bound = create_bound_source_repository(Path(temporary))
            identity = read("identity.json")
            identity["source"] = bound["source"]
            analyzer.verify_current_source_identity(identity, bound["repo"])
            for relative in (
                analyzer.AMENDMENT_RELATIVE_PATH,
                "paper/evidence/ane-v2/analyze_trace.py",
                analyzer.PROJECT_RELATIVE_PATH,
                analyzer.INFO_PLIST_RELATIVE_PATH,
            ):
                path = bound["repo"] / relative
                original = path.read_bytes()
                path.write_bytes(original + b"changed\n")
                with self.subTest(relative=relative), self.assertRaisesRegex(
                    analyzer.ValidationError, "current source bytes differ"
                ):
                    analyzer.verify_current_source_identity(identity, bound["repo"])
                path.write_bytes(original)

    def test_sealed_source_identity_accepts_a_descendant_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            bound = create_bound_source_repository(Path(temporary))
            identity = read("identity.json")
            identity["source"] = bound["source"]
            evidence = bound["repo"] / "paper" / "final-evidence.json"
            evidence.write_text('{"status":"sealed"}\n', encoding="utf-8")
            for command in (
                ["git", "add", "paper/final-evidence.json"],
                ["git", "commit", "-q", "-m", "publish sealed evidence"],
            ):
                subprocess.run(command, cwd=bound["repo"], check=True, capture_output=True)
            analyzer.verify_current_source_identity(identity, bound["repo"])

    def test_publication_scan_rejects_private_identity_fields(self):
        with self.assertRaisesRegex(publication.PublicationError, "private keys"):
            publication.scan_public_value(
                {"schema": "public-w8-trace-identity-v4", "team_identifier": "PRIVATE"},
                "identity.json",
            )

    def test_publication_loader_rejects_duplicate_keys_before_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            path.write_text('{"schema":"one","schema":"two"}\n', encoding="utf-8")
            with self.assertRaisesRegex(publication.PublicationError, "duplicate JSON key"):
                publication.load_json(path)

    def test_publication_loader_scans_raw_bytes_for_embedded_paths_and_raw_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            for payload in (
                '{"value":"prefix /Users/reviewer/private"}\n',
                '{"raw_stderr":"framework failure"}\n',
                '{"value":"/private/var/containers/Bundle/Application/secret"}\n',
                '{"value":"Identifier=io.private.TeamOnly"}\n',
                '{"value":"00008110-001A2B3C4D5E6F70"}\n',
            ):
                path.write_text(payload, encoding="utf-8")
                with self.subTest(payload=payload), self.assertRaises(
                    publication.PublicationError
                ):
                    publication.load_json(path)

    def test_complete_publication_bundle_is_recomputed_and_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bound = create_bound_source_repository(root)
            bundle = root / "bundle"
            bundle.mkdir()
            identity = read("identity.json")
            identity["source"] = bound["source"]
            (bundle / "identity.json").write_text(
                json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            run_metadata = read("run-metadata.json")
            run_metadata["identity_record_sha256"] = hashlib.sha256(
                (bundle / "identity.json").read_bytes()
            ).hexdigest()
            run_metadata["protocol_amendment_sha256"] = bound["source"][
                "amendment_file_sha256"
            ]
            (bundle / "run-metadata.json").write_text(
                json.dumps(run_metadata, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            fixture_names = {
                "capture-command.json": "capture-command.json",
                "export-command.json": "export-command.json",
                "app-records.json": "app-records.json",
            }
            for output_name, fixture_name in fixture_names.items():
                (bundle / output_name).write_bytes((FIXTURE / fixture_name).read_bytes())
            tables = {}
            for role, table_name, map_name in (
                ("signposts", "signposts.json", "signpost-map.json"),
                ("mpsgraph_program", "mpsgraph.json", "mpsgraph-map.json"),
                ("ane_prediction", "ane.json", "ane-map.json"),
            ):
                mapping = (
                    signpost_mapping()
                    if role == "signposts"
                    else interval_mapping(role)
                )
                map_path = bundle / map_name
                map_path.write_text(
                    json.dumps(mapping, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                table = read(table_name)
                table["column_mapping_sha256"] = publication.canonical_json_sha256(mapping)
                table_path = bundle / table_name
                table_path.write_text(
                    json.dumps(table, sort_keys=True, separators=(",", ":")) + "\n",
                    encoding="utf-8",
                )
                tables[table_name] = table
            inputs = {
                "signposts": tables["signposts.json"],
                "mpsgraph": tables["mpsgraph.json"],
                "ane": tables["ane.json"],
                "identity": identity,
                "run_metadata": run_metadata,
                "capture_command": read("capture-command.json"),
                "export_command": read("export-command.json"),
                "app_records": read("app-records.json"),
                "input_hashes": {
                    "signposts": hashlib.sha256((bundle / "signposts.json").read_bytes()).hexdigest(),
                    "mpsgraph": hashlib.sha256((bundle / "mpsgraph.json").read_bytes()).hexdigest(),
                    "ane": hashlib.sha256((bundle / "ane.json").read_bytes()).hexdigest(),
                    "identity_record": hashlib.sha256(
                        (bundle / "identity.json").read_bytes()
                    ).hexdigest(),
                    "run_metadata": hashlib.sha256(
                        (bundle / "run-metadata.json").read_bytes()
                    ).hexdigest(),
                    "capture_command": fixture_sha256("capture-command.json"),
                    "export_command": fixture_sha256("export-command.json"),
                    "app_records": fixture_sha256("app-records.json"),
                },
            }
            (bundle / "ane-analysis.json").write_bytes(
                analyzer.canonical_json_bytes(
                    analyzer.analyze(**inputs, source_root=bound["repo"])
                )
            )
            publication.validate_bundle(
                bundle, analyzer, canonicalizer, bound["repo"]
            )


if __name__ == "__main__":
    unittest.main()
