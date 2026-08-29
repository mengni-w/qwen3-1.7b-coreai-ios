#!/usr/bin/env python3
"""Convert a pinned xctrace XML table to the analyzer's canonical JSON contract.

Xcode table schemas and element positions are recorded explicitly in a mapping
file rather than guessed.  Conversion to integer nanoseconds uses Decimal and
fails if the exported value is not exactly representable in nanoseconds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


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
SIGNPOST_FIELDS = (
    "row_id",
    "subsystem",
    "category",
    "name",
    "run_uuid",
    "pid",
    "start_ns",
    "duration_ns",
    "terminal_state",
)
UNIT_FACTORS = {
    "ns": Decimal(1),
    "us": Decimal(1_000),
    "ms": Decimal(1_000_000),
    "s": Decimal(1_000_000_000),
}
MAPPING_SCHEMA = "ane-v2-xctrace-column-map-v1"
SOURCE_MODES = {"literal", "row_index", "index", "tag"}
COLUMN_SPEC_KEYS = SOURCE_MODES | {
    "attribute",
    "regex",
    "group",
    "null_values",
    "type",
    "unit",
}
SUPPORTED_TYPES = {
    "string",
    "nullable_string",
    "integer",
    "nullable_integer",
    "nanoseconds",
}


class MappingError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MappingError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def validate_mapping(mapping: Any, expected_role: str | None = None) -> None:
    require(isinstance(mapping, dict), "mapping must be an object")
    role = mapping.get("table_role")
    require(role in ("signposts", "mpsgraph_program", "ane_prediction"), "unknown table role")
    if expected_role is not None:
        require(role == expected_role, f"mapping table_role must be {expected_role}")
    expected_top_level = {"schema", "table_role", "row_xpath", "columns"}
    if role != "signposts":
        expected_top_level.add("native_identifier_name")
    require(
        set(mapping) == expected_top_level,
        "mapping fields differ from the exact allowlist",
    )
    require(mapping.get("schema") == MAPPING_SCHEMA, "mapping schema mismatch")
    row_xpath = mapping.get("row_xpath")
    require(isinstance(row_xpath, str) and row_xpath, "row_xpath is required")
    columns = mapping.get("columns")
    require(isinstance(columns, dict), "columns must be an object")
    required = SIGNPOST_FIELDS if role == "signposts" else INTERVAL_FIELDS
    require(set(columns) == set(required), "mapping columns must exactly equal the canonical fields")
    if role != "signposts":
        native_name = mapping.get("native_identifier_name")
        require(
            native_name is None or (isinstance(native_name, str) and native_name),
            "native_identifier_name must be null or a non-empty string",
        )

    for field, spec in columns.items():
        require(isinstance(spec, dict), f"mapping for {field} must be an object")
        require(set(spec) <= COLUMN_SPEC_KEYS, f"mapping for {field} has unknown fields")
        modes = set(spec) & SOURCE_MODES
        require(len(modes) == 1, f"mapping for {field} needs exactly one source mode")
        mode = next(iter(modes))
        if mode == "row_index":
            require(
                field == "row_id" and spec == {"row_index": True},
                "row_index is allowed only as the complete row_id specification",
            )
            continue
        if mode == "literal":
            require(
                field == "native_identifier"
                and spec.get("literal") is None
                and mapping.get("native_identifier_name") is None,
                f"literal substitution is not permitted for source field {field}",
            )
            require(
                set(spec) == {"literal", "type"}
                and spec.get("type") in ("nullable_string", "nullable_integer"),
                "null native_identifier literal needs exactly one nullable type",
            )
            continue
        if mode == "index":
            index = spec.get("index")
            require(
                isinstance(index, int) and not isinstance(index, bool) and index >= 0,
                f"mapping for {field} has an invalid column index",
            )
        else:
            require(
                isinstance(spec.get("tag"), str) and bool(spec["tag"]),
                f"mapping for {field} has an invalid tag",
            )
        if "attribute" in spec:
            require(
                isinstance(spec["attribute"], str) and bool(spec["attribute"]),
                f"mapping for {field} has an invalid attribute",
            )
        if "regex" in spec:
            pattern = spec["regex"]
            require(isinstance(pattern, str) and bool(pattern), f"mapping for {field} has an invalid regex")
            try:
                compiled_pattern = re.compile(pattern)
            except re.error as error:
                raise MappingError(f"mapping for {field} has an invalid regex: {error}") from error
        require("group" not in spec or "regex" in spec, f"mapping for {field} has group without regex")
        if "group" in spec:
            group = spec["group"]
            require(
                isinstance(group, int) and not isinstance(group, bool) and group >= 0,
                f"mapping for {field} has an invalid regex group",
            )
        if "regex" in spec:
            group = spec.get("group", 1)
            require(
                group == 0 or group <= compiled_pattern.groups,
                f"mapping for {field} selects a missing regex group",
            )
        value_type = spec.get("type", "string")
        require(value_type in SUPPORTED_TYPES, f"mapping for {field} has an unsupported type")
        if value_type.startswith("nullable_"):
            require(field == "native_identifier", "only native_identifier may be nullable")
        null_values = spec.get("null_values", [])
        require(isinstance(null_values, list), f"mapping for {field} null_values must be an array")
        require(
            all(
                isinstance(item, (str, int)) and not isinstance(item, bool)
                for item in null_values
            ),
            f"mapping for {field} null_values must contain only string or integer scalars",
        )
        require(
            not null_values or value_type.startswith("nullable_"),
            f"mapping for {field} null_values requires a nullable type",
        )
        if value_type == "nanoseconds":
            require(spec.get("unit") in UNIT_FACTORS, f"mapping for {field} needs a valid time unit")
        else:
            require("unit" not in spec, f"mapping for {field} has a unit on a non-time value")


def resolve_element(
    element: ET.Element,
    references: dict[str, ET.Element],
    row_index: int,
) -> ET.Element:
    seen: set[str] = set()
    while "ref" in element.attrib:
        reference = element.attrib["ref"]
        require(reference not in seen, f"row {row_index} contains a reference cycle")
        seen.add(reference)
        require(reference in references, f"row {row_index} has unresolved ref {reference!r}")
        element = references[reference]
    return element


def resolved_text(
    element: ET.Element,
    references: dict[str, ET.Element],
    row_index: int,
) -> str:
    element = resolve_element(element, references, row_index)
    parts = [element.text or ""]
    for child in element:
        parts.append(resolved_text(child, references, row_index))
        parts.append(child.tail or "")
    return "".join(parts)


def extract_raw(
    row: ET.Element,
    spec: dict[str, Any],
    row_index: int,
    references: dict[str, ET.Element],
) -> Any:
    source_modes = sum(
        key in spec for key in ("literal", "row_index", "index", "tag")
    )
    require(source_modes == 1, "each column needs exactly one source mode")
    if "literal" in spec:
        value: Any = spec["literal"]
    elif spec.get("row_index") is True:
        value = f"xml-row-{row_index:06d}"
    else:
        if "index" in spec:
            index = spec["index"]
            require(isinstance(index, int) and index >= 0, "column index must be non-negative")
            children = list(row)
            require(index < len(children), f"row {row_index} has no child index {index}")
            element = children[index]
        else:
            tag = spec["tag"]
            require(isinstance(tag, str) and tag, "column tag must be a non-empty string")
            matches = row.findall(tag)
            require(len(matches) == 1, f"row {row_index} tag {tag!r} matched {len(matches)}")
            element = matches[0]
        element = resolve_element(element, references, row_index)
        attribute = spec.get("attribute")
        if attribute is None:
            value = resolved_text(element, references, row_index).strip()
        else:
            require(isinstance(attribute, str) and attribute, "attribute must be a string")
            require(attribute in element.attrib, f"row {row_index} lacks attribute {attribute!r}")
            value = element.attrib[attribute]

    if isinstance(value, str) and "regex" in spec:
        pattern = spec["regex"]
        group = spec.get("group", 1)
        require(isinstance(pattern, str) and pattern, "regex must be a non-empty string")
        require(isinstance(group, int) and group >= 0, "regex group must be non-negative")
        match = re.search(pattern, value)
        require(match is not None, f"row {row_index} value does not match {pattern!r}")
        value = match.group(group)

    null_values = spec.get("null_values", [])
    require(isinstance(null_values, list), "null_values must be an array")
    if value in null_values:
        value = None
    return value


def convert(value: Any, spec: dict[str, Any], row_index: int) -> Any:
    value_type = spec.get("type", "string")
    if value is None:
        require(value_type.startswith("nullable_"), f"row {row_index} has unexpected null")
        return None
    if value_type in ("string", "nullable_string"):
        require(isinstance(value, (str, int)), f"row {row_index} value is not scalar text")
        return str(value)
    if value_type in ("integer", "nullable_integer"):
        try:
            converted = int(value)
        except (TypeError, ValueError) as error:
            raise MappingError(f"row {row_index} value is not an integer: {value!r}") from error
        return converted
    if value_type == "nanoseconds":
        unit = spec.get("unit")
        require(unit in UNIT_FACTORS, "nanosecond conversion unit must be ns/us/ms/s")
        try:
            scaled = Decimal(str(value)) * UNIT_FACTORS[unit]
        except InvalidOperation as error:
            raise MappingError(f"row {row_index} timestamp is not decimal: {value!r}") from error
        integral = scaled.to_integral_value()
        require(scaled == integral, f"row {row_index} value is not exactly representable in ns")
        return int(integral)
    raise MappingError(f"unsupported mapping type: {value_type!r}")


def canonicalize(xml_path: Path, mapping: dict[str, Any]) -> dict[str, Any]:
    validate_mapping(mapping)
    role = mapping.get("table_role")
    row_xpath = mapping.get("row_xpath")
    columns = mapping.get("columns")
    required = SIGNPOST_FIELDS if role == "signposts" else INTERVAL_FIELDS

    try:
        root = ET.parse(xml_path).getroot()
    except (OSError, ET.ParseError) as error:
        raise MappingError(f"cannot parse xctrace XML: {error}") from error
    xml_rows = root.findall(row_xpath)
    require(bool(xml_rows), f"row_xpath {row_xpath!r} selected no rows")
    references: dict[str, ET.Element] = {}
    for element in root.iter():
        identifier = element.attrib.get("id")
        if identifier is None:
            continue
        require(identifier not in references, f"duplicate xctrace element id {identifier!r}")
        references[identifier] = element
    rows = []
    for index, xml_row in enumerate(xml_rows, start=1):
        row = {}
        for field in required:
            spec = columns[field]
            row[field] = convert(
                extract_raw(xml_row, spec, index, references), spec, index
            )
        rows.append(row)

    common = {
        "timestamp_unit": "ns",
        "source_export_sha256": sha256_file(xml_path),
        "column_mapping_sha256": hashlib.sha256(
            canonical_json_bytes(mapping)
        ).hexdigest(),
        "rows": rows,
    }
    if role == "signposts":
        return {"schema": "ane-v2-canonical-signpost-table-v1", **common}
    return {
        "schema": "ane-v2-canonical-interval-table-v1",
        "table_role": role,
        "native_identifier_name": mapping.get("native_identifier_name"),
        **common,
    }


def publicize_canonical_table(
    full_table: dict[str, Any], target_pid: int
) -> dict[str, Any]:
    require(
        isinstance(target_pid, int) and not isinstance(target_pid, bool) and target_pid > 0,
        "target PID must be a positive integer",
    )
    rows = full_table.get("rows")
    require(isinstance(rows, list), "canonical table rows must be an array")
    for index, row in enumerate(rows):
        require(isinstance(row, dict), f"canonical row {index} must be an object")
        pid = row.get("pid")
        require(
            isinstance(pid, int) and not isinstance(pid, bool) and pid > 0,
            f"canonical row {index} PID must be a positive integer",
        )
    target_rows = [row for row in rows if row["pid"] == target_pid]
    excluded_count = len(rows) - len(target_rows)
    common = {
        "timestamp_unit": full_table["timestamp_unit"],
        "source_export_sha256": full_table["source_export_sha256"],
        "column_mapping_sha256": full_table["column_mapping_sha256"],
        "full_table_sha256": hashlib.sha256(canonical_json_bytes(full_table)).hexdigest(),
        "excluded_other_process_count": excluded_count,
        "rows": target_rows,
    }
    if full_table.get("schema") == "ane-v2-canonical-signpost-table-v1":
        return {"schema": "ane-v2-public-canonical-signpost-table-v2", **common}
    require(
        full_table.get("schema") == "ane-v2-canonical-interval-table-v1",
        "canonical table schema mismatch",
    )
    return {
        "schema": "ane-v2-public-canonical-interval-table-v2",
        "table_role": full_table["table_role"],
        "native_identifier_name": full_table["native_identifier_name"],
        **common,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--target-pid", type=int, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--public-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    private_output = args.private_output.resolve()
    public_output = args.public_output.resolve()
    require(private_output != public_output, "private and public outputs must differ")
    full_table = canonicalize(args.xml, mapping)
    public_table = publicize_canonical_table(full_table, args.target_pid)
    private_output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    public_output.parent.mkdir(parents=True, exist_ok=True)
    private_output.write_bytes(canonical_json_bytes(full_table))
    private_output.chmod(0o600)
    public_output.write_bytes(canonical_json_bytes(public_table))
    print(f"wrote private {private_output} sha256={sha256_file(private_output)}")
    print(f"wrote public {public_output} sha256={sha256_file(public_output)}")


if __name__ == "__main__":
    main()
