#!/usr/bin/env python3
"""Deterministic ANE trace-window validator and exact multiset join.

The tool consumes canonical interval exports.  It deliberately performs no
timestamp tolerance, nearest-neighbour matching, row-order pairing, or count
substitution.  See README.md for the canonical input contract.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SIGNPOST_SUBSYSTEM = "io.massif.qwen3.coreai.trace-confirmation"
SIGNPOST_CATEGORY = "inference"
SIGNPOST_NAME = "PUBLIC_W8_TRACE_CONFIRMATION_V1"
ARTIFACT_REPOSITORY = "massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p"
ARTIFACT_REVISION = "75bbe06906cb5d953e602e3e4fb6364187c81822"
ROOT_METADATA_VERSION = "0.2"
ROOT_METADATA_SHA256 = "c12e3b1035dd8c009d5b8d8572d0ad829236871edd10c02ef35d89644c5289d1"
PUBLISHED_SHA256SUMS_SHA256 = "11b44a503983182f99f5de2a458947ac1bfb9b68bfaafd39a5b13feb4d430be9"
BENCHMARK_MANIFEST_SHA256 = "91c68e82e280a36d39aaeef9b8726ab1d59e52760b6f970db67c334a674d47b2"
BENCHMARK_MANIFEST_FILE_COUNT = 59
PUBLISHED_SHA256SUMS_ENTRY_COUNT = 57
ARTIFACT_SOURCE_HASH = "13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c"
MAIN_H16P_SHA256 = "09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca"
ARTIFACT_PRODUCER = "coreai-build-3600.83.1"
COMPILED_BUNDLE_FILE_LIST_SHA256 = (
    "182336f4654bb735bcad35e45f7832756c34469931ad96d872532dca727ebd8d"
)
COREAI_SOURCE_REVISION = "04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a"
COREAI_REPOSITORY = "https://github.com/apple/coreai-models.git"
RUNTIME_PATCH_RELATIVE_PATH = (
    "paper/evidence/ane-v2/coreai-models-xcode27-beta6-compat.patch"
)
RUNTIME_PATCH_SHA256 = "100d8e3e0c865aa3a94e0bc96f5f202fc6581e1df029053a0f72e69198919044"
PATCHED_RUNTIME_FILES = [
    {
        "path": (
            "swift/Sources/CoreAILanguageModels/LanguageModel/"
            "CoreAILanguageModel.swift"
        ),
        "base_sha256": "9a672d0b3c8faa200a7326a5c38df74740bd31c8f96bce12232fdc41f967ca23",
        "patched_sha256": "fd6f9b7c7344faf9bb6e3333dc06fb9a8466f886f1d994458afb939d0762ead6",
    },
    {
        "path": (
            "swift/Sources/CoreAILanguageModels/VLM/"
            "CoreAIVisionLanguageModel.swift"
        ),
        "base_sha256": "78a426a821bd1dd4eff4a5eda1c77a72444270ec5ed2a49538113887b8c48a99",
        "patched_sha256": "0938e55c0a5b8dc1430bb2ea87ed78795df6255a6c1c331cd55853dd09c07a1d",
    },
]
MEASURED_PROMPT_SHA256 = "d975102e7856d44efc3e483a2c919e7a9d612fde515c50b110bc255a13a20f81"
TARGET_DEVICE_IDENTIFIER_CLASS = "iPhone16,1"
PUBLIC_BUNDLE_IDENTIFIER = "io.massif.PublicW8TraceConfirmation"
PRIOR_AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_1.md"
ARTIFACT_AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_2.md"
AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_3.md"
PROJECT_RELATIVE_PATH = "companion/CoreAIQwen17Companion.xcodeproj/project.pbxproj"
INFO_PLIST_RELATIVE_PATH = "companion/CoreAIQwen17Companion/Info.plist"
PACKAGE_RESOLVED_RELATIVE_PATH = (
    "companion/CoreAIQwen17Companion.xcodeproj/project.xcworkspace/"
    "xcshareddata/swiftpm/Package.resolved"
)
PROTOCOL_RELATIVE_PATH = "paper/EXPERIMENT_PROTOCOL_V1.md"
REQUIRED_SOURCE_PATHS = {
    "companion/CoreAIQwen17Companion/CoreAIQwen17CompanionApp.swift",
    INFO_PLIST_RELATIVE_PATH,
    PRIOR_AMENDMENT_RELATIVE_PATH,
    ARTIFACT_AMENDMENT_RELATIVE_PATH,
    AMENDMENT_RELATIVE_PATH,
    RUNTIME_PATCH_RELATIVE_PATH,
    "paper/evidence/ane-v2/analyze_trace.py",
    "paper/evidence/ane-v2/canonicalize_xctrace.py",
    "paper/evidence/ane-v2/capture_trace.py",
    "paper/evidence/ane-v2/download_public_w8.sh",
    "paper/evidence/ane-v2/export_trace.py",
    "paper/evidence/ane-v2/extract_app_records.py",
    "paper/evidence/ane-v2/prepare_identity.py",
    "paper/evidence/ane-v2/seal_run_metadata.py",
    "paper/evidence/ane-v2/validate_public_bundle.py",
}
PERMITTED_CONCLUSION = (
    "The Apple Neural Engine participated in the traced inference program."
)
CLAIM_EXCLUSIONS = [
    "exclusive ANE execution",
    "the proportion of work executed on ANE",
    "the absence of CPU or GPU work",
    "a performance or energy advantage",
    "behavior outside the recorded artifact, app build, device, OS, and run",
]
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
COREAI_BUILD_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2,}$")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
APP_BASE_FIELDS = {"schema", "event", "run_uuid"}
APP_GENERATION_FIELDS = {
    "cached_input_tokens", "emitted_tokens", "input_tokens", "reasoning_tokens",
    "time_to_first_token_seconds", "total_seconds",
}
APP_EVENT_FIELDS = {
    "prerequisites_begin": {
        "app_bundle_identifier", "app_executable_sha256", "artifact_repository",
        "artifact_revision", "artifact_source_hash", "coreai_source_revision",
        "device_identifier_class", "device_model", "low_power_mode_enabled",
        "os_build", "os_version", "pid", "thermal_state", "wall_clock_utc",
    },
    "smoke_complete": APP_GENERATION_FIELDS | {"pid", "wall_clock_utc"},
    "warmup_complete": APP_GENERATION_FIELDS | {"pid", "wall_clock_utc"},
    "measured_session_ready": {"pid", "wall_clock_utc"},
    "measured_request_begin": {"pid", "prompt_sha256", "wall_clock_utc"},
    "measured_request_end": APP_GENERATION_FIELDS
    | {"pid", "prompt_sha256", "terminal_state", "wall_clock_utc"},
}


class ValidationError(ValueError):
    """Raised when evidence does not satisfy the frozen input contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def benchmark_manifest_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read canonical JSON {path}: {error}") from error


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def require_exact_keys(value: Any, expected: set[str], field: str) -> None:
    require(isinstance(value, dict), f"{field} must be an object")
    actual = set(value)
    require(
        actual == expected,
        f"{field} fields differ from the public allowlist; "
        f"unknown={sorted(actual - expected)} missing={sorted(expected - actual)}",
    )


def require_string(value: Any, field: str) -> str:
    require(isinstance(value, str) and bool(value), f"{field} must be a non-empty string")
    return value


def require_int(value: Any, field: str, *, minimum: int = 0) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool) and value >= minimum,
        f"{field} must be an integer >= {minimum}",
    )
    return value


def require_number(value: Any, field: str, *, minimum: float = 0.0) -> float:
    require(
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= minimum,
        f"{field} must be a finite number >= {minimum}",
    )
    return float(value)


def require_sha256(value: Any, field: str) -> str:
    value = require_string(value, field)
    require(bool(SHA256_RE.fullmatch(value)), f"{field} must be a lowercase SHA-256")
    return value


def require_relative_posix_path(value: Any, field: str) -> str:
    value = require_string(value, field)
    parts = value.split("/")
    require(
        not value.startswith("/")
        and "\\" not in value
        and all(part not in ("", ".", "..") for part in parts),
        f"{field} must be a normalized relative POSIX path",
    )
    return value


def require_uuid(value: Any, field: str) -> str:
    value = require_string(value, field).lower()
    require(bool(UUID_RE.fullmatch(value)), f"{field} must be a lowercase RFC 4122 UUID")
    return value


def require_utc_timestamp(value: Any, field: str) -> datetime:
    value = require_string(value, field)
    require(value.endswith("Z"), f"{field} must be an explicit UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValidationError(f"{field} is not an ISO-8601 timestamp") from error
    return parsed


def validate_identity(identity: Any) -> None:
    require_exact_keys(
        identity,
        {"schema", "artifact", "source", "runtime", "app", "toolchain"},
        "identity",
    )
    require(
        identity.get("schema") == "public-w8-trace-identity-v4",
        "identity record schema mismatch",
    )
    artifact = identity.get("artifact")
    source = identity.get("source")
    runtime = identity.get("runtime")
    app = identity.get("app")
    toolchain = identity.get("toolchain")
    require_exact_keys(
        artifact,
        {
            "repository", "revision", "root_metadata_version", "root_metadata_sha256",
            "source_hash", "main_h16p_sha256", "artifact_producer",
            "compiled_bundle_file_list_sha256", "manifest_format", "manifest_sha256", "payloads",
            "published_sha256s", "published_sha256s_file_sha256",
        },
        "identity.artifact",
    )
    require_exact_keys(
        source,
        {
            "git_commit", "git_status_clean", "project_file", "project_file_sha256",
            "package_resolved_file", "package_resolved_file_sha256", "protocol_file",
            "protocol_file_sha256", "prior_amendment_file",
            "prior_amendment_file_sha256", "artifact_amendment_file",
            "artifact_amendment_file_sha256", "amendment_file",
            "amendment_file_sha256", "source_files",
        },
        "identity.source",
    )
    require_exact_keys(
        runtime,
        {"repository", "base_revision", "patch_file", "patch_sha256", "patched_files"},
        "identity.runtime",
    )
    require_exact_keys(
        app,
        {
            "configuration", "bundle_identifier", "bundle_manifest_sha256",
            "bundle_file_count", "executable_relative_path", "executable_sha256",
            "info_plist_sha256", "code_signing",
        },
        "identity.app",
    )
    require_exact_keys(
        toolchain,
        {
            "xcode_version", "xcode_build", "instruments_version",
            "instruments_build", "coreai_source_revision",
        },
        "identity.toolchain",
    )

    require(artifact.get("repository") == ARTIFACT_REPOSITORY, "artifact repository mismatch")
    require(artifact.get("revision") == ARTIFACT_REVISION, "artifact revision mismatch")
    require(
        artifact.get("root_metadata_version") == ROOT_METADATA_VERSION,
        "root metadata version mismatch",
    )
    require(
        artifact.get("root_metadata_sha256") == ROOT_METADATA_SHA256,
        "root metadata hash mismatch",
    )
    require(artifact.get("source_hash") == ARTIFACT_SOURCE_HASH, "artifact sourceHash mismatch")
    require(
        artifact.get("main_h16p_sha256") == MAIN_H16P_SHA256,
        "compiled main-h16p.mlirb mismatch",
    )
    require(
        artifact.get("artifact_producer") == ARTIFACT_PRODUCER,
        "artifact producer mismatch",
    )
    require(
        artifact.get("compiled_bundle_file_list_sha256")
        == COMPILED_BUNDLE_FILE_LIST_SHA256,
        "compiled-bundle fingerprint mismatch",
    )
    require(
        artifact.get("manifest_sha256") == BENCHMARK_MANIFEST_SHA256,
        "benchmark artifact manifest hash mismatch",
    )
    require(
        artifact.get("manifest_format")
        == "benchmark-artifact-manifest-json-v2",
        "artifact manifest format mismatch",
    )
    payloads = artifact.get("payloads")
    require(isinstance(payloads, list) and bool(payloads), "artifact payload manifest is empty")
    paths: set[str] = set()
    payload_paths: list[str] = []
    manifest_files: list[dict[str, Any]] = []
    found_main = False
    for index, payload in enumerate(payloads):
        require_exact_keys(
            payload, {"path", "kind", "size_bytes", "sha256"},
            f"artifact.payloads[{index}]",
        )
        path = require_relative_posix_path(payload.get("path"), f"artifact.payloads[{index}].path")
        require(path not in paths, f"duplicate artifact payload path: {path}")
        paths.add(path)
        payload_paths.append(path)
        require(payload.get("kind") == "file", f"artifact payload {index} must be a regular file")
        size_bytes = require_int(
            payload.get("size_bytes"), f"artifact.payloads[{index}].size_bytes"
        )
        digest = require_sha256(payload.get("sha256"), f"artifact.payloads[{index}].sha256")
        manifest_files.append(
            {"path": path, "bytes": size_bytes, "sha256": digest}
        )
        if path.endswith("/main-h16p.mlirb") or path == "main-h16p.mlirb":
            require(not found_main, "artifact manifest contains multiple main-h16p.mlirb files")
            require(digest == MAIN_H16P_SHA256, "artifact payload main hash mismatch")
            found_main = True
    require(found_main, "artifact manifest does not contain main-h16p.mlirb")
    require(
        len(payloads) == BENCHMARK_MANIFEST_FILE_COUNT,
        f"artifact manifest must contain {BENCHMARK_MANIFEST_FILE_COUNT} files",
    )
    require(
        payload_paths == sorted(payload_paths),
        "artifact payload manifest is not in canonical path order",
    )
    payload_by_path = {payload["path"]: payload["sha256"] for payload in payloads}
    require(
        payload_by_path.get("metadata.json") == ROOT_METADATA_SHA256,
        "artifact manifest root metadata identity mismatch",
    )
    require(
        payload_by_path.get("SHA256SUMS") == PUBLISHED_SHA256SUMS_SHA256,
        "artifact manifest SHA256SUMS identity mismatch",
    )
    require(
        artifact.get("published_sha256s_file_sha256")
        == PUBLISHED_SHA256SUMS_SHA256,
        "published SHA256SUMS file hash mismatch",
    )
    published = artifact.get("published_sha256s")
    require(isinstance(published, list) and bool(published), "published SHA256SUMS is empty")
    payload_by_path = {payload["path"]: payload["sha256"] for payload in payloads}
    published_paths: set[str] = set()
    published_path_order: list[str] = []
    published_records: list[dict[str, str]] = []
    for index, record in enumerate(published):
        require_exact_keys(record, {"path", "sha256"}, f"published_sha256s[{index}]")
        path = require_relative_posix_path(record.get("path"), f"published_sha256s[{index}].path")
        digest = require_sha256(record.get("sha256"), f"published_sha256s[{index}].sha256")
        require(path not in published_paths, f"duplicate published SHA256SUMS path: {path}")
        published_paths.add(path)
        published_path_order.append(path)
        require(payload_by_path.get(path) == digest, f"published digest differs for {path}")
        published_records.append({"path": path, "sha256": digest})
    require(
        len(published_records) == PUBLISHED_SHA256SUMS_ENTRY_COUNT,
        f"published SHA256SUMS must contain {PUBLISHED_SHA256SUMS_ENTRY_COUNT} entries",
    )
    require(
        published_path_order == sorted(published_path_order),
        "published SHA256SUMS entries are not in canonical path order",
    )
    expected_published_paths = sorted(paths - {".gitattributes", "SHA256SUMS"})
    require(
        published_path_order == expected_published_paths,
        "published SHA256SUMS path set differs from the frozen payload set",
    )
    manifest_document = {
        "schemaVersion": 2,
        "repository": ARTIFACT_REPOSITORY,
        "revision": ARTIFACT_REVISION,
        "publishedSHA256SUMS": {
            "sha256": PUBLISHED_SHA256SUMS_SHA256,
            "entries": len(published_records),
            "matchingEntries": len(published_records),
            "acknowledgedMismatches": [],
        },
        "files": manifest_files,
    }
    reconstructed_manifest_sha256 = hashlib.sha256(
        benchmark_manifest_json_bytes(manifest_document)
    ).hexdigest()
    require(
        reconstructed_manifest_sha256 == artifact["manifest_sha256"],
        "identity payloads do not reconstruct the frozen benchmark manifest",
    )

    commit = require_string(source.get("git_commit"), "identity.source.git_commit")
    require(bool(COMMIT_RE.fullmatch(commit)), "source git commit must be a lowercase 40-hex ID")
    require(source.get("git_status_clean") is True, "instrumented companion source was dirty")
    require(
        source.get("project_file") == "companion/CoreAIQwen17Companion.xcodeproj/project.pbxproj",
        "identity source project path mismatch",
    )
    require_sha256(source.get("project_file_sha256"), "identity.source.project_file_sha256")
    require(
        source.get("package_resolved_file")
        == "companion/CoreAIQwen17Companion.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved",
        "identity source Package.resolved path mismatch",
    )
    require_sha256(
        source.get("package_resolved_file_sha256"),
        "identity.source.package_resolved_file_sha256",
    )
    require(
        source.get("protocol_file") == "paper/EXPERIMENT_PROTOCOL_V1.md",
        "identity source protocol path mismatch",
    )
    require_sha256(source.get("protocol_file_sha256"), "identity.source.protocol_file_sha256")
    require(
        source.get("prior_amendment_file") == PRIOR_AMENDMENT_RELATIVE_PATH,
        "identity source prior-amendment path mismatch",
    )
    require_sha256(
        source.get("prior_amendment_file_sha256"),
        "identity.source.prior_amendment_file_sha256",
    )
    require(
        source.get("artifact_amendment_file") == ARTIFACT_AMENDMENT_RELATIVE_PATH,
        "identity source artifact-amendment path mismatch",
    )
    require_sha256(
        source.get("artifact_amendment_file_sha256"),
        "identity.source.artifact_amendment_file_sha256",
    )
    require(source.get("amendment_file") == AMENDMENT_RELATIVE_PATH, "identity source amendment path mismatch")
    require_sha256(source.get("amendment_file_sha256"), "identity.source.amendment_file_sha256")
    files = source.get("source_files")
    require(isinstance(files, list) and bool(files), "source file manifest is empty")
    source_paths = set()
    for index, record in enumerate(files):
        require_exact_keys(record, {"path", "sha256"}, f"source.source_files[{index}]")
        path = require_relative_posix_path(record.get("path"), f"source.source_files[{index}].path")
        require(path not in source_paths, f"duplicate source file path: {path}")
        source_paths.add(path)
        require_sha256(record.get("sha256"), f"source.source_files[{index}].sha256")
    missing_source_paths = sorted(REQUIRED_SOURCE_PATHS - source_paths)
    require(
        not missing_source_paths,
        f"identity source manifest lacks required files: {', '.join(missing_source_paths)}",
    )
    source_digest_by_path = {record["path"]: record["sha256"] for record in files}
    require(
        source_digest_by_path[AMENDMENT_RELATIVE_PATH]
        == source["amendment_file_sha256"],
        "source manifest does not bind the protocol amendment",
    )
    require(
        source_digest_by_path[PRIOR_AMENDMENT_RELATIVE_PATH]
        == source["prior_amendment_file_sha256"],
        "source manifest does not bind the prior protocol amendment",
    )
    require(
        source_digest_by_path[ARTIFACT_AMENDMENT_RELATIVE_PATH]
        == source["artifact_amendment_file_sha256"],
        "source manifest does not bind the artifact protocol amendment",
    )
    require(
        source_digest_by_path[RUNTIME_PATCH_RELATIVE_PATH] == RUNTIME_PATCH_SHA256,
        "source manifest does not bind the frozen runtime patch",
    )

    require(runtime.get("repository") == COREAI_REPOSITORY, "runtime repository mismatch")
    require(
        runtime.get("base_revision") == COREAI_SOURCE_REVISION,
        "runtime base revision mismatch",
    )
    require(
        runtime.get("patch_file") == RUNTIME_PATCH_RELATIVE_PATH,
        "runtime patch path mismatch",
    )
    require(
        runtime.get("patch_sha256") == RUNTIME_PATCH_SHA256,
        "runtime patch hash mismatch",
    )
    require(
        runtime.get("patch_sha256") == source_digest_by_path[RUNTIME_PATCH_RELATIVE_PATH],
        "runtime patch identity differs from the sealed source manifest",
    )
    patched_files = runtime.get("patched_files")
    require(
        isinstance(patched_files, list) and len(patched_files) == len(PATCHED_RUNTIME_FILES),
        "runtime patched-file manifest length mismatch",
    )
    for index, (observed, expected) in enumerate(zip(patched_files, PATCHED_RUNTIME_FILES)):
        require_exact_keys(
            observed,
            {"path", "base_sha256", "patched_sha256"},
            f"identity.runtime.patched_files[{index}]",
        )
        require(
            observed == expected,
            f"runtime patched-file identity mismatch at index {index}",
        )

    require(app.get("configuration") == "Release", "trace app must be a Release build")
    require(app.get("bundle_identifier") == PUBLIC_BUNDLE_IDENTIFIER, "trace app bundle identifier mismatch")
    require_sha256(app.get("bundle_manifest_sha256"), "identity.app.bundle_manifest_sha256")
    require_int(app.get("bundle_file_count"), "identity.app.bundle_file_count", minimum=1)
    executable_relative_path = require_relative_posix_path(
        app.get("executable_relative_path"), "identity.app.executable_relative_path"
    )
    require_sha256(app.get("executable_sha256"), "identity.app.executable_sha256")
    require_sha256(app.get("info_plist_sha256"), "identity.app.info_plist_sha256")
    signing = app.get("code_signing")
    require_exact_keys(
        signing,
        {
            "signed", "cdhash", "signature_format", "entitlements_sha256",
            "codesign_display_sha256",
        },
        "identity.app.code_signing",
    )
    require(signing.get("signed") is True, "strict codesign verification was not recorded")
    require_string(signing.get("cdhash"), "identity.app.code_signing.cdhash")
    require_string(signing.get("signature_format"), "identity.app.code_signing.signature_format")
    require_sha256(
        signing.get("entitlements_sha256"),
        "identity.app.code_signing.entitlements_sha256",
    )
    require_sha256(
        signing.get("codesign_display_sha256"),
        "identity.app.code_signing.codesign_display_sha256",
    )

    require_string(toolchain.get("xcode_version"), "identity.toolchain.xcode_version")
    require_string(toolchain.get("xcode_build"), "identity.toolchain.xcode_build")
    require_string(
        toolchain.get("instruments_version"), "identity.toolchain.instruments_version"
    )
    require_string(
        toolchain.get("instruments_build"), "identity.toolchain.instruments_build"
    )
    require(
        toolchain.get("coreai_source_revision") == COREAI_SOURCE_REVISION,
        "Core AI source revision mismatch",
    )
    require(
        toolchain.get("coreai_source_revision") == runtime["base_revision"],
        "toolchain and runtime Core AI revisions differ",
    )


def verify_current_source_identity(identity: Any, source_root: Path) -> None:
    source_root = source_root.resolve()
    require(source_root.is_dir(), "source root is not a directory")
    source = identity["source"]
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        capture_output=True,
        check=False,
        text=True,
    )
    require(completed.returncode == 0, "cannot resolve the current source commit")
    current_commit = completed.stdout.strip()
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source["git_commit"], current_commit],
        cwd=source_root,
        capture_output=True,
        check=False,
    )
    require(
        ancestor.returncode == 0,
        "sealed source commit is not an ancestor of the current source commit",
    )

    explicit_files = {
        "project_file": (PROJECT_RELATIVE_PATH, "project_file_sha256"),
        "package_resolved_file": (
            PACKAGE_RESOLVED_RELATIVE_PATH,
            "package_resolved_file_sha256",
        ),
        "protocol_file": (PROTOCOL_RELATIVE_PATH, "protocol_file_sha256"),
        "prior_amendment_file": (
            PRIOR_AMENDMENT_RELATIVE_PATH,
            "prior_amendment_file_sha256",
        ),
        "artifact_amendment_file": (
            ARTIFACT_AMENDMENT_RELATIVE_PATH,
            "artifact_amendment_file_sha256",
        ),
        "amendment_file": (AMENDMENT_RELATIVE_PATH, "amendment_file_sha256"),
    }
    for path_field, (expected_path, digest_field) in explicit_files.items():
        require(source[path_field] == expected_path, f"sealed {path_field} path mismatch")
        path = source_root / expected_path
        require(
            path.is_file() and not path.is_symlink(),
            f"current source file is missing or not regular: {expected_path}",
        )
        require(
            sha256_file(path) == source[digest_field],
            f"current source bytes differ from the sealed identity: {expected_path}",
        )

    discovered = sorted((source_root / "companion").rglob("*.swift"))
    discovered.extend(sorted((source_root / "companion").rglob("*.plist")))
    discovered.extend(sorted((source_root / "paper/evidence/ane-v2").glob("*.py")))
    discovered.extend(sorted((source_root / "paper/evidence/ane-v2").glob("*.sh")))
    discovered.extend(sorted((source_root / "paper/evidence/ane-v2").glob("*.patch")))
    discovered.extend(
        [
            source_root / PRIOR_AMENDMENT_RELATIVE_PATH,
            source_root / ARTIFACT_AMENDMENT_RELATIVE_PATH,
            source_root / AMENDMENT_RELATIVE_PATH,
        ]
    )
    discovered.sort(key=lambda path: path.relative_to(source_root).as_posix())
    actual_paths = [path.relative_to(source_root).as_posix() for path in discovered]
    sealed_records = source["source_files"]
    sealed_paths = [record["path"] for record in sealed_records]
    require(
        actual_paths == sealed_paths,
        "current source file set differs from the sealed identity",
    )
    for path, record in zip(discovered, sealed_records):
        relative = record["path"]
        require(
            path.is_file() and not path.is_symlink(),
            f"current source file is missing or not regular: {relative}",
        )
        require(
            sha256_file(path) == record["sha256"],
            f"current source bytes differ from the sealed identity: {relative}",
        )


def validate_run_metadata(metadata: Any, identity: Any, identity_sha256: str) -> tuple[str, int]:
    require_exact_keys(
        metadata,
        {
            "schema", "run_uuid", "pid", "device_model", "device_identifier_class",
            "os_version", "os_build", "xcode_version", "xcode_build",
            "instruments_version", "instruments_build", "coreai_build", "thermal_state",
            "low_power_mode_enabled", "capture_start_utc", "capture_end_utc",
            "trace_start_utc", "trace_end_utc", "input_tokens", "emitted_tokens",
            "terminal_state", "trace_sha256", "capture_command_record_sha256",
            "export_command_record_sha256", "app_records_sha256",
            "odie_profile_export_sha256", "identity_record_sha256",
            "installed_bundle_identifier", "identity_binding_verified",
            "protocol_amendment_sha256",
        },
        "run_metadata",
    )
    require(
        metadata.get("schema") == "public-w8-trace-run-metadata-v2",
        "run metadata schema mismatch",
    )
    run_uuid = require_uuid(metadata.get("run_uuid"), "run_metadata.run_uuid")
    pid = require_int(metadata.get("pid"), "run_metadata.pid", minimum=1)
    require(metadata.get("device_model") == "iPhone 15 Pro", "device must be iPhone 15 Pro")
    require(
        metadata.get("device_identifier_class") == TARGET_DEVICE_IDENTIFIER_CLASS,
        f"device identifier class must be {TARGET_DEVICE_IDENTIFIER_CLASS}",
    )
    require_string(metadata.get("os_version"), "run_metadata.os_version")
    require_string(metadata.get("os_build"), "run_metadata.os_build")
    coreai_build = require_string(metadata.get("coreai_build"), "run_metadata.coreai_build")
    require(
        bool(COREAI_BUILD_RE.fullmatch(coreai_build)),
        "run_metadata.coreai_build must be an exact dotted numeric version",
    )
    require_string(metadata.get("thermal_state"), "run_metadata.thermal_state")
    require(
        isinstance(metadata.get("low_power_mode_enabled"), bool),
        "run_metadata.low_power_mode_enabled must be Boolean",
    )
    capture_start = require_utc_timestamp(
        metadata.get("capture_start_utc"), "run_metadata.capture_start_utc"
    )
    capture_end = require_utc_timestamp(
        metadata.get("capture_end_utc"), "run_metadata.capture_end_utc"
    )
    trace_start = require_utc_timestamp(
        metadata.get("trace_start_utc"), "run_metadata.trace_start_utc"
    )
    trace_end = require_utc_timestamp(metadata.get("trace_end_utc"), "run_metadata.trace_end_utc")
    require(capture_start < capture_end, "capture wall-clock interval is not positive")
    require(trace_start < trace_end, "measured wall-clock interval is not positive")
    require(
        capture_start <= trace_start <= trace_end <= capture_end,
        "measured wall-clock interval is not contained by the capture",
    )
    require_int(metadata.get("input_tokens"), "run_metadata.input_tokens", minimum=1)
    require_int(metadata.get("emitted_tokens"), "run_metadata.emitted_tokens")
    require(
        metadata.get("terminal_state") in ("completed", "error"),
        "run_metadata.terminal_state must be completed or error",
    )
    for field in (
        "trace_sha256",
        "capture_command_record_sha256",
        "export_command_record_sha256",
        "app_records_sha256",
        "odie_profile_export_sha256",
    ):
        require_sha256(metadata.get(field), f"run_metadata.{field}")
    require(
        metadata.get("identity_record_sha256") == identity_sha256,
        "run metadata does not identify the supplied identity record",
    )
    require(
        metadata.get("identity_binding_verified") is True,
        "private-to-public identity binding was not verified",
    )
    require(
        metadata.get("protocol_amendment_sha256")
        == identity["source"]["amendment_file_sha256"],
        "run metadata protocol amendment differs from source identity",
    )
    require(
        metadata.get("installed_bundle_identifier") == identity["app"]["bundle_identifier"],
        "installed bundle identifier differs from the Release app identity",
    )
    toolchain = identity["toolchain"]
    for field in ("xcode_version", "xcode_build", "instruments_version", "instruments_build"):
        require(
            metadata.get(field) == toolchain[field],
            f"run metadata {field} differs from the identity record",
        )
    return run_uuid, pid


def validate_capture_record(capture: Any, run_metadata: Any, pid: int) -> None:
    require_exact_keys(
        capture,
        {
            "schema", "argv", "template_sha256", "attached_pid", "started_utc",
            "ended_utc", "return_code", "xcode_version", "xcode_build",
            "instruments_version", "instruments_build",
        },
        "capture",
    )
    require(
        capture.get("schema") == "public-w8-trace-capture-command-v2",
        "capture command record schema mismatch",
    )
    require_int(capture.get("attached_pid"), "capture.attached_pid", minimum=1)
    require(capture.get("attached_pid") == pid, "capture command attached to a different PID")
    require_int(capture.get("return_code"), "capture.return_code")
    require(capture.get("return_code") == 0, "trace capture command did not succeed")
    require_string(capture.get("started_utc"), "capture.started_utc")
    require_string(capture.get("ended_utc"), "capture.ended_utc")
    require(
        capture["started_utc"] == run_metadata["capture_start_utc"]
        and capture["ended_utc"] == run_metadata["capture_end_utc"],
        "capture command timestamps differ from run metadata",
    )
    require_sha256(capture.get("template_sha256"), "capture.template_sha256")
    for field in ("xcode_version", "xcode_build", "instruments_version", "instruments_build"):
        require(
            capture.get(field) == run_metadata[field],
            f"capture {field} differs from the sealed toolchain",
        )
    argv = capture.get("argv")
    require(
        isinstance(argv, list) and all(isinstance(item, str) for item in argv),
        "capture argv must be a string array",
    )
    require(len(argv) == 16, "capture argv shape mismatch")
    time_limit = argv[10]
    require(bool(re.fullmatch(r"[1-9][0-9]*s", time_limit)), "capture time limit must be whole seconds")
    expected_argv = [
        "xcrun", "xctrace", "record", "--template", "${TRACE_TEMPLATE}",
        "--device", "${TRACE_DEVICE}", "--attach", str(pid), "--time-limit",
        time_limit, "--run-name", SIGNPOST_NAME, "--output", "${TRACE_BUNDLE}",
        "--no-prompt",
    ]
    require(
        all(not item.startswith("/") for item in argv),
        "capture argv contains a real filesystem path",
    )
    require(argv == expected_argv, "capture argv differs from the public allowlist")


def validate_app_records(records_document: Any, run_metadata: Any, identity: Any) -> None:
    require_exact_keys(records_document, {"schema", "run_uuid", "records"}, "app_records")
    require(
        records_document.get("schema") == "public-w8-trace-app-record-set-v2",
        "app record-set schema mismatch",
    )
    require(
        records_document.get("run_uuid") == run_metadata["run_uuid"],
        "app record-set run UUID mismatch",
    )
    records = records_document.get("records")
    require(isinstance(records, list), "app records must be an array")
    required_events = (
        "prerequisites_begin",
        "smoke_complete",
        "warmup_complete",
        "measured_session_ready",
        "measured_request_begin",
        "measured_request_end",
    )
    for event in required_events:
        require(
            sum(record.get("event") == event for record in records if isinstance(record, dict)) == 1,
            f"app record-set must contain exactly one {event}",
        )
    require(len(records) == len(required_events), "app record-set contains an unknown or duplicate event")
    for index, record in enumerate(records):
        require(isinstance(record, dict), f"app record {index} must be an object")
        event = record.get("event")
        expected_fields = APP_EVENT_FIELDS.get(event)
        require(expected_fields is not None, f"app record {index} has an unknown event")
        require_exact_keys(record, APP_BASE_FIELDS | expected_fields, f"app record {index}")
        require(
            record.get("run_uuid") == run_metadata["run_uuid"]
            and record.get("schema") == "public-w8-trace-confirmation-app-record-v2",
            "app record-set mixes schemas or run UUIDs",
        )
        require_int(record.get("pid"), f"app.{event}.pid", minimum=1)
        if event in ("smoke_complete", "warmup_complete", "measured_request_end"):
            require_int(record.get("input_tokens"), f"app.{event}.input_tokens", minimum=1)
            for field in ("cached_input_tokens", "emitted_tokens", "reasoning_tokens"):
                require_int(record.get(field), f"app.{event}.{field}")
            first_token = require_number(
                record.get("time_to_first_token_seconds"),
                f"app.{event}.time_to_first_token_seconds",
            )
            total = require_number(record.get("total_seconds"), f"app.{event}.total_seconds")
            require(first_token <= total, f"app.{event} first-token time exceeds total time")
    prerequisite = next(record for record in records if record["event"] == "prerequisites_begin")
    measured_session = next(
        record for record in records if record["event"] == "measured_session_ready"
    )
    measured_begin = next(record for record in records if record["event"] == "measured_request_begin")
    terminal = next(record for record in records if record["event"] == "measured_request_end")
    ordered_records = [next(record for record in records if record["event"] == event) for event in required_events]
    ordered_indices = [records.index(record) for record in ordered_records]
    require(ordered_indices == sorted(ordered_indices), "app prerequisite records are out of order")
    ordered_times = [
        require_utc_timestamp(record.get("wall_clock_utc"), f"app.{record['event']}.wall_clock_utc")
        for record in ordered_records
    ]
    require(
        all(left <= right for left, right in zip(ordered_times, ordered_times[1:])),
        "app prerequisite timestamps are out of order",
    )
    require(ordered_times[-2] < ordered_times[-1], "measured request interval is not positive")
    require(
        all(record.get("pid") == run_metadata["pid"] for record in ordered_records),
        "app-side PID mismatch",
    )
    require(
        measured_session["wall_clock_utc"] <= measured_begin["wall_clock_utc"],
        "measured session was not ready before the measured request",
    )
    require(
        prerequisite.get("artifact_repository") == identity["artifact"]["repository"]
        and prerequisite.get("artifact_revision") == identity["artifact"]["revision"]
        and prerequisite.get("artifact_source_hash") == identity["artifact"]["source_hash"],
        "app-side artifact identity mismatch",
    )
    require(
        prerequisite.get("app_bundle_identifier") == identity["app"]["bundle_identifier"],
        "app-side bundle identifier mismatch",
    )
    require(
        prerequisite.get("app_executable_sha256") == identity["app"]["executable_sha256"],
        "installed app executable differs from the sealed Release app",
    )
    require(
        prerequisite.get("coreai_source_revision") == COREAI_SOURCE_REVISION,
        "app-side Core AI source revision mismatch",
    )
    for field in (
        "device_model",
        "device_identifier_class",
        "os_version",
        "os_build",
        "thermal_state",
        "low_power_mode_enabled",
    ):
        require(
            prerequisite.get(field) == run_metadata[field],
            f"app-side {field} differs from run metadata",
        )
    require(
        measured_begin.get("prompt_sha256") == MEASURED_PROMPT_SHA256
        and terminal.get("prompt_sha256") == MEASURED_PROMPT_SHA256,
        "measured prompt hash mismatch",
    )
    require(
        terminal.get("terminal_state") == run_metadata["terminal_state"]
        and terminal.get("input_tokens") == run_metadata["input_tokens"]
        and terminal.get("emitted_tokens") == run_metadata["emitted_tokens"],
        "app terminal record differs from run metadata",
    )


def validate_export_record(
    export: Any,
    run_metadata: Any,
    signposts: Any,
    mpsgraph: Any,
    ane: Any,
) -> None:
    require_exact_keys(
        export,
        {
            "schema", "created_utc", "run_number", "trace_bundle_sha256", "commands",
            "toc", "exports", "xcode_version", "xcode_build", "instruments_version",
            "instruments_build",
        },
        "export",
    )
    require(
        export.get("schema") == "public-w8-trace-export-command-v2",
        "export command record schema mismatch",
    )
    require_utc_timestamp(export.get("created_utc"), "export.created_utc")
    require(export.get("trace_bundle_sha256") == run_metadata["trace_sha256"], "trace hash mismatch")
    for field in ("xcode_version", "xcode_build", "instruments_version", "instruments_build"):
        require(
            export.get(field) == run_metadata[field],
            f"export {field} differs from the sealed toolchain",
        )
    require_int(export.get("run_number"), "export.run_number", minimum=1)
    require_exact_keys(export.get("toc"), {"path", "sha256"}, "export.toc")
    require(export["toc"]["path"] == "trace-toc.xml", "export TOC path mismatch")
    require_sha256(export["toc"].get("sha256"), "export.toc.sha256")
    exports = export.get("exports")
    require_exact_keys(
        exports,
        {"signposts", "mpsgraph", "ane", "process_info", "odie_profile"},
        "export.exports",
    )
    source_tables = {
        "signposts": signposts,
        "mpsgraph": mpsgraph,
        "ane": ane,
    }
    for role in ("signposts", "mpsgraph", "ane", "process_info", "odie_profile"):
        item = exports.get(role)
        require_exact_keys(item, {"schema", "path", "sha256"}, f"export.exports.{role}")
        require_string(item.get("schema"), f"export.exports.{role}.schema")
        require(
            item.get("path") == f"{role}.xml",
            f"export.exports.{role}.path mismatch",
        )
        digest = require_sha256(item.get("sha256"), f"export.exports.{role}.sha256")
        if role in source_tables:
            require(
                source_tables[role].get("source_export_sha256") == digest,
                f"canonical {role} table does not identify its raw export",
            )
        if role == "odie_profile":
            require(
                run_metadata["odie_profile_export_sha256"] == digest,
                "run metadata does not identify the retained ODIEProfile export",
            )
    commands = export.get("commands")
    require(
        isinstance(commands, list)
        and len(commands) == 6
        and all(
            isinstance(command, list)
            and all(isinstance(item, str) for item in command)
            for command in commands
        ),
        "export command record must retain one TOC and five table commands",
    )
    flattened = [item for command in commands for item in command]
    require("${TRACE_BUNDLE}" in flattened, "export commands omit the trace placeholder")
    require(
        any(item.startswith("${EXPORT_DIRECTORY}/") for item in flattened),
        "export commands omit the export-directory placeholder",
    )
    run_number = export["run_number"]
    expected_commands = [[
        "xcrun", "xctrace", "export", "--input", "${TRACE_BUNDLE}", "--toc",
        "--output", "${EXPORT_DIRECTORY}/trace-toc.xml",
    ]]
    for role in ("signposts", "mpsgraph", "ane", "process_info", "odie_profile"):
        xpath = (
            f'/trace-toc/run[@number="{run_number}"]/data/'
            f'table[@schema="{exports[role]["schema"]}"]'
        )
        expected_commands.append([
            "xcrun", "xctrace", "export", "--input", "${TRACE_BUNDLE}",
            "--xpath", xpath, "--output", f"${{EXPORT_DIRECTORY}}/{role}.xml",
        ])
    require(commands == expected_commands, "export commands differ from the public allowlist")


def validate_signpost_table(table: Any, run_uuid: str, pid: int) -> tuple[dict[str, Any], int]:
    require_exact_keys(
        table,
        {
            "schema", "timestamp_unit", "source_export_sha256", "column_mapping_sha256",
            "full_table_sha256", "excluded_other_process_count", "rows",
        },
        "signposts",
    )
    require(
        table.get("schema") == "ane-v2-public-canonical-signpost-table-v2",
        "signpost table schema mismatch",
    )
    require(table.get("timestamp_unit") == "ns", "signpost timestamps must be integer ns")
    require_sha256(table.get("source_export_sha256"), "signposts.source_export_sha256")
    require_sha256(table.get("column_mapping_sha256"), "signposts.column_mapping_sha256")
    require_sha256(table.get("full_table_sha256"), "signposts.full_table_sha256")
    hidden_count = require_int(
        table.get("excluded_other_process_count"),
        "signposts.excluded_other_process_count",
    )
    rows = table.get("rows")
    require(isinstance(rows, list), "signpost rows must be an array")
    signpost_fields = {
        "row_id", "subsystem", "category", "name", "run_uuid", "pid",
        "start_ns", "duration_ns", "terminal_state",
    }
    for index, candidate in enumerate(rows):
        require_exact_keys(candidate, signpost_fields, f"signposts row {index}")
        require_string(candidate.get("row_id"), f"signposts row {index}.row_id")
        for field in (
            "subsystem", "category", "name", "run_uuid", "terminal_state"
        ):
            require_string(candidate.get(field), f"signposts row {index}.{field}")
        candidate_pid = require_int(candidate.get("pid"), f"signposts row {index}.pid", minimum=1)
        require(candidate_pid == pid, f"signpost PID mismatch at row {index}")
        require_int(candidate.get("start_ns"), f"signposts row {index}.start_ns")
        require_int(candidate.get("duration_ns"), f"signposts row {index}.duration_ns", minimum=1)
    frozen_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and row.get("subsystem") == SIGNPOST_SUBSYSTEM
        and row.get("category") == SIGNPOST_CATEGORY
        and row.get("name") == SIGNPOST_NAME
    ]
    require(
        len(frozen_rows) == 1,
        f"expected exactly one frozen signpost interval, found {len(frozen_rows)}",
    )
    row = frozen_rows[0]
    require_uuid(row.get("run_uuid"), "signpost.run_uuid")
    require(row["run_uuid"].lower() == run_uuid, "signpost run UUID mismatch")
    require_int(row.get("pid"), "signpost.pid", minimum=1)
    require(row["pid"] == pid, "signpost PID mismatch")
    start_ns = require_int(row.get("start_ns"), "signpost.start_ns")
    duration_ns = require_int(row.get("duration_ns"), "signpost.duration_ns", minimum=1)
    require_string(row.get("row_id"), "signpost.row_id")
    require(
        row.get("terminal_state") in ("completed", "error"),
        "signpost terminal state must be completed or error",
    )
    return {**row, "start_ns": start_ns, "duration_ns": duration_ns}, hidden_count


INTERVAL_FIELDS = (
    "row_id",
    "start_ns",
    "duration_ns",
    "program_label",
    "channel",
    "state",
    "process",
    "pid",
    "native_identifier",
)


def validate_interval_table(
    table: Any, role: str, target_pid: int
) -> tuple[list[dict[str, Any]], str | None, int]:
    require_exact_keys(
        table,
        {
            "schema", "table_role", "timestamp_unit", "source_export_sha256",
            "column_mapping_sha256", "full_table_sha256",
            "excluded_other_process_count", "native_identifier_name", "rows",
        },
        role,
    )
    require(
        table.get("schema") == "ane-v2-public-canonical-interval-table-v2",
        f"{role} table schema mismatch",
    )
    require(table.get("table_role") == role, f"{role} table role mismatch")
    require(table.get("timestamp_unit") == "ns", f"{role} timestamps must be integer ns")
    require_sha256(table.get("source_export_sha256"), f"{role}.source_export_sha256")
    require_sha256(table.get("column_mapping_sha256"), f"{role}.column_mapping_sha256")
    require_sha256(table.get("full_table_sha256"), f"{role}.full_table_sha256")
    hidden_count = require_int(
        table.get("excluded_other_process_count"),
        f"{role}.excluded_other_process_count",
    )
    native_name = table.get("native_identifier_name")
    require(
        native_name is None or (isinstance(native_name, str) and bool(native_name)),
        f"{role}.native_identifier_name must be null or a non-empty string",
    )
    rows = table.get("rows")
    require(isinstance(rows, list), f"{role} rows must be an array")
    validated: list[dict[str, Any]] = []
    row_ids: set[str] = set()
    for index, row in enumerate(rows):
        require_exact_keys(row, set(INTERVAL_FIELDS), f"{role} row {index}")
        row_id = require_string(row["row_id"], f"{role}[{index}].row_id")
        require(row_id not in row_ids, f"duplicate {role} row_id: {row_id}")
        row_ids.add(row_id)
        start_ns = require_int(row["start_ns"], f"{role}[{index}].start_ns")
        duration_ns = require_int(
            row["duration_ns"], f"{role}[{index}].duration_ns", minimum=1
        )
        pid = require_int(row["pid"], f"{role}[{index}].pid", minimum=1)
        require(pid == target_pid, f"{role}[{index}] is not owned by the target PID")
        for field in ("program_label", "channel", "state", "process"):
            require(isinstance(row[field], str), f"{role}[{index}].{field} must be a string")
        native = row["native_identifier"]
        require(
            native is None
            or (isinstance(native, (str, int)) and not isinstance(native, bool)),
            f"{role}[{index}].native_identifier must be null, string, or integer",
        )
        validated.append(
            {**row, "start_ns": start_ns, "duration_ns": duration_ns, "pid": pid}
        )
    return validated, native_name, hidden_count


def filter_to_owned_window(
    rows: Iterable[dict[str, Any]], *, pid: int, begin_ns: int, end_ns: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for row in rows:
        reasons = []
        row_end = row["start_ns"] + row["duration_ns"]
        if row["pid"] != pid:
            reasons.append("wrong_pid")
        if row["start_ns"] < begin_ns:
            reasons.append("starts_before_run_begin")
        if row_end > end_ns:
            reasons.append("ends_after_run_end")
        analyzed = {
            **row,
            "relative_start_ns": row["start_ns"] - begin_ns,
            "end_ns": row_end,
        }
        if reasons:
            excluded.append({"reasons": reasons, "row": analyzed})
        else:
            eligible.append(analyzed)
    return sorted(eligible, key=row_sort_key), sorted(
        excluded, key=lambda item: row_sort_key(item["row"])
    )


def row_sort_key(row: dict[str, Any]) -> bytes:
    return canonical_json_bytes(row)


def exclusion_reason_counts(excluded: list[dict[str, Any]]) -> dict[str, int]:
    counts: collections.Counter[str] = collections.Counter()
    for item in excluded:
        counts.update(item["reasons"])
    return dict(sorted(counts.items()))


def public_exclusion_reason_counts(
    excluded: list[dict[str, Any]], hidden_other_process_count: int
) -> dict[str, int]:
    counts = collections.Counter(exclusion_reason_counts(excluded))
    if hidden_other_process_count:
        counts["wrong_pid"] += hidden_other_process_count
    return dict(sorted(counts.items()))


def selected_key_mode(
    mps_rows: list[dict[str, Any]],
    ane_rows: list[dict[str, Any]],
    mps_native_name: str | None,
    ane_native_name: str | None,
) -> str:
    if (
        mps_rows
        and ane_rows
        and mps_native_name is not None
        and mps_native_name == ane_native_name
        and all(row["native_identifier"] is not None for row in mps_rows)
        and all(row["native_identifier"] is not None for row in ane_rows)
    ):
        return "native_identifier_relative_start_duration"
    return "relative_start_duration_fallback"


def join_key(row: dict[str, Any], mode: str) -> tuple[Any, ...]:
    if mode == "native_identifier_relative_start_duration":
        native = row["native_identifier"]
        # Preserve JSON scalar type so integer 7 never silently equals string "7".
        native_typed = ("integer", native) if isinstance(native, int) else ("string", native)
        return (native_typed, row["relative_start_ns"], row["duration_ns"])
    return (row["relative_start_ns"], row["duration_ns"])


def key_json(key: tuple[Any, ...], mode: str) -> dict[str, Any]:
    if mode == "native_identifier_relative_start_duration":
        native_typed, relative_start_ns, duration_ns = key
        return {
            "native_identifier": {"type": native_typed[0], "value": native_typed[1]},
            "relative_start_ns": relative_start_ns,
            "duration_ns": duration_ns,
        }
    relative_start_ns, duration_ns = key
    return {"relative_start_ns": relative_start_ns, "duration_ns": duration_ns}


def exact_multiset_join(
    mps_rows: list[dict[str, Any]], ane_rows: list[dict[str, Any]], mode: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    mps_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = collections.defaultdict(list)
    ane_by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = collections.defaultdict(list)
    for row in mps_rows:
        mps_by_key[join_key(row, mode)].append(row)
    for row in ane_rows:
        ane_by_key[join_key(row, mode)].append(row)

    matched: list[dict[str, Any]] = []
    unmatched_mps: list[dict[str, Any]] = []
    unmatched_ane: list[dict[str, Any]] = []
    multiplicities: list[dict[str, Any]] = []
    keys = sorted(set(mps_by_key) | set(ane_by_key), key=lambda key: canonical_json_bytes(key_json(key, mode)))
    for key in keys:
        left = sorted(mps_by_key.get(key, []), key=row_sort_key)
        right = sorted(ane_by_key.get(key, []), key=row_sort_key)
        match_count = min(len(left), len(right))
        key_value = key_json(key, mode)
        for index in range(match_count):
            matched.append(
                {"key": key_value, "mpsgraph_row": left[index], "ane_row": right[index]}
            )
        unmatched_mps.extend(left[match_count:])
        unmatched_ane.extend(right[match_count:])
        multiplicities.append(
            {
                "key": key_value,
                "mpsgraph": len(left),
                "ane": len(right),
                "matched": match_count,
                "unmatched_mpsgraph": len(left) - match_count,
                "unmatched_ane": len(right) - match_count,
            }
        )
    return matched, unmatched_mps, unmatched_ane, multiplicities


def analyze(
    *,
    signposts: Any,
    mpsgraph: Any,
    ane: Any,
    identity: Any,
    run_metadata: Any,
    capture_command: Any,
    export_command: Any,
    app_records: Any,
    input_hashes: dict[str, str],
    source_root: Path | None = None,
) -> dict[str, Any]:
    validate_identity(identity)
    if source_root is not None:
        verify_current_source_identity(identity, source_root)
    run_uuid, pid = validate_run_metadata(
        run_metadata, identity, input_hashes["identity_record"]
    )
    require(
        run_metadata["capture_command_record_sha256"] == input_hashes["capture_command"],
        "run metadata does not identify the supplied capture command record",
    )
    require(
        run_metadata["export_command_record_sha256"] == input_hashes["export_command"],
        "run metadata does not identify the supplied export command record",
    )
    require(
        run_metadata["app_records_sha256"] == input_hashes["app_records"],
        "run metadata does not identify the supplied app records",
    )
    validate_capture_record(capture_command, run_metadata, pid)
    validate_app_records(app_records, run_metadata, identity)
    validate_export_record(export_command, run_metadata, signposts, mpsgraph, ane)
    signpost, _hidden_signpost_count = validate_signpost_table(signposts, run_uuid, pid)
    require(
        signpost["terminal_state"] == run_metadata["terminal_state"],
        "signpost and run metadata terminal states differ",
    )
    begin_ns = signpost["start_ns"]
    end_ns = begin_ns + signpost["duration_ns"]
    mps_rows, mps_native_name, hidden_mps_count = validate_interval_table(
        mpsgraph, "mpsgraph_program", pid
    )
    ane_rows, ane_native_name, hidden_ane_count = validate_interval_table(
        ane, "ane_prediction", pid
    )
    eligible_mps, excluded_mps = filter_to_owned_window(
        mps_rows, pid=pid, begin_ns=begin_ns, end_ns=end_ns
    )
    eligible_ane, excluded_ane = filter_to_owned_window(
        ane_rows, pid=pid, begin_ns=begin_ns, end_ns=end_ns
    )
    mode = selected_key_mode(
        eligible_mps, eligible_ane, mps_native_name, ane_native_name
    )
    matched, unmatched_mps, unmatched_ane, multiplicities = exact_multiset_join(
        eligible_mps, eligible_ane, mode
    )
    duplicate_multiplicities = [
        record
        for record in multiplicities
        if record["mpsgraph"] > 1 or record["ane"] > 1
    ]
    conclusion = PERMITTED_CONCLUSION if matched else None
    return {
        "schema": "public-w8-ane-trace-analysis-v3",
        "protocol": "paper/EXPERIMENT_PROTOCOL_V1.md#3-ane-trace-confirmation",
        "protocol_amendment": AMENDMENT_RELATIVE_PATH,
        "run_uuid": run_uuid,
        "pid": pid,
        "owned_window": {
            "run_begin_ns": begin_ns,
            "run_end_ns": end_ns,
            "duration_ns": signpost["duration_ns"],
            "terminal_state": signpost["terminal_state"],
            "signpost": signpost,
        },
        "selected_key_mode": mode,
        "native_identifier_names": {
            "mpsgraph_program": mps_native_name,
            "ane_prediction": ane_native_name,
        },
        "counts": {
            "mpsgraph_exported": len(mps_rows) + hidden_mps_count,
            "ane_exported": len(ane_rows) + hidden_ane_count,
            "mpsgraph_eligible": len(eligible_mps),
            "ane_eligible": len(eligible_ane),
            "matched": len(matched),
            "unmatched_mpsgraph": len(unmatched_mps),
            "unmatched_ane": len(unmatched_ane),
            "excluded_mpsgraph": len(excluded_mps) + hidden_mps_count,
            "excluded_ane": len(excluded_ane) + hidden_ane_count,
        },
        "matched_rows": matched,
        "unmatched_mpsgraph_rows": unmatched_mps,
        "unmatched_ane_rows": unmatched_ane,
        "exclusion_reason_counts": {
            "mpsgraph": public_exclusion_reason_counts(excluded_mps, hidden_mps_count),
            "ane": public_exclusion_reason_counts(excluded_ane, hidden_ane_count),
        },
        "key_multiplicities": multiplicities,
        "duplicate_multiplicities": duplicate_multiplicities,
        "permitted_conclusion": conclusion,
        "claim_exclusions": CLAIM_EXCLUSIONS,
        "input_sha256": input_hashes,
        "run_environment": {
            "device_model": run_metadata["device_model"],
            "device_identifier_class": run_metadata["device_identifier_class"],
            "os_version": run_metadata["os_version"],
            "os_build": run_metadata["os_build"],
            "coreai_build": run_metadata["coreai_build"],
            "thermal_state": run_metadata["thermal_state"],
            "low_power_mode_enabled": run_metadata["low_power_mode_enabled"],
            "xcode_version": run_metadata["xcode_version"],
            "xcode_build": run_metadata["xcode_build"],
            "instruments_version": run_metadata["instruments_version"],
            "instruments_build": run_metadata["instruments_build"],
            "capture_start_utc": run_metadata["capture_start_utc"],
            "capture_end_utc": run_metadata["capture_end_utc"],
            "trace_start_utc": run_metadata["trace_start_utc"],
            "trace_end_utc": run_metadata["trace_end_utc"],
            "input_tokens": run_metadata["input_tokens"],
            "emitted_tokens": run_metadata["emitted_tokens"],
            "terminal_state": run_metadata["terminal_state"],
        },
        "identity_summary": {
            "artifact_repository": identity["artifact"]["repository"],
            "artifact_revision": identity["artifact"]["revision"],
            "root_metadata_version": identity["artifact"]["root_metadata_version"],
            "root_metadata_sha256": identity["artifact"]["root_metadata_sha256"],
            "published_sha256s_file_sha256": identity["artifact"][
                "published_sha256s_file_sha256"
            ],
            "artifact_manifest_sha256": identity["artifact"]["manifest_sha256"],
            "source_aimodel_sha256": identity["artifact"]["source_hash"],
            "compiled_main_sha256": identity["artifact"]["main_h16p_sha256"],
            "artifact_producer": identity["artifact"]["artifact_producer"],
            "compiled_bundle_file_list_sha256": identity["artifact"][
                "compiled_bundle_file_list_sha256"
            ],
            "source_commit": identity["source"]["git_commit"],
            "runtime_repository": identity["runtime"]["repository"],
            "runtime_base_revision": identity["runtime"]["base_revision"],
            "runtime_patch_sha256": identity["runtime"]["patch_sha256"],
            "patched_runtime_files": identity["runtime"]["patched_files"],
            "app_bundle_identifier": identity["app"]["bundle_identifier"],
            "app_bundle_manifest_sha256": identity["app"]["bundle_manifest_sha256"],
            "xcode_build": identity["toolchain"]["xcode_build"],
            "instruments_build": identity["toolchain"]["instruments_build"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signposts", type=Path, required=True)
    parser.add_argument("--mpsgraph", type=Path, required=True)
    parser.add_argument("--ane", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--capture-command", type=Path, required=True)
    parser.add_argument("--export-command", type=Path, required=True)
    parser.add_argument("--app-records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = {
        "signposts": args.signposts,
        "mpsgraph": args.mpsgraph,
        "ane": args.ane,
        "identity_record": args.identity,
        "run_metadata": args.run_metadata,
        "capture_command": args.capture_command,
        "export_command": args.export_command,
        "app_records": args.app_records,
    }
    input_hashes = {name: sha256_file(path) for name, path in paths.items()}
    result = analyze(
        signposts=load_json(args.signposts),
        mpsgraph=load_json(args.mpsgraph),
        ane=load_json(args.ane),
        identity=load_json(args.identity),
        run_metadata=load_json(args.run_metadata),
        capture_command=load_json(args.capture_command),
        export_command=load_json(args.export_command),
        app_records=load_json(args.app_records),
        input_hashes=input_hashes,
        source_root=Path(__file__).resolve().parents[3],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_json_bytes(result))
    print(f"wrote {args.output} sha256={sha256_file(args.output)}")


if __name__ == "__main__":
    main()
