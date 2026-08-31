#!/usr/bin/env python3
"""Build and cross-check the dynamic metadata record after trace capture."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


EXPECTED_PROMPT = "Reply with exactly PUBLIC-W8-TRACE-OK and no other text. /no_think"
EXPECTED_PROMPT_SHA256 = hashlib.sha256(EXPECTED_PROMPT.encode("utf-8")).hexdigest()
COREAI_SOURCE_REVISION = "04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a"
COREAI_BUILD_RE = re.compile(r"^[0-9]+(?:\.[0-9]+){2,}$")
VERSION_TOKEN_RE = re.compile(r"(?<![0-9.])([0-9]+(?:\.[0-9]+){2,})(?![0-9.])")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def trace_bundle_sha256(root: Path) -> str:
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            target = os.readlink(path).encode("utf-8")
            digest = hashlib.sha256(b"SYMLINK\0" + target).hexdigest()
            records.append(f"{digest}\t{len(target)}\tsymlink\t{relative}\n")
        elif path.is_file():
            records.append(
                f"{sha256_file(path)}\t{path.stat().st_size}\tfile\t{relative}\n"
            )
    if not records:
        raise ValueError("trace bundle contains no files")
    return hashlib.sha256("".join(records).encode("utf-8")).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_private_identity_binding(private_path: Path, public_path: Path) -> None:
    if private_path.is_symlink():
        raise ValueError("private identity record must not be a symlink")
    status = private_path.stat()
    if not stat.S_ISREG(status.st_mode):
        raise ValueError("private identity record must be a regular file")
    mode = stat.S_IMODE(status.st_mode)
    if mode != 0o600:
        raise ValueError("private identity record must have mode 0600")
    private = load(private_path)
    if set(private) != {"schema", "public_identity_sha256", "code_signing"}:
        raise ValueError("private identity fields differ from schema v2")
    if private.get("schema") != "private-w8-trace-signing-identity-v2":
        raise ValueError("private identity schema mismatch")
    if private.get("public_identity_sha256") != sha256_file(public_path):
        raise ValueError("private identity does not bind the supplied public identity")
    public = load(public_path)
    if (
        public.get("schema") != "public-w8-trace-identity-v4"
        or public.get("app", {}).get("code_signing", {}).get("signed") is not True
    ):
        raise ValueError("public identity does not record a verified signature")
    signing = private.get("code_signing")
    if not isinstance(signing, dict) or set(signing) != {
        "identifier", "team_identifier", "authorities", "verification"
    }:
        raise ValueError("private signing identity fields differ from schema v2")
    if not all(isinstance(signing.get(field), str) and signing[field] for field in (
        "identifier", "team_identifier"
    )):
        raise ValueError("private signing identity is incomplete")
    if signing["identifier"] != public["app"].get("bundle_identifier"):
        raise ValueError("private signing Identifier differs from the public bundle ID")
    authorities = signing.get("authorities")
    if not isinstance(authorities, list) or not authorities or not all(
        isinstance(item, str) and item for item in authorities
    ):
        raise ValueError("private signing authority chain is incomplete")
    verification = signing.get("verification")
    expected_argv = ["codesign", "--verify", "--deep", "--strict", "${APP_BUNDLE}"]
    if not isinstance(verification, dict) or set(verification) != {
        "argv", "return_code", "verified"
    }:
        raise ValueError("private signature verification fields differ from schema v2")
    if (
        verification.get("argv") != expected_argv
        or verification.get("return_code") != 0
        or verification.get("verified") is not True
    ):
        raise ValueError("strict signature verification did not succeed")


def one_event(records, event):
    matches = [record for record in records if record.get("event") == event]
    if len(matches) != 1:
        raise ValueError(f"expected one {event} app record, found {len(matches)}")
    return matches[0]


def parse_utc(value, field):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an ISO-8601 UTC timestamp")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp") from error


def verify_odie_profile(path: Path, export: dict, coreai_build: str) -> str:
    if not path.is_file():
        raise ValueError(f"ODIEProfile export is not a file: {path}")
    odie_sha = sha256_file(path)
    odie_record = export.get("exports", {}).get("odie_profile", {})
    if odie_record.get("sha256") != odie_sha:
        raise ValueError("ODIEProfile export differs from the export command record")
    if not isinstance(coreai_build, str) or COREAI_BUILD_RE.fullmatch(coreai_build) is None:
        raise ValueError("Core AI build must be an exact dotted numeric version")
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise ValueError(f"ODIEProfile export is not valid XML: {error}") from error
    references = {}
    for element in root.iter():
        identifier = element.attrib.get("id")
        if identifier is None:
            continue
        if identifier in references:
            raise ValueError(f"ODIEProfile export has duplicate XML id {identifier!r}")
        references[identifier] = element

    def resolved_text(element, seen=None):
        seen = set() if seen is None else set(seen)
        while "ref" in element.attrib:
            reference = element.attrib["ref"]
            if reference in seen:
                raise ValueError("ODIEProfile export contains an XML reference cycle")
            seen.add(reference)
            if reference not in references:
                raise ValueError(f"ODIEProfile export has unresolved XML ref {reference!r}")
            element = references[reference]
        parts = [element.text or ""]
        for child in element:
            parts.append(resolved_text(child, seen))
            parts.append(child.tail or "")
        return "".join(parts)

    observed_versions: set[str] = set()
    structural_names = ("build", "version", "coreai")
    row_names = {"row", "record", "entry", "item"}
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1].lower()
        direct_values = [resolved_text(element), *element.attrib.values()]
        for key, value in element.attrib.items():
            key_name = key.rsplit("}", 1)[-1].lower()
            if any(label in key_name for label in structural_names) or "coreai" in value.lower():
                observed_versions.update(VERSION_TOKEN_RE.findall(value))
        direct_text = " ".join(direct_values)
        if any(label in local_name for label in structural_names) or "coreai" in direct_text.lower():
            observed_versions.update(VERSION_TOKEN_RE.findall(direct_text))
        if local_name in row_names:
            row_text = " ".join(resolved_text(child) for child in element)
            lowered = row_text.lower()
            if "coreai" in lowered and ("build" in lowered or "version" in lowered):
                observed_versions.update(VERSION_TOKEN_RE.findall(row_text))
    if coreai_build not in observed_versions:
        raise ValueError("Core AI build is absent as an exact structured ODIEProfile value")
    return odie_sha


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--private-identity", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--capture-command", type=Path, required=True)
    parser.add_argument("--export-command", type=Path, required=True)
    parser.add_argument("--odie-profile-export", type=Path, required=True)
    parser.add_argument("--app-records", type=Path, required=True)
    parser.add_argument("--coreai-build", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    identity = load(args.identity)
    capture = load(args.capture_command)
    export = load(args.export_command)
    app_record_set = load(args.app_records)
    if identity.get("schema") != "public-w8-trace-identity-v4":
        raise SystemExit("identity schema mismatch")
    if capture.get("schema") != "public-w8-trace-capture-command-v2":
        raise SystemExit("capture command schema mismatch")
    if export.get("schema") != "public-w8-trace-export-command-v2":
        raise SystemExit("export command schema mismatch")
    if app_record_set.get("schema") != "public-w8-trace-app-record-set-v2":
        raise SystemExit("app record-set schema mismatch")
    try:
        verify_private_identity_binding(args.private_identity, args.identity)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    records = app_record_set.get("records")
    if not isinstance(records, list):
        raise SystemExit("app record set has no records array")

    prerequisite = one_event(records, "prerequisites_begin")
    smoke = one_event(records, "smoke_complete")
    warmup = one_event(records, "warmup_complete")
    measured_session = one_event(records, "measured_session_ready")
    measured_begin = one_event(records, "measured_request_begin")
    measured_end = one_event(records, "measured_request_end")
    run_uuid = app_record_set.get("run_uuid")
    if any(record.get("run_uuid") != run_uuid for record in records):
        raise SystemExit("app record set mixes run UUIDs")
    pids = {record.get("pid") for record in records if "pid" in record}
    if len(pids) != 1:
        raise SystemExit(f"app records do not have one PID: {sorted(pids)}")
    pid = next(iter(pids))
    ordered_records = [
        prerequisite,
        smoke,
        warmup,
        measured_session,
        measured_begin,
        measured_end,
    ]
    ordered_indices = [records.index(record) for record in ordered_records]
    if ordered_indices != sorted(ordered_indices):
        raise SystemExit("app prerequisite records are out of order")
    ordered_times = [
        parse_utc(record.get("wall_clock_utc"), f"app.{record.get('event')}.wall_clock_utc")
        for record in ordered_records
    ]
    if any(left > right for left, right in zip(ordered_times, ordered_times[1:])):
        raise SystemExit("app prerequisite timestamps are out of order")
    if ordered_times[-2] >= ordered_times[-1]:
        raise SystemExit("measured request interval is not positive")
    if any(record.get("pid") != pid for record in ordered_records):
        raise SystemExit("app prerequisite records do not all carry the owned PID")
    if capture.get("attached_pid") != pid:
        raise SystemExit("capture command attached to a different PID")
    if measured_begin.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise SystemExit("measured request prompt hash mismatch")
    if measured_end.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise SystemExit("terminal measured prompt hash mismatch")
    if measured_end.get("terminal_state") != "completed":
        raise SystemExit("failed measured requests are retained but are not an admissible confirmation run")
    if prerequisite.get("coreai_source_revision") != COREAI_SOURCE_REVISION:
        raise SystemExit("app-side Core AI source revision mismatch")
    if prerequisite.get("artifact_revision") != identity["artifact"]["revision"]:
        raise SystemExit("app-side artifact revision mismatch")
    if prerequisite.get("artifact_repository") != identity["artifact"]["repository"]:
        raise SystemExit("app-side artifact repository mismatch")
    if prerequisite.get("artifact_source_hash") != identity["artifact"]["source_hash"]:
        raise SystemExit("app-side artifact sourceHash mismatch")
    if prerequisite.get("app_bundle_identifier") != identity["app"]["bundle_identifier"]:
        raise SystemExit("installed bundle identifier mismatch")
    if prerequisite.get("app_executable_sha256") != identity["app"]["executable_sha256"]:
        raise SystemExit("installed app executable differs from the sealed Release app")

    trace_sha = trace_bundle_sha256(args.trace)
    if export.get("trace_bundle_sha256") != trace_sha:
        raise SystemExit("export command refers to a different trace bundle")
    try:
        odie_sha = verify_odie_profile(
            args.odie_profile_export, export, args.coreai_build
        )
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    toolchain = identity["toolchain"]
    record = {
        "schema": "public-w8-trace-run-metadata-v2",
        "run_uuid": run_uuid,
        "pid": pid,
        "device_model": prerequisite.get("device_model"),
        "device_identifier_class": prerequisite.get("device_identifier_class"),
        "os_version": prerequisite.get("os_version"),
        "os_build": prerequisite.get("os_build"),
        "xcode_version": toolchain["xcode_version"],
        "xcode_build": toolchain["xcode_build"],
        "instruments_version": toolchain["instruments_version"],
        "instruments_build": toolchain["instruments_build"],
        "coreai_build": args.coreai_build,
        "thermal_state": prerequisite.get("thermal_state"),
        "low_power_mode_enabled": prerequisite.get("low_power_mode_enabled"),
        "capture_start_utc": capture.get("started_utc"),
        "capture_end_utc": capture.get("ended_utc"),
        "trace_start_utc": measured_begin.get("wall_clock_utc"),
        "trace_end_utc": measured_end.get("wall_clock_utc"),
        "input_tokens": measured_end.get("input_tokens"),
        "emitted_tokens": measured_end.get("emitted_tokens"),
        "terminal_state": measured_end.get("terminal_state"),
        "trace_sha256": trace_sha,
        "capture_command_record_sha256": sha256_file(args.capture_command),
        "export_command_record_sha256": sha256_file(args.export_command),
        "app_records_sha256": sha256_file(args.app_records),
        "odie_profile_export_sha256": odie_sha,
        "identity_record_sha256": sha256_file(args.identity),
        "installed_bundle_identifier": prerequisite.get("app_bundle_identifier"),
        "identity_binding_verified": True,
        "protocol_amendment_sha256": identity["source"]["amendment_file_sha256"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output} sha256={sha256_file(args.output)}")


if __name__ == "__main__":
    main()
