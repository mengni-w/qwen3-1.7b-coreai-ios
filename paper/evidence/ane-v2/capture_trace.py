#!/usr/bin/env python3
"""Record an exact-PID Core AI + Points of Interest trace on the target device."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def toolchain_identity() -> dict[str, str]:
    xcode = subprocess.run(
        ["xcodebuild", "-version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    if len(xcode) < 2 or not xcode[0].startswith("Xcode ") or not xcode[1].startswith(
        "Build version "
    ):
        raise SystemExit("unexpected xcodebuild -version output")
    xctrace = subprocess.run(
        ["xcrun", "xctrace", "version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    match = re.fullmatch(r"xctrace version (.+) \(([^()]+)\)", xctrace)
    if match is None:
        raise SystemExit("unexpected xctrace version output")
    return {
        "xcode_version": xcode[0].removeprefix("Xcode "),
        "xcode_build": xcode[1].removeprefix("Build version "),
        "instruments_version": match.group(1),
        "instruments_build": match.group(2),
    }


def stream(pipe, sink) -> None:
    for chunk in iter(lambda: pipe.readline(), b""):
        sink.buffer.write(chunk)
        sink.buffer.flush()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--command-record", type=Path, required=True)
    parser.add_argument("--time-limit", default="90s")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.pid <= 0:
        raise SystemExit("--pid must be positive")
    if not args.template.is_file():
        raise SystemExit(f"trace template does not exist: {args.template}")
    if args.output.exists():
        raise SystemExit(f"refusing existing trace output: {args.output}")
    if args.command_record.exists():
        raise SystemExit(f"refusing existing command record: {args.command_record}")
    device = os.environ.get("TRACE_DEVICE_UDID")
    if not device:
        raise SystemExit("set TRACE_DEVICE_UDID to the physical device identifier")

    toolchain = toolchain_identity()
    command = [
        "xcrun",
        "xctrace",
        "record",
        "--template",
        str(args.template.resolve()),
        "--device",
        device,
        "--attach",
        str(args.pid),
        "--time-limit",
        args.time_limit,
        "--run-name",
        "PUBLIC_W8_TRACE_CONFIRMATION_V1",
        "--output",
        str(args.output.resolve()),
        "--no-prompt",
    ]
    public_command = [
        "xcrun",
        "xctrace",
        "record",
        "--template",
        "${TRACE_TEMPLATE}",
        "--device",
        "${TRACE_DEVICE}",
        "--attach",
        str(args.pid),
        "--time-limit",
        args.time_limit,
        "--run-name",
        "PUBLIC_W8_TRACE_CONFIRMATION_V1",
        "--output",
        "${TRACE_BUNDLE}",
        "--no-prompt",
    ]
    started = utc_now()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None and process.stderr is not None
    threads = [
        threading.Thread(target=stream, args=(process.stdout, sys.stdout)),
        threading.Thread(target=stream, args=(process.stderr, sys.stderr)),
    ]
    for thread in threads:
        thread.start()
    return_code = process.wait()
    for thread in threads:
        thread.join()
    ended = utc_now()
    record = {
        "schema": "public-w8-trace-capture-command-v2",
        "argv": public_command,
        "template_sha256": sha256_file(args.template),
        "attached_pid": args.pid,
        "started_utc": started,
        "ended_utc": ended,
        "return_code": return_code,
        **toolchain,
    }
    args.command_record.parent.mkdir(parents=True, exist_ok=True)
    args.command_record.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if return_code != 0:
        raise SystemExit(return_code)
    if not args.output.is_dir():
        raise SystemExit("xctrace returned success without producing a .trace bundle")
    print(f"capture command record: {args.command_record}")


if __name__ == "__main__":
    main()
