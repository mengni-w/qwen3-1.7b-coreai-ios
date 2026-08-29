#!/usr/bin/env python3
"""Seal the pre-capture artifact, source, Release app, and toolchain identities."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
from pathlib import Path
from typing import Any


ARTIFACT_REPOSITORY = "massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p"
ARTIFACT_REVISION = "466ebe2e5cec125fa113ea71503add41bba581a8"
ARTIFACT_SOURCE_HASH = "5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73"
MAIN_H16P_SHA256 = "a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f"
COREAI_SOURCE_REVISION = "04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a"
PROJECT_RELATIVE_PATH = "companion/CoreAIQwen17Companion.xcodeproj/project.pbxproj"
PACKAGE_RESOLVED_RELATIVE_PATH = (
    "companion/CoreAIQwen17Companion.xcodeproj/project.xcworkspace/"
    "xcshareddata/swiftpm/Package.resolved"
)
APP_SOURCE_RELATIVE_PATH = (
    "companion/CoreAIQwen17Companion/CoreAIQwen17CompanionApp.swift"
)
PROTOCOL_RELATIVE_PATH = "paper/EXPERIMENT_PROTOCOL_V1.md"
AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_1.md"
PUBLIC_BUNDLE_IDENTIFIER = "io.massif.PublicW8TraceConfirmation"


class IdentityError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise IdentityError(message)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")
        raise IdentityError(f"command failed ({completed.returncode}): {command!r}\n{stderr}")
    return completed


def canonical_manifest(root: Path, *, exclude_cache: bool) -> tuple[list[dict[str, Any]], str]:
    require(root.is_dir(), f"manifest root is not a directory: {root}")
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if exclude_cache and ".cache" in Path(relative).parts:
            continue
        if path.is_symlink():
            target = os.readlink(path).encode("utf-8")
            records.append(
                {
                    "path": relative,
                    "kind": "symlink",
                    "size_bytes": len(target),
                    "sha256": sha256_bytes(b"SYMLINK\0" + target),
                }
            )
        elif path.is_file():
            records.append(
                {
                    "path": relative,
                    "kind": "file",
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    require(bool(records), f"manifest root has no payload files: {root}")
    manifest_bytes = b"".join(
        (
            f"{record['sha256']}\t{record['size_bytes']}\t{record['kind']}\t{record['path']}\n"
        ).encode("utf-8")
        for record in records
    )
    return records, sha256_bytes(manifest_bytes)


def git_identity(repo: Path) -> dict[str, Any]:
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.decode().strip()
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "cannot resolve a full source commit")
    status = run(
        [
            "git",
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            "companion",
            "paper/evidence/ane-v2",
            PROTOCOL_RELATIVE_PATH,
            AMENDMENT_RELATIVE_PATH,
        ],
        cwd=repo,
    ).stdout.decode("utf-8", errors="strict")
    require(status == "", "ANE confirmation sources are not clean; commit them before sealing")
    project = repo / PROJECT_RELATIVE_PATH
    package_resolved = repo / PACKAGE_RESOLVED_RELATIVE_PATH
    swift_source = repo / APP_SOURCE_RELATIVE_PATH
    protocol = repo / PROTOCOL_RELATIVE_PATH
    amendment = repo / AMENDMENT_RELATIVE_PATH
    require(project.is_file(), f"missing project file: {project}")
    require(package_resolved.is_file(), f"missing Package.resolved: {package_resolved}")
    require(swift_source.is_file(), f"missing instrumented source: {swift_source}")
    require(protocol.is_file(), f"missing experiment protocol: {protocol}")
    require(amendment.is_file(), f"missing protocol amendment: {amendment}")
    resolved = json.loads(package_resolved.read_text(encoding="utf-8"))
    coreai_pins = [
        pin
        for pin in resolved.get("pins", [])
        if pin.get("identity") == "coreai-models"
    ]
    require(len(coreai_pins) == 1, "Package.resolved must contain one coreai-models pin")
    require(
        coreai_pins[0].get("state", {}).get("revision") == COREAI_SOURCE_REVISION,
        "Package.resolved Core AI revision mismatch",
    )
    source_paths = sorted((repo / "companion").rglob("*.swift"))
    source_paths.extend(sorted((repo / "paper/evidence/ane-v2").glob("*.py")))
    source_paths.extend(sorted((repo / "paper/evidence/ane-v2").glob("*.sh")))
    source_paths.append(amendment)
    source_paths.sort(key=lambda path: path.relative_to(repo).as_posix())
    require(swift_source in source_paths, "instrumented Swift source was not discovered")
    return {
        "git_commit": commit,
        "git_status_clean": True,
        "project_file": PROJECT_RELATIVE_PATH,
        "project_file_sha256": sha256_file(project),
        "package_resolved_file": PACKAGE_RESOLVED_RELATIVE_PATH,
        "package_resolved_file_sha256": sha256_file(package_resolved),
        "protocol_file": PROTOCOL_RELATIVE_PATH,
        "protocol_file_sha256": sha256_file(protocol),
        "amendment_file": AMENDMENT_RELATIVE_PATH,
        "amendment_file_sha256": sha256_file(amendment),
        "source_files": [
            {
                "path": path.relative_to(repo).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in source_paths
        ],
    }


def parse_key_value_lines(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), []).append(value.strip())
    return values


def code_signing_identity(
    app_bundle: Path, bundle_identifier: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    # A display record is not proof that the bundle is valid.  Verification is
    # deliberately the first codesign operation so `signed: true` can only be
    # emitted after the strict check succeeds.
    run(["codesign", "--verify", "--deep", "--strict", str(app_bundle)])
    display = run(["codesign", "-d", "--verbose=4", str(app_bundle)])
    display_text = (display.stdout + display.stderr).decode("utf-8", errors="replace")
    values = parse_key_value_lines(display_text)
    entitlements = run(["codesign", "-d", "--entitlements", ":-", str(app_bundle)])
    entitlement_bytes = entitlements.stdout
    if not entitlement_bytes:
        entitlement_bytes = entitlements.stderr
    identifier = (values.get("Identifier") or [""])[0]
    team = (values.get("TeamIdentifier") or [""])[0]
    cdhash = (values.get("CDHash") or [""])[0]
    signature_format = (values.get("Format") or [""])[0]
    authorities = values.get("Authority", [])
    require(identifier != "", "codesign output lacks Identifier")
    require(identifier == bundle_identifier, "codesign Identifier differs from bundle ID")
    require(team not in ("", "not set"), "Release app lacks a signing TeamIdentifier")
    require(cdhash != "", "codesign output lacks CDHash")
    require(signature_format != "", "codesign output lacks Format")
    require(bool(authorities), "codesign output lacks an Authority chain")
    public = {
        "signed": True,
        "cdhash": cdhash,
        "signature_format": signature_format,
        "entitlements_sha256": sha256_bytes(entitlement_bytes),
        "codesign_display_sha256": sha256_bytes(display_text.encode("utf-8")),
    }
    private = {
        "identifier": identifier,
        "team_identifier": team,
        "authorities": authorities,
        "verification": {
            "argv": ["codesign", "--verify", "--deep", "--strict", "${APP_BUNDLE}"],
            "return_code": 0,
            "verified": True,
        },
    }
    return public, private


def app_identity(app_bundle: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    require(app_bundle.is_dir() and app_bundle.suffix == ".app", "--app must be an .app bundle")
    plist_path = app_bundle / "Info.plist"
    require(plist_path.is_file(), "Release app has no Info.plist")
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    executable_name = info.get("CFBundleExecutable")
    bundle_identifier = info.get("CFBundleIdentifier")
    build_configuration = info.get("ANETraceBuildConfiguration")
    require(isinstance(executable_name, str) and executable_name, "Info.plist lacks executable")
    require(isinstance(bundle_identifier, str) and bundle_identifier, "Info.plist lacks bundle ID")
    require(
        bundle_identifier == PUBLIC_BUNDLE_IDENTIFIER,
        f"Release app bundle ID must be {PUBLIC_BUNDLE_IDENTIFIER}",
    )
    require(
        build_configuration == "Release",
        "Info.plist does not identify the sealed app as a Release build",
    )
    executable = app_bundle / executable_name
    require(executable.is_file(), "Release app executable is missing")
    manifest, manifest_sha = canonical_manifest(app_bundle, exclude_cache=False)
    public_signing, private_signing = code_signing_identity(
        app_bundle, bundle_identifier
    )
    public = {
        "configuration": build_configuration,
        "bundle_identifier": bundle_identifier,
        "bundle_manifest_sha256": manifest_sha,
        "bundle_file_count": len(manifest),
        "executable_relative_path": executable.relative_to(app_bundle).as_posix(),
        "executable_sha256": sha256_file(executable),
        "info_plist_sha256": sha256_file(plist_path),
        "code_signing": public_signing,
    }
    return public, private_signing


def artifact_identity(artifact_dir: Path) -> dict[str, Any]:
    payloads, manifest_sha = canonical_manifest(artifact_dir, exclude_cache=True)
    payload_by_path = {item["path"]: item for item in payloads}
    published_sums_path = artifact_dir / "SHA256SUMS"
    require(published_sums_path.is_file(), "public artifact has no SHA256SUMS")
    published_sums: list[dict[str, str]] = []
    for line_number, line in enumerate(
        published_sums_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        require(match is not None, f"invalid SHA256SUMS line {line_number}")
        digest, relative = match.groups()
        require(relative in payload_by_path, f"SHA256SUMS path is missing: {relative}")
        require(
            payload_by_path[relative]["sha256"] == digest,
            f"published payload digest mismatch: {relative}",
        )
        published_sums.append({"path": relative, "sha256": digest})
    require(bool(published_sums), "public SHA256SUMS is empty")
    mains = [item for item in payloads if item["path"].endswith("main-h16p.mlirb")]
    require(len(mains) == 1, f"expected one main-h16p.mlirb, found {len(mains)}")
    require(mains[0]["kind"] == "file", "public compiled main must be a regular file")
    require(mains[0]["sha256"] == MAIN_H16P_SHA256, "public compiled main hash mismatch")
    main_path = artifact_dir / mains[0]["path"]
    metadata_path = main_path.parent / "metadata.json"
    require(metadata_path.is_file(), "compiled asset metadata.json is missing")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source_hash = metadata.get("sourceHash")
    require(
        isinstance(source_hash, str) and source_hash.lower() == ARTIFACT_SOURCE_HASH,
        "public sourceHash mismatch",
    )
    require(
        isinstance(metadata.get("producer"), str) and bool(metadata["producer"]),
        "compiled asset metadata lacks producer identity",
    )
    return {
        "repository": ARTIFACT_REPOSITORY,
        "revision": ARTIFACT_REVISION,
        "source_hash": ARTIFACT_SOURCE_HASH,
        "main_h16p_sha256": MAIN_H16P_SHA256,
        "artifact_producer": metadata.get("producer"),
        "manifest_format": "sha256-tab-size-tab-kind-tab-posix-path-newline-v1",
        "manifest_sha256": manifest_sha,
        "payloads": payloads,
        "published_sha256s": published_sums,
        "published_sha256s_file_sha256": sha256_file(published_sums_path),
    }


def toolchain_identity() -> dict[str, str]:
    xcode_lines = run(["xcodebuild", "-version"]).stdout.decode("utf-8").splitlines()
    require(len(xcode_lines) >= 2 and xcode_lines[0].startswith("Xcode "), "unexpected Xcode version")
    require(xcode_lines[1].startswith("Build version "), "unexpected Xcode build line")
    xctrace = run(["xcrun", "xctrace", "version"]).stdout.decode("utf-8").strip()
    match = re.fullmatch(r"xctrace version (.+) \(([^()]+)\)", xctrace)
    require(match is not None, "unexpected xctrace version output")
    return {
        "xcode_version": xcode_lines[0].removeprefix("Xcode "),
        "xcode_build": xcode_lines[1].removeprefix("Build version "),
        "instruments_version": match.group(1),
        "instruments_build": match.group(2),
        "coreai_source_revision": COREAI_SOURCE_REVISION,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--publication-dir", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    return parser.parse_args()


def is_within(path: Path, directory: Path) -> bool:
    return path == directory or path.is_relative_to(directory)


def validate_output_boundaries(
    *, repo: Path, publication_dir: Path, public_output: Path, private_output: Path
) -> None:
    require(
        is_within(public_output, publication_dir),
        "--public-output must be inside --publication-dir",
    )
    require(
        not is_within(private_output, repo),
        "--private-output must be outside the repository",
    )
    require(
        not is_within(private_output, publication_dir),
        "--private-output must be outside the publication directory",
    )
    require(public_output != private_output, "public and private outputs must differ")


def write_new(path: Path, encoded: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if mode == 0o600 else 0o755)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise
    os.chmod(path, mode)


def main() -> None:
    args = parse_args()
    repo = args.repo.resolve()
    publication_dir = args.publication_dir.resolve()
    public_output = args.public_output.resolve()
    private_output = args.private_output.resolve()
    validate_output_boundaries(
        repo=repo,
        publication_dir=publication_dir,
        public_output=public_output,
        private_output=private_output,
    )
    require(not public_output.exists(), f"refusing existing public output: {public_output}")
    require(not private_output.exists(), f"refusing existing private output: {private_output}")
    public_app, private_signing = app_identity(args.app.resolve())
    public_record = {
        "schema": "public-w8-trace-identity-v2",
        "artifact": artifact_identity(args.artifact_dir.resolve()),
        "source": git_identity(repo),
        "app": public_app,
        "toolchain": toolchain_identity(),
    }
    public_encoded = (
        json.dumps(public_record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    private_record = {
        "schema": "private-w8-trace-signing-identity-v2",
        "public_identity_sha256": sha256_bytes(public_encoded),
        "code_signing": private_signing,
    }
    private_encoded = (
        json.dumps(private_record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    write_new(public_output, public_encoded, mode=0o644)
    try:
        write_new(private_output, private_encoded, mode=0o600)
    except Exception:
        public_output.unlink(missing_ok=True)
        raise
    print(f"wrote public identity {public_output} sha256={sha256_bytes(public_encoded)}")
    print(f"wrote private signing identity {private_output} mode=0600")


if __name__ == "__main__":
    main()
