#!/usr/bin/env python3
"""Export the five required xctrace tables without silently selecting schemas."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROLES = ("signposts", "mpsgraph", "ane", "process_info", "odie_profile")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def public_command(command: list[str], trace: str, output_dir: Path) -> list[str]:
    public: list[str] = []
    output_prefix = str(output_dir.resolve()) + os.sep
    for item in command:
        if item == trace:
            public.append("${TRACE_BUNDLE}")
        elif item.startswith(output_prefix):
            public.append("${EXPORT_DIRECTORY}/" + item.removeprefix(output_prefix))
        else:
            public.append(item)
    return public


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


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def verify_schemas_in_toc(toc_path: Path, run_number: int, schemas: dict[str, str]) -> None:
    try:
        root = ET.parse(toc_path).getroot()
    except ET.ParseError as error:
        raise SystemExit(f"cannot parse exported trace TOC: {error}") from error
    runs = [
        element
        for element in root.iter()
        if local_name(element.tag) == "run"
        and element.attrib.get("number") == str(run_number)
    ]
    if len(runs) != 1:
        raise SystemExit(f"TOC contains {len(runs)} runs numbered {run_number}")
    available = [
        element.attrib.get("schema")
        for element in runs[0].iter()
        if local_name(element.tag) == "table" and element.attrib.get("schema")
    ]
    for role, schema in schemas.items():
        if available.count(schema) != 1:
            raise SystemExit(
                f"TOC run {run_number} contains {available.count(schema)} tables "
                f"for {role} schema {schema!r}"
            )


def schema_value(value: str) -> str:
    if not value or '"' in value or "'" in value:
        raise argparse.ArgumentTypeError("schema must be a non-empty quote-free string")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-number", type=int, default=1)
    for role in ROLES:
        parser.add_argument(f"--{role.replace('_', '-')}-schema", type=schema_value, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.trace.is_dir() or args.trace.suffix != ".trace":
        raise SystemExit("--trace must be an existing .trace bundle")
    if args.output_dir.exists():
        raise SystemExit(f"refusing existing output directory: {args.output_dir}")
    if args.run_number <= 0:
        raise SystemExit("--run-number must be positive")
    args.output_dir.mkdir(parents=True)
    trace = str(args.trace.resolve())
    commands: list[list[str]] = []

    toc_path = args.output_dir / "trace-toc.xml"
    toc_command = [
        "xcrun",
        "xctrace",
        "export",
        "--input",
        trace,
        "--toc",
        "--output",
        str(toc_path.resolve()),
    ]
    commands.append(toc_command)
    run(toc_command)

    schemas = {role: getattr(args, f"{role}_schema") for role in ROLES}
    if len(set(schemas.values())) != len(ROLES):
        raise SystemExit("the five required roles must use five distinct TOC schemas")
    verify_schemas_in_toc(toc_path, args.run_number, schemas)
    exports: dict[str, dict[str, str]] = {}
    for role in ROLES:
        output = args.output_dir / f"{role}.xml"
        xpath = (
            f'/trace-toc/run[@number="{args.run_number}"]/data/'
            f'table[@schema="{schemas[role]}"]'
        )
        command = [
            "xcrun",
            "xctrace",
            "export",
            "--input",
            trace,
            "--xpath",
            xpath,
            "--output",
            str(output.resolve()),
        ]
        commands.append(command)
        run(command)
        if not output.is_file() or output.stat().st_size == 0:
            raise SystemExit(f"empty required export: {role}")
        exports[role] = {
            "schema": schemas[role],
            "path": output.name,
            "sha256": sha256_file(output),
        }

    record = {
        "schema": "public-w8-trace-export-command-v2",
        "created_utc": utc_now(),
        "run_number": args.run_number,
        "trace_bundle_sha256": trace_bundle_sha256(args.trace),
        "commands": [
            public_command(command, trace, args.output_dir) for command in commands
        ],
        "toc": {"path": toc_path.name, "sha256": sha256_file(toc_path)},
        "exports": exports,
        **toolchain_identity(),
    }
    record_path = args.output_dir / "export-command.json"
    record_path.write_text(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"export command record: {record_path}")


if __name__ == "__main__":
    main()
