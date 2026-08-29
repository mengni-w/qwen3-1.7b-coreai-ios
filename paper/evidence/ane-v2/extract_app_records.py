#!/usr/bin/env python3
"""Extract one UUID-owned, allowlisted set of ANE_TRACE_V2_JSON app records."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


MARKER = "ANE_TRACE_V2_JSON="
REQUIRED_EVENTS = (
    "prerequisites_begin",
    "smoke_complete",
    "warmup_complete",
    "measured_session_ready",
    "measured_request_begin",
    "measured_request_end",
)
BASE_FIELDS = {"schema", "event", "run_uuid"}
GENERATION_FIELDS = {
    "cached_input_tokens",
    "emitted_tokens",
    "input_tokens",
    "reasoning_tokens",
    "time_to_first_token_seconds",
    "total_seconds",
}
EVENT_FIELDS = {
    "prerequisites_begin": {
        "app_bundle_identifier",
        "app_executable_sha256",
        "artifact_repository",
        "artifact_revision",
        "artifact_source_hash",
        "coreai_source_revision",
        "device_identifier_class",
        "device_model",
        "low_power_mode_enabled",
        "os_build",
        "os_version",
        "pid",
        "thermal_state",
        "wall_clock_utc",
    },
    "smoke_complete": GENERATION_FIELDS | {"pid", "wall_clock_utc"},
    "warmup_complete": GENERATION_FIELDS | {"pid", "wall_clock_utc"},
    "measured_session_ready": {"pid", "wall_clock_utc"},
    "measured_request_begin": {"pid", "prompt_sha256", "wall_clock_utc"},
}
MEASURED_END_COMPLETED_FIELDS = GENERATION_FIELDS | {
    "pid",
    "prompt_sha256",
    "terminal_state",
    "wall_clock_utc",
}
MEASURED_END_ERROR_FIELDS = {
    "pid",
    "prompt_sha256",
    "terminal_state",
    "wall_clock_utc",
}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def validate_public_record(record: object, line_number: int) -> dict:
    if not isinstance(record, dict):
        raise SystemExit(f"line {line_number} trace record is not an object")
    if record.get("schema") != "public-w8-trace-confirmation-app-record-v2":
        raise SystemExit(f"line {line_number} has an unexpected app-record schema")
    event = record.get("event")
    if event == "measured_request_end":
        state = record.get("terminal_state")
        if state == "completed":
            expected = BASE_FIELDS | MEASURED_END_COMPLETED_FIELDS
        elif state == "error":
            expected = BASE_FIELDS | MEASURED_END_ERROR_FIELDS
        else:
            raise SystemExit(f"line {line_number} has an invalid terminal state")
    else:
        fields = EVENT_FIELDS.get(event)
        if fields is None:
            raise SystemExit(f"line {line_number} has an unknown public trace event")
        expected = BASE_FIELDS | fields
    if set(record) != expected:
        unknown = sorted(set(record) - expected)
        missing = sorted(expected - set(record))
        raise SystemExit(
            f"line {line_number} app-record fields differ from the public allowlist; "
            f"unknown={unknown} missing={missing}"
        )
    run_uuid = record.get("run_uuid")
    if not isinstance(run_uuid, str) or UUID_RE.fullmatch(run_uuid) is None:
        raise SystemExit(f"line {line_number} has an invalid run UUID")
    pid = record.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool) or pid < 1:
        raise SystemExit(f"line {line_number} has an invalid PID")
    if GENERATION_FIELDS <= set(record):
        for field in (
            "cached_input_tokens",
            "emitted_tokens",
            "input_tokens",
            "reasoning_tokens",
        ):
            value = record[field]
            minimum = 1 if field == "input_tokens" else 0
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise SystemExit(
                    f"line {line_number} {field} must be an integer >= {minimum}"
                )
        times = {}
        for field in ("time_to_first_token_seconds", "total_seconds"):
            value = record[field]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
            ):
                raise SystemExit(
                    f"line {line_number} {field} must be a finite non-negative number"
                )
            times[field] = float(value)
        if times["time_to_first_token_seconds"] > times["total_seconds"]:
            raise SystemExit(f"line {line_number} first-token time exceeds total time")
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--run-uuid")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = []
    for number, line in enumerate(args.log.read_text(encoding="utf-8").splitlines(), start=1):
        if MARKER not in line:
            continue
        payload = line.split(MARKER, 1)[1].strip()
        try:
            record = json.loads(payload)
        except json.JSONDecodeError as error:
            raise SystemExit(f"line {number} has an invalid trace JSON record: {error}") from error
        records.append(validate_public_record(record, number))
    if not records:
        raise SystemExit("the log contains no ANE trace app records")
    uuids = sorted({record.get("run_uuid") for record in records})
    if args.run_uuid is None:
        if len(uuids) != 1:
            raise SystemExit(f"log contains multiple run UUIDs; select one: {uuids}")
        run_uuid = uuids[0]
    else:
        run_uuid = args.run_uuid.lower()
        if run_uuid not in uuids:
            raise SystemExit(f"requested run UUID is absent: {run_uuid}")
    selected = [record for record in records if record.get("run_uuid") == run_uuid]
    events = [record.get("event") for record in selected]
    for event in REQUIRED_EVENTS:
        count = events.count(event)
        if count != 1:
            raise SystemExit(f"run {run_uuid} has {count} records for required event {event}")
    output = {
        "schema": "public-w8-trace-app-record-set-v2",
        "run_uuid": run_uuid,
        "records": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
