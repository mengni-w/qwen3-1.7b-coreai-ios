#!/usr/bin/env python3
"""Recursively verify the fixed, reviewed ANE publication bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any


PUBLIC_FILES = {
    "identity.json",
    "capture-command.json",
    "export-command.json",
    "app-records.json",
    "run-metadata.json",
    "signposts.json",
    "mpsgraph.json",
    "ane.json",
    "signpost-map.json",
    "mpsgraph-map.json",
    "ane-map.json",
    "ane-analysis.json",
}
FORBIDDEN_KEYS = {
    "identifier",
    "team_identifier",
    "authority",
    "authorities",
    "device_identifier_sha256",
    "device_udid",
    "udid",
    "raw_stdout",
    "raw_stderr",
    "raw_error",
    "stdout",
    "stderr",
    "stdout_sha256",
    "stderr_sha256",
    "error",
}
PRIVATE_STRING_PREFIXES = (
    "Apple Development:",
    "Apple Distribution:",
    "Developer ID Application:",
    "iPhone Developer:",
    "private-w8-trace-",
)
PRIVATE_PATH_RE = re.compile(r"(?:file://|~/?|/(?:Users|private|Volumes|var|tmp)/)")
RAW_PRIVATE_PATH_RE = re.compile(
    rb"(?:file://|~/?|/(?:Users|private|Volumes|var|tmp)/)",
    re.IGNORECASE,
)
RAW_PRIVATE_TOKEN_RE = re.compile(
    rb"(?:Apple Development:|Apple Distribution:|Developer ID Application:|"
    rb"iPhone Developer:|private-w8-trace-|raw[_ -]?(?:stdout|stderr|error)|"
    rb"(?:TeamIdentifier|Identifier|Authority)=)",
    re.IGNORECASE,
)
DEVICE_IDENTIFIER_RE = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}(?![0-9A-Fa-f])")
RAW_DEVICE_IDENTIFIER_RE = re.compile(
    rb"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}(?![0-9A-Fa-f])"
)


class PublicationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PublicationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def scan_public_bytes(raw: bytes, name: str) -> None:
    if RAW_PRIVATE_PATH_RE.search(raw):
        raise PublicationError(f"{name} raw bytes contain a private host path")
    if RAW_PRIVATE_TOKEN_RE.search(raw):
        raise PublicationError(f"{name} raw bytes contain a private token")
    if RAW_DEVICE_IDENTIFIER_RE.search(raw):
        raise PublicationError(f"{name} raw bytes contain a device identifier")


def load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        scan_public_bytes(raw, path.name)
        text = raw.decode("utf-8")
        return json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except PublicationError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicationError(f"cannot read public JSON {path.name}: {error}") from error


def scan_public_value(value: Any, location: str) -> None:
    if isinstance(value, dict):
        forbidden = sorted(set(value) & FORBIDDEN_KEYS)
        if forbidden:
            raise PublicationError(f"{location} contains private keys: {forbidden}")
        for key, item in value.items():
            scan_public_value(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_public_value(item, f"{location}[{index}]")
    elif isinstance(value, str):
        if any(
            value.lower().startswith(prefix.lower())
            for prefix in PRIVATE_STRING_PREFIXES
        ):
            raise PublicationError(f"{location} contains a private signing value or schema")
        if PRIVATE_PATH_RE.search(value):
            raise PublicationError(f"{location} contains a private host path")
        if DEVICE_IDENTIFIER_RE.search(value):
            raise PublicationError(f"{location} contains a device identifier")


def load_analyzer(directory: Path):
    path = directory / "analyze_trace.py"
    spec = importlib.util.spec_from_file_location("ane_v2_publication_analyzer", path)
    if spec is None or spec.loader is None:
        raise PublicationError("cannot load the ANE analyzer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_canonicalizer(directory: Path):
    path = directory / "canonicalize_xctrace.py"
    spec = importlib.util.spec_from_file_location("ane_v2_publication_canonicalizer", path)
    if spec is None or spec.loader is None:
        raise PublicationError("cannot load the ANE canonicalizer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_bundle(
    bundle: Path,
    analyzer: Any,
    canonicalizer: Any | None = None,
    source_root: Path | None = None,
) -> None:
    if bundle.is_symlink() or not bundle.is_dir():
        raise PublicationError("--bundle must be a directory")
    paths: dict[str, Path] = {}
    for path in bundle.rglob("*"):
        relative = path.relative_to(bundle).as_posix()
        if path.is_symlink() or not path.is_file():
            raise PublicationError(f"public bundle contains a non-regular entry: {relative}")
        paths[relative] = path
    actual = set(paths)
    if actual != PUBLIC_FILES:
        raise PublicationError(
            "public bundle file set differs from the allowlist; "
            f"unknown={sorted(actual - PUBLIC_FILES)} missing={sorted(PUBLIC_FILES - actual)}"
        )
    documents = {name: load_json(path) for name, path in paths.items()}
    for name, document in documents.items():
        scan_public_value(document, name)

    if canonicalizer is None:
        canonicalizer = load_canonicalizer(Path(__file__).resolve().parent)
    for role, mapping_name, expected_mapping_role in (
        ("signposts", "signpost-map.json", "signposts"),
        ("mpsgraph", "mpsgraph-map.json", "mpsgraph_program"),
        ("ane", "ane-map.json", "ane_prediction"),
    ):
        try:
            canonicalizer.validate_mapping(
                documents[mapping_name], expected_role=expected_mapping_role
            )
        except canonicalizer.MappingError as error:
            raise PublicationError(f"{mapping_name} rejected: {error}") from error
        if documents[f"{role}.json"].get("column_mapping_sha256") != canonical_json_sha256(
            documents[mapping_name]
        ):
            raise PublicationError(f"{role} table does not bind its published mapping")

    inputs = {
        "signposts": documents["signposts.json"],
        "mpsgraph": documents["mpsgraph.json"],
        "ane": documents["ane.json"],
        "identity": documents["identity.json"],
        "run_metadata": documents["run-metadata.json"],
        "capture_command": documents["capture-command.json"],
        "export_command": documents["export-command.json"],
        "app_records": documents["app-records.json"],
        "input_hashes": {
            "signposts": sha256_file(paths["signposts.json"]),
            "mpsgraph": sha256_file(paths["mpsgraph.json"]),
            "ane": sha256_file(paths["ane.json"]),
            "identity_record": sha256_file(paths["identity.json"]),
            "run_metadata": sha256_file(paths["run-metadata.json"]),
            "capture_command": sha256_file(paths["capture-command.json"]),
            "export_command": sha256_file(paths["export-command.json"]),
            "app_records": sha256_file(paths["app-records.json"]),
        },
    }
    try:
        expected_analysis = analyzer.canonical_json_bytes(
            analyzer.analyze(
                **inputs,
                source_root=(
                    source_root
                    if source_root is not None
                    else Path(__file__).resolve().parents[3]
                ),
            )
        )
    except analyzer.ValidationError as error:
        raise PublicationError(f"public analyzer input rejected: {error}") from error
    if paths["ane-analysis.json"].read_bytes() != expected_analysis:
        raise PublicationError("published analysis is not the deterministic analyzer output")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args()
    evidence_directory = Path(__file__).resolve().parent
    analyzer = load_analyzer(evidence_directory)
    canonicalizer = load_canonicalizer(evidence_directory)
    try:
        validate_bundle(
            args.bundle.resolve(),
            analyzer,
            canonicalizer,
            Path(__file__).resolve().parents[3],
        )
    except PublicationError as error:
        raise SystemExit(str(error)) from error
    print("PUBLIC_BUNDLE_PRIVACY_OK")


if __name__ == "__main__":
    main()
