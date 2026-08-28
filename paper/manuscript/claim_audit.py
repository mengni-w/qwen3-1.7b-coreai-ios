#!/usr/bin/env python3
"""Fail closed when the manuscript drifts beyond the frozen evidence ledger."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript" / "qwen3-coreai-report.tex"
BIBLIOGRAPHY = ROOT / "manuscript" / "references.bib"
LEDGER = ROOT / "EVIDENCE_INDEX.md"
AUDIT = ROOT / "manuscript" / "CLAIM_AUDIT.md"
GENERATED = ROOT / "manuscript" / "generated"
MANIFEST = GENERATED / "MANIFEST.sha256"


class AuditError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_csv(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def verify_generated_manifest() -> None:
    require(MANIFEST.is_file(), "missing manuscript generated-asset manifest")
    listed: set[str] = set()
    for line_number, line in enumerate(
        MANIFEST.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        require(match is not None, f"malformed generated manifest line {line_number}")
        expected, relative = match.groups()
        require(relative not in listed, f"duplicate generated asset: {relative}")
        path = GENERATED / relative
        require(path.is_file(), f"missing generated asset: {relative}")
        require(sha256(path) == expected, f"generated asset hash drift: {relative}")
        listed.add(relative)

    actual = {
        path.relative_to(GENERATED).as_posix()
        for path in GENERATED.rglob("*")
        if path.is_file() and path != MANIFEST
    }
    require(
        listed == actual,
        "generated manifest file-set mismatch: "
        f"unlisted={sorted(actual - listed)}, missing={sorted(listed - actual)}",
    )

    required = {
        *(f"tables/t{i}-{name}.tex" for i, name in (
            (1, "public-status"),
            (2, "profile-definitions"),
            (3, "w8-fidelity"),
            (4, "w8-device-evidence"),
            (5, "paired-quality"),
            (6, "size-rss"),
            (7, "workload-performance"),
        )),
        *(f"figures/f{i}-{name}.pdf" for i, name in (
            (1, "static-pipeline"),
            (2, "profile-comparison"),
            (3, "paired-quality"),
            (4, "workload-latency"),
            (5, "size-rss"),
        )),
        "figures/f1-static-pipeline.svg",
        "figures/f2-profile-comparison.svg",
    }
    require(
        required == listed,
        "generated manifest inventory mismatch: "
        f"unexpected={sorted(listed - required)}, missing={sorted(required - listed)}",
    )


def audit() -> None:
    for path in (MANUSCRIPT, BIBLIOGRAPHY, LEDGER, AUDIT):
        require(path.is_file(), f"missing required file: {path.relative_to(ROOT)}")

    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    bibliography = BIBLIOGRAPHY.read_text(encoding="utf-8")
    ledger = LEDGER.read_text(encoding="utf-8")
    audit_text = AUDIT.read_text(encoding="utf-8")

    admitted = set(re.findall(r"^### (CL-\d{2})\b", ledger, flags=re.MULTILINE))
    used: set[str] = set()
    for marker in re.findall(r"\\evidence\{([^}]+)\}", manuscript):
        used |= split_csv(marker)
    require(used, "manuscript contains no evidence markers")
    require(used <= admitted, f"unknown manuscript claim IDs: {sorted(used - admitted)}")

    audited = set(re.findall(r"\| (CL-\d{2}(?:\s*,\s*CL-\d{2})*) \|", audit_text))
    audited_ids: set[str] = set()
    for group in audited:
        audited_ids |= split_csv(group)
    require(used <= audited_ids, f"claim audit omits used IDs: {sorted(used - audited_ids)}")
    require("Audit result: **PASS**" in audit_text, "manual claim audit is not marked PASS")

    cite_keys: set[str] = set()
    for group in re.findall(r"\\cite[tp]?\{([^}]+)\}", manuscript):
        cite_keys |= split_csv(group)
    bib_keys = set(re.findall(r"^@[A-Za-z]+\{([^,]+),", bibliography, flags=re.MULTILINE))
    require(cite_keys <= bib_keys, f"missing bibliography entries: {sorted(cite_keys - bib_keys)}")
    require(cite_keys, "manuscript contains no bibliographic citations")

    required_sections = (
        "Introduction",
        "Background and Related Work",
        "System Profiles",
        "Methods",
        "Results",
        "Discussion",
        "Reproducibility",
        "Limitations and Threats to Validity",
        "Conclusion",
    )
    for section in required_sections:
        require(f"\\section{{{section}}}" in manuscript, f"missing section: {section}")

    required_inputs = (
        "t1-public-status",
        "t2-profile-definitions",
        "t3-w8-fidelity",
        "t4-w8-device-evidence",
        "t5-paired-quality",
        "t6-size-rss",
        "t7-workload-performance",
    )
    for name in required_inputs:
        require(name in manuscript, f"manuscript omits generated table: {name}")
    for name in (
        "f1-static-pipeline",
        "f2-profile-comparison",
        "f3-paired-quality",
        "f4-workload-latency",
        "f5-size-rss",
    ):
        require(name in manuscript, f"manuscript omits generated figure: {name}")

    require(
        manuscript.count("not byte-identical") >= 1,
        "historical/public W8 identity disclosure is missing",
    )

    lowered = manuscript.lower()
    forbidden_positive_patterns = {
        "priority claim": r"\b(first ever|world['’]s first|first qwen3-1\.7b core ai)\b",
        "Apple adoption": r"\bapple (accepted|adopted|endorsed|merged) (this|our|the)\b",
        "exclusive ANE": r"\b(all|every|entirely|exclusively) (operations? )?(ran|run|execute[ds]?) on (the )?(apple )?neural engine\b",
        "quality equivalence": r"\b(statistically equivalent|quality parity|non-inferior)\b",
        "energy superiority": r"\b(energy|battery|joules?)[- ]?(efficient|efficiency|advantage|superiority)\b",
    }
    for label, pattern in forbidden_positive_patterns.items():
        for match in re.finditer(pattern, lowered):
            sentence_start = max(
                lowered.rfind(".", 0, match.start()),
                lowered.rfind("\n", 0, match.start()),
            )
            sentence_end_candidates = [
                position
                for position in (
                    lowered.find(".", match.end()),
                    lowered.find("\n", match.end()),
                )
                if position >= 0
            ]
            sentence_end = min(sentence_end_candidates) if sentence_end_candidates else len(lowered)
            sentence = lowered[sentence_start + 1 : sentence_end]
            explicitly_negative = any(
                marker in f" {sentence} "
                for marker in (
                    " not ",
                    " no ",
                    " neither ",
                    " does not ",
                    " do not ",
                    " cannot ",
                    " would therefore exceed ",
                )
            )
            require(explicitly_negative, f"forbidden positive claim detected: {label}")

    for placeholder in ("TODO", "TBD", "PLACEHOLDER", "INSERT FIGURE", "CITATION NEEDED"):
        require(placeholder not in manuscript.upper(), f"unresolved placeholder: {placeholder}")

    verify_generated_manifest()

    print("CLAIM_AUDIT_OK")
    print(f"admitted_claims={len(admitted)}")
    print(f"manuscript_claims={len(used)}")
    print(f"bibliography_citations={len(cite_keys)}")


if __name__ == "__main__":
    try:
        audit()
    except AuditError as error:
        print(f"CLAIM_AUDIT_FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
