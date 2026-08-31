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
ARTIFACT_REVISION = "75bbe06906cb5d953e602e3e4fb6364187c81822"
ROOT_METADATA_VERSION = "0.2"
ROOT_METADATA_SHA256 = "c12e3b1035dd8c009d5b8d8572d0ad829236871edd10c02ef35d89644c5289d1"
PUBLISHED_SHA256SUMS_SHA256 = "11b44a503983182f99f5de2a458947ac1bfb9b68bfaafd39a5b13feb4d430be9"
BENCHMARK_MANIFEST_NAME = "benchmark-artifact-manifest.json"
BENCHMARK_MANIFEST_SHA256 = "91c68e82e280a36d39aaeef9b8726ab1d59e52760b6f970db67c334a674d47b2"
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
PATCHED_RUNTIME_FILES = (
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
)
PROJECT_RELATIVE_PATH = "companion/CoreAIQwen17Companion.xcodeproj/project.pbxproj"
PACKAGE_RESOLVED_RELATIVE_PATH = (
    "companion/CoreAIQwen17Companion.xcodeproj/project.xcworkspace/"
    "xcshareddata/swiftpm/Package.resolved"
)
APP_SOURCE_RELATIVE_PATH = (
    "companion/CoreAIQwen17Companion/CoreAIQwen17CompanionApp.swift"
)
PROTOCOL_RELATIVE_PATH = "paper/EXPERIMENT_PROTOCOL_V1.md"
PRIOR_AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_1.md"
ARTIFACT_AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_2.md"
AMENDMENT_RELATIVE_PATH = "paper/ANE_V2_AMENDMENT_3.md"
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


def artifact_files(root: Path) -> list[dict[str, Any]]:
    require(root.is_dir(), f"artifact root is not a directory: {root}")
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        require(".cache" not in Path(relative).parts, "Hugging Face transport cache remains")
        require(not path.is_symlink(), f"artifact contains a symbolic link: {relative}")
        if path.is_file() and relative != BENCHMARK_MANIFEST_NAME:
            records.append(
                {
                    "path": relative,
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    require(bool(records), "artifact root has no payload files")
    return records


def published_sha256s(
    artifact_dir: Path,
    files: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = artifact_dir / "SHA256SUMS"
    require(path.is_file() and not path.is_symlink(), "public artifact has no regular SHA256SUMS")
    file_digests = None if files is None else {record["path"]: record["sha256"] for record in files}
    observed_sums_sha = (
        sha256_file(path) if file_digests is None else file_digests.get("SHA256SUMS")
    )
    require(
        observed_sums_sha == PUBLISHED_SHA256SUMS_SHA256,
        "published SHA256SUMS file hash mismatch",
    )
    records: list[dict[str, str]] = []
    paths: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  \./(.+)", line)
        require(match is not None, f"invalid SHA256SUMS line {line_number}")
        digest, relative = match.groups()
        relative_path = Path(relative)
        require(
            not relative.startswith("/")
            and all(part not in ("", ".", "..") for part in relative_path.parts),
            f"invalid SHA256SUMS path: {relative}",
        )
        require(relative not in paths, f"duplicate SHA256SUMS path: {relative}")
        paths.add(relative)
        payload = artifact_dir / relative_path
        require(
            payload.is_file() and not payload.is_symlink(),
            f"SHA256SUMS path is not a regular file: {relative}",
        )
        observed = sha256_file(payload) if file_digests is None else file_digests.get(relative)
        require(observed == digest, f"published payload digest mismatch: {relative}")
        records.append({"path": relative, "sha256": digest})
    require(bool(records), "public SHA256SUMS is empty")
    return (
        {
            "sha256": PUBLISHED_SHA256SUMS_SHA256,
            "entries": len(records),
            "matchingEntries": len(records),
            "acknowledgedMismatches": [],
        },
        records,
    )


def validate_compiled_identity(artifact_dir: Path, files: list[dict[str, Any]]) -> dict[str, str]:
    by_path = {record["path"]: record for record in files}
    root_metadata_path = artifact_dir / "metadata.json"
    require(
        root_metadata_path.is_file() and not root_metadata_path.is_symlink(),
        "root metadata.json is missing",
    )
    require(
        by_path.get("metadata.json", {}).get("sha256") == ROOT_METADATA_SHA256,
        "root metadata hash mismatch",
    )
    root_metadata = json.loads(root_metadata_path.read_text(encoding="utf-8"))
    require(
        str(root_metadata.get("metadata_version", "")) == ROOT_METADATA_VERSION,
        "root metadata_version mismatch",
    )
    assets = root_metadata.get("assets")
    require(isinstance(assets, dict), "root metadata assets are missing")
    compiled_relative = assets.get("main")
    require(
        isinstance(compiled_relative, str)
        and compiled_relative
        and not compiled_relative.startswith("/")
        and all(part not in ("", ".", "..") for part in compiled_relative.split("/")),
        "root metadata main asset path is invalid",
    )
    compilation = root_metadata.get("compilation")
    require(isinstance(compilation, dict), "root metadata compilation identity is missing")
    require(
        compilation.get("source_aimodel_sha256") == ARTIFACT_SOURCE_HASH,
        "root metadata source artifact hash mismatch",
    )
    require(
        compilation.get("compiled_main_sha256") == MAIN_H16P_SHA256,
        "root metadata compiled main hash mismatch",
    )
    require(
        compilation.get("compiled_bundle_file_list_sha256")
        == COMPILED_BUNDLE_FILE_LIST_SHA256,
        "root metadata compiled-bundle fingerprint mismatch",
    )

    compiled_dir = artifact_dir / compiled_relative
    compiled_metadata_path = compiled_dir / "metadata.json"
    main_path = compiled_dir / "main-h16p.mlirb"
    main_hash_path = compiled_dir / "main.hash"
    require(compiled_metadata_path.is_file(), "compiled asset metadata.json is missing")
    compiled_metadata = json.loads(compiled_metadata_path.read_text(encoding="utf-8"))
    require(
        str(compiled_metadata.get("sourceHash", "")).lower() == ARTIFACT_SOURCE_HASH,
        "compiled asset sourceHash mismatch",
    )
    require(
        compiled_metadata.get("producer") == ARTIFACT_PRODUCER,
        "compiled asset producer mismatch",
    )
    require(main_path.is_file(), "compiled main-h16p.mlirb is missing")
    require(main_hash_path.is_file(), "compiled main.hash is missing")
    require(main_hash_path.read_bytes().hex() == MAIN_H16P_SHA256, "compiled main.hash mismatch")

    main_relative = (Path(compiled_relative) / "main-h16p.mlirb").as_posix()
    require(
        by_path.get(main_relative, {}).get("sha256") == MAIN_H16P_SHA256,
        "artifact manifest compiled-main identity mismatch",
    )
    return {
        "root_metadata_version": ROOT_METADATA_VERSION,
        "root_metadata_sha256": ROOT_METADATA_SHA256,
        "source_hash": ARTIFACT_SOURCE_HASH,
        "main_h16p_sha256": MAIN_H16P_SHA256,
        "artifact_producer": ARTIFACT_PRODUCER,
        "compiled_bundle_file_list_sha256": COMPILED_BUNDLE_FILE_LIST_SHA256,
    }


def benchmark_manifest_bytes(artifact_dir: Path) -> bytes:
    files = artifact_files(artifact_dir)
    validate_compiled_identity(artifact_dir, files)
    published_summary, _ = published_sha256s(artifact_dir, files)
    document = {
        "schemaVersion": 2,
        "repository": ARTIFACT_REPOSITORY,
        "revision": ARTIFACT_REVISION,
        "publishedSHA256SUMS": published_summary,
        "files": files,
    }
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def prepare_downloaded_artifact(artifact_dir: Path) -> None:
    artifact_dir = artifact_dir.resolve()
    manifest_path = artifact_dir / BENCHMARK_MANIFEST_NAME
    require(not manifest_path.exists(), f"refusing existing artifact manifest: {manifest_path}")
    encoded = benchmark_manifest_bytes(artifact_dir)
    require(
        sha256_bytes(encoded) == BENCHMARK_MANIFEST_SHA256,
        "generated benchmark artifact manifest hash mismatch",
    )
    write_new(manifest_path, encoded, mode=0o644)
    print(f"wrote artifact manifest {manifest_path} sha256={BENCHMARK_MANIFEST_SHA256}")


def validate_benchmark_manifest(
    artifact_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    manifest_path = artifact_dir / BENCHMARK_MANIFEST_NAME
    require(
        manifest_path.is_file() and not manifest_path.is_symlink(),
        "benchmark artifact manifest is missing",
    )
    require(
        sha256_file(manifest_path) == BENCHMARK_MANIFEST_SHA256,
        "benchmark artifact manifest hash mismatch",
    )
    expected_bytes = benchmark_manifest_bytes(artifact_dir)
    require(manifest_path.read_bytes() == expected_bytes, "benchmark artifact manifest contents differ")
    document = json.loads(expected_bytes)
    _, published_records = published_sha256s(artifact_dir, document["files"])
    return document["files"], document["publishedSHA256SUMS"], published_records


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
            PRIOR_AMENDMENT_RELATIVE_PATH,
            ARTIFACT_AMENDMENT_RELATIVE_PATH,
            AMENDMENT_RELATIVE_PATH,
        ],
        cwd=repo,
    ).stdout.decode("utf-8", errors="strict")
    require(status == "", "ANE confirmation sources are not clean; commit them before sealing")
    project = repo / PROJECT_RELATIVE_PATH
    package_resolved = repo / PACKAGE_RESOLVED_RELATIVE_PATH
    swift_source = repo / APP_SOURCE_RELATIVE_PATH
    protocol = repo / PROTOCOL_RELATIVE_PATH
    prior_amendment = repo / PRIOR_AMENDMENT_RELATIVE_PATH
    artifact_amendment = repo / ARTIFACT_AMENDMENT_RELATIVE_PATH
    amendment = repo / AMENDMENT_RELATIVE_PATH
    runtime_patch = repo / RUNTIME_PATCH_RELATIVE_PATH
    require(project.is_file(), f"missing project file: {project}")
    require(
        f'repositoryURL = "{COREAI_REPOSITORY}";' in project.read_text(encoding="utf-8"),
        "Xcode project Core AI repository URL mismatch",
    )
    require(package_resolved.is_file(), f"missing Package.resolved: {package_resolved}")
    require(swift_source.is_file(), f"missing instrumented source: {swift_source}")
    require(protocol.is_file(), f"missing experiment protocol: {protocol}")
    require(prior_amendment.is_file(), f"missing prior protocol amendment: {prior_amendment}")
    require(
        artifact_amendment.is_file(),
        f"missing artifact protocol amendment: {artifact_amendment}",
    )
    require(amendment.is_file(), f"missing protocol amendment: {amendment}")
    require(
        runtime_patch.is_file() and not runtime_patch.is_symlink(),
        f"missing regular runtime patch: {runtime_patch}",
    )
    require(sha256_file(runtime_patch) == RUNTIME_PATCH_SHA256, "runtime patch hash mismatch")
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
    source_paths.extend(sorted((repo / "companion").rglob("*.plist")))
    source_paths.extend(sorted((repo / "paper/evidence/ane-v2").glob("*.py")))
    source_paths.extend(sorted((repo / "paper/evidence/ane-v2").glob("*.sh")))
    source_paths.extend([prior_amendment, artifact_amendment, amendment, runtime_patch])
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
        "prior_amendment_file": PRIOR_AMENDMENT_RELATIVE_PATH,
        "prior_amendment_file_sha256": sha256_file(prior_amendment),
        "artifact_amendment_file": ARTIFACT_AMENDMENT_RELATIVE_PATH,
        "artifact_amendment_file_sha256": sha256_file(artifact_amendment),
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


def runtime_identity(repo: Path, checkout: Path) -> dict[str, Any]:
    require(checkout.is_dir() and not checkout.is_symlink(), "Core AI checkout is invalid")
    patch = repo / RUNTIME_PATCH_RELATIVE_PATH
    require(
        patch.is_file() and not patch.is_symlink(),
        "frozen Core AI runtime patch is not a regular file",
    )
    require(sha256_file(patch) == RUNTIME_PATCH_SHA256, "runtime patch hash mismatch")

    head = run(["git", "rev-parse", "HEAD"], cwd=checkout).stdout.decode().strip()
    require(head == COREAI_SOURCE_REVISION, "Core AI checkout revision mismatch")
    changed_paths = sorted(
        line
        for line in run(
            ["git", "diff", "--name-only", "HEAD", "--"], cwd=checkout
        ).stdout.decode("utf-8", errors="strict").splitlines()
        if line
    )
    expected_paths = sorted(record["path"] for record in PATCHED_RUNTIME_FILES)
    require(
        changed_paths == expected_paths,
        "Core AI checkout contains changes outside the frozen runtime patch",
    )
    untracked = run(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=checkout
    ).stdout.decode("utf-8", errors="strict").splitlines()
    require(not untracked, "Core AI checkout contains untracked files")
    reverse = subprocess.run(
        ["git", "apply", "--check", "--reverse", str(patch)],
        cwd=checkout,
        capture_output=True,
        check=False,
    )
    require(reverse.returncode == 0, "frozen Core AI runtime patch is not applied exactly")

    patched_files: list[dict[str, str]] = []
    for expected in PATCHED_RUNTIME_FILES:
        relative = expected["path"]
        base_bytes = run(["git", "show", f"HEAD:{relative}"], cwd=checkout).stdout
        require(
            sha256_bytes(base_bytes) == expected["base_sha256"],
            f"Core AI base source hash mismatch: {relative}",
        )
        current = checkout / relative
        require(
            current.is_file() and not current.is_symlink(),
            f"Core AI patched source is not a regular file: {relative}",
        )
        require(
            sha256_file(current) == expected["patched_sha256"],
            f"Core AI patched source hash mismatch: {relative}",
        )
        patched_files.append(dict(expected))

    return {
        "repository": COREAI_REPOSITORY,
        "base_revision": COREAI_SOURCE_REVISION,
        "patch_file": RUNTIME_PATCH_RELATIVE_PATH,
        "patch_sha256": RUNTIME_PATCH_SHA256,
        "patched_files": patched_files,
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
    files, published_summary, published_sums = validate_benchmark_manifest(artifact_dir)
    payloads = [
        {
            "path": record["path"],
            "kind": "file",
            "size_bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for record in files
    ]
    return {
        "repository": ARTIFACT_REPOSITORY,
        "revision": ARTIFACT_REVISION,
        "root_metadata_version": ROOT_METADATA_VERSION,
        "root_metadata_sha256": ROOT_METADATA_SHA256,
        "source_hash": ARTIFACT_SOURCE_HASH,
        "main_h16p_sha256": MAIN_H16P_SHA256,
        "artifact_producer": ARTIFACT_PRODUCER,
        "compiled_bundle_file_list_sha256": COMPILED_BUNDLE_FILE_LIST_SHA256,
        "manifest_format": "benchmark-artifact-manifest-json-v2",
        "manifest_sha256": BENCHMARK_MANIFEST_SHA256,
        "payloads": payloads,
        "published_sha256s": published_sums,
        "published_sha256s_file_sha256": published_summary["sha256"],
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
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-artifact-dir", type=Path)
    mode.add_argument("--repo", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--coreai-checkout", type=Path)
    parser.add_argument("--publication-dir", type=Path)
    parser.add_argument("--public-output", type=Path)
    parser.add_argument("--private-output", type=Path)
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
    if args.prepare_artifact_dir is not None:
        require(
            all(
                value is None
                for value in (
                    args.artifact_dir,
                    args.app,
                    args.coreai_checkout,
                    args.publication_dir,
                    args.public_output,
                    args.private_output,
                )
            ),
            "artifact preparation does not accept identity-sealing arguments",
        )
        prepare_downloaded_artifact(args.prepare_artifact_dir)
        return

    require(args.repo is not None, "--repo is required for identity sealing")
    for name in (
        "artifact_dir",
        "app",
        "coreai_checkout",
        "publication_dir",
        "public_output",
        "private_output",
    ):
        require(getattr(args, name) is not None, f"--{name.replace('_', '-')} is required")
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
        "schema": "public-w8-trace-identity-v4",
        "artifact": artifact_identity(args.artifact_dir.resolve()),
        "source": git_identity(repo),
        "runtime": runtime_identity(repo, args.coreai_checkout.resolve()),
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
