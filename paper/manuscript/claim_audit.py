#!/usr/bin/env python3
"""Fail closed when the manuscript drifts beyond the frozen evidence ledger."""

from __future__ import annotations

import hashlib
import json
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
QUALITY_ANALYSIS = ROOT / "analysis" / "generated" / "quality-analysis-v2.json"
FIDELITY_TABLE = ROOT / "analysis" / "generated" / "tables" / "t3-w8-fidelity.json"
COMPATIBILITY_TABLE = (
    ROOT / "analysis" / "generated" / "tables" / "t8-w8-compatibility.json"
)
COMPATIBILITY_TEX = GENERATED / "tables" / "t8-w8-compatibility.tex"
SOURCE_LOCK = ROOT / "analysis" / "source-lock.json"
REPORT_PROTOCOL_V2 = ROOT / "REPORT_PROTOCOL_V2.md"
W8_COMPATIBILITY_OBSERVATION = ROOT / "W8_COMPATIBILITY_OBSERVATION_1.md"


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
            (8, "w8-compatibility"),
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


def verify_cmrc_headline_numbers(
    manuscript: str,
    quality_path: Path = QUALITY_ANALYSIS,
) -> None:
    require(quality_path.is_file(), "missing generated CMRC quality analysis")
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
        w8 = quality["variants"]["W8_ANE"]["summary"]
        int4 = quality["variants"]["INT4_GPU"]["summary"]
        comparison = quality["comparison"]
        em_difference = comparison["emDifferenceFirstMinusSecond"]
        f1_difference = comparison["f1DifferenceFirstMinusSecond"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise AuditError(f"invalid generated CMRC quality analysis: {error}") from error

    expected_fragments = {
        "profile scores": (
            f"Static-W8 scored {w8['em']:.2f} EM / {w8['f1']:.2f} F1 and "
            f"Dynamic-INT4 scored {int4['em']:.2f} EM / {int4['f1']:.2f} F1"
        ),
        "exact-match counts": (
            f"W8 produced {w8['exactMatchCount']} exact matches ({w8['em']:.2f} EM) "
            f"and {w8['f1']:.2f} F1; INT4 produced {int4['exactMatchCount']} exact "
            f"matches ({int4['em']:.2f} EM) and {int4['f1']:.2f} F1"
        ),
        "paired differences and intervals": (
            f"{em_difference['observedPoints']:+.2f} EM points with a 95\\% stratified "
            f"bootstrap interval of [{em_difference['lower95Points']:+.2f}, "
            f"{em_difference['upper95Points']:+.2f}] and "
            f"{f1_difference['observedPoints']:+.2f} F1 points with an interval of "
            f"[{f1_difference['lower95Points']:+.2f}, "
            f"{f1_difference['upper95Points']:+.2f}]"
        ),
        "paired sign tests": (
            f"{comparison['emWinSignTestPValue']:.3f} for EM and "
            f"{comparison['f1WinSignTestPValue']:.3f} for F1"
        ),
    }
    for label, fragment in expected_fragments.items():
        require(
            fragment in manuscript,
            f"manuscript CMRC {label} drift from generated analysis: expected {fragment!r}",
        )


def verify_fidelity_headline_numbers(
    manuscript: str,
    fidelity_path: Path = FIDELITY_TABLE,
) -> None:
    require(fidelity_path.is_file(), "missing generated W8 fidelity table")
    try:
        fidelity = json.loads(fidelity_path.read_text(encoding="utf-8"))
        holdout = fidelity["evaluations"]["w8_frozen_holdout"]
        historical = fidelity["historicalQualitySummary"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise AuditError(f"invalid generated W8 fidelity table: {error}") from error

    require(fidelity.get("schemaVersion") == 2, "generated T3 is not fidelity-v2")
    require(
        historical.get("status") == "superseded_for_reported_fidelity_metrics",
        "historical W8 fidelity values are not marked superseded",
    )
    expected = (
        f"The holdout mean logit cosine was {holdout['mean_cosine']:.6f}, "
        f"the minimum was {holdout['minimum_cosine']:.6f}, top-1 agreement was "
        f"{100 * holdout['top1_agreement']:.2f}\\%, and the mean "
        f"candidate-minus-reference NLL delta was {holdout['mean_nll_delta']:.6f}."
    )
    require(
        expected in manuscript,
        f"manuscript W8 fidelity values drift from generated T3: expected {expected!r}",
    )


def verify_w8_compatibility_claims(
    manuscript: str,
    compatibility_path: Path = COMPATIBILITY_TABLE,
) -> None:
    require(compatibility_path.is_file(), "missing generated W8 compatibility table")
    require(COMPATIBILITY_TEX.is_file(), "missing rendered W8 compatibility table")
    visible_text = (
        manuscript + "\n" + COMPATIBILITY_TEX.read_text(encoding="utf-8")
    )
    try:
        compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
        old = compatibility["oldPublicArtifact"]
        current = compatibility["currentCandidate"]
        repeated = compatibility["repeatedAuthoringExports"]
        boundary = compatibility["claimBoundary"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise AuditError(f"invalid generated W8 compatibility table: {error}") from error

    require(old["attempts"] == 2, "compatibility evidence must retain two old-AOT attempts")
    require(
        old["failureStage"] == "ANECCompileOffline",
        "compatibility evidence has an unexpected old-AOT failure stage",
    )
    require(
        old["afterFullRebootRequestAndReconnectAttemptIncluded"] is True,
        "compatibility evidence omits the reboot-request/reconnect boundary",
    )
    require(
        old["completedRebootDirectlyVerified"] is False,
        "compatibility evidence overstates direct verification of reboot completion",
    )
    require(current["attempts"] == 1, "candidate compatibility evidence must remain one load")
    require(
        boundary == {
            "loadOnly": True,
            "generationPerformed": False,
            "instrumentsTracePerformed": False,
            "coldStartBenchmarkClaimed": False,
            "causeIsolated": False,
            "performanceComparisonClaimed": False,
        },
        "compatibility claim boundary drift",
    )
    require(repeated["rawByteEquality"] is False, "repeat exports became byte-identical")

    expected_fragments = {
        "old producer": old["producer"],
        "current producer": current["producer"],
        "current source hash": current["sourceHashSHA256"],
        "current compiled-main hash": current["compiledMainSHA256"],
        "first repeated-export hash": repeated["firstMainMLIRBSHA256"],
        "second repeated-export hash": repeated["secondMainMLIRBSHA256"],
        "load duration": f'{current["loadSeconds"]:.3f} s',
        "peak process RSS": f'{current["peakProcessResidentMiB"]:,.1f} MiB',
    }
    for label, fragment in expected_fragments.items():
        require(
            fragment in visible_text,
            f"manuscript W8 compatibility {label} drift: expected {fragment!r}",
        )

    lowered = visible_text.lower()
    for phrase in (
        "load-only",
        "precludes causal attribution",
        "no generation or instruments trace",
        "not a cold-start benchmark",
        "full-reboot request",
        "timed out while waiting for the device",
    ):
        require(phrase in lowered, f"compatibility limitation is missing: {phrase}")


def audit() -> None:
    for path in (
        MANUSCRIPT,
        BIBLIOGRAPHY,
        LEDGER,
        AUDIT,
        SOURCE_LOCK,
        REPORT_PROTOCOL_V2,
        W8_COMPATIBILITY_OBSERVATION,
    ):
        require(path.is_file(), f"missing required file: {path.relative_to(ROOT)}")

    source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))
    for relative, path in (
        ("paper/REPORT_PROTOCOL_V2.md", REPORT_PROTOCOL_V2),
        (
            "paper/W8_COMPATIBILITY_OBSERVATION_1.md",
            W8_COMPATIBILITY_OBSERVATION,
        ),
    ):
        require(relative in source_lock["localFiles"], f"source lock omits {relative}")
        require(
            source_lock["localFiles"][relative] == sha256(path),
            f"source lock drift: {relative}",
        )

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
            "t8-w8-compatibility",
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

    verify_cmrc_headline_numbers(manuscript)
    verify_fidelity_headline_numbers(manuscript)
    verify_w8_compatibility_claims(manuscript)

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
