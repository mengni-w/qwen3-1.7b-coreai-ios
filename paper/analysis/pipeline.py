#!/usr/bin/env python3
"""Rebuild paper data from frozen, already published evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import random
import shutil
import statistics
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "analysis"
LOCK_PATH = ANALYSIS_DIR / "source-lock.json"
PUBLIC_STATUS_PATH = ANALYSIS_DIR / "public-status-v1.json"
DEFAULT_GENERATED_DIR = ANALYSIS_DIR / "generated"


class PipelineError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise PipelineError(f"Missing locked input: {path}")
    observed = sha256(path)
    if observed.lower() != expected.lower():
        raise PipelineError(
            f"SHA-256 mismatch for {path}: expected {expected}, observed {observed}"
        )


def run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    capture_bytes: bool = False,
) -> str | bytes:
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=None,
        text=not capture_bytes,
    )
    return completed.stdout


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verify_runtime(lock: dict) -> None:
    expected = lock["runtime"]
    actual_python = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    if actual_python != expected["python"]:
        raise PipelineError(
            f"Python {expected['python']} is required; run analysis/run.sh "
            f"instead of invoking pipeline.py directly (observed {actual_python})"
        )
    import nltk

    if nltk.__version__ != expected["nltk"]:
        raise PipelineError(
            f"NLTK {expected['nltk']} is required, observed {nltk.__version__}"
        )


def ensure_repository(name: str, spec: dict, target: Path, offline: bool) -> None:
    if not target.exists():
        if offline:
            raise PipelineError(f"Offline cache is missing repository {name}: {target}")
        target.mkdir(parents=True)
        run(["git", "init", "--quiet"], cwd=target)
        run(["git", "remote", "add", "origin", spec["url"]], cwd=target)
    elif not (target / ".git").is_dir():
        raise PipelineError(f"Analysis cache path is not a Git repository: {target}")

    origin = str(run(["git", "remote", "get-url", "origin"], cwd=target)).strip()
    if origin != spec["url"]:
        raise PipelineError(
            f"Repository origin mismatch for {name}: expected {spec['url']}, got {origin}"
        )

    commit = spec["commit"]
    if offline:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=target,
            check=True,
            stdout=subprocess.DEVNULL,
        )
    else:
        run(["git", "fetch", "--quiet", "--depth", "1", "origin", commit], cwd=target)
    run(["git", "checkout", "--quiet", "--detach", "--force", commit], cwd=target)
    observed = str(run(["git", "rev-parse", "HEAD"], cwd=target)).strip()
    if observed != commit:
        raise PipelineError(f"Commit mismatch for {name}: {observed}")

    for relative_path, expected_hash in spec["files"].items():
        require_hash(target / relative_path, expected_hash)


def ensure_download(url: str, target: Path, expected_hash: str, offline: bool) -> None:
    if target.is_file() and sha256(target).lower() == expected_hash.lower():
        return
    if offline:
        raise PipelineError(f"Offline cache is missing exact download: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".download")
    subprocess.run(
        [
            "curl",
            "-fsSL",
            "--retry",
            "3",
            "--retry-all-errors",
            url,
            "-o",
            str(temporary),
        ],
        check=True,
    )
    require_hash(temporary, expected_hash)
    os.replace(temporary, target)


def load_unique_jsonl(path: Path) -> dict[str, dict]:
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                raise PipelineError(f"Invalid result record at {path}:{line_number}")
            sample_id = record["id"]
            if sample_id in records:
                raise PipelineError(f"Duplicate result ID in {path}: {sample_id}")
            records[sample_id] = record
    return records


def validate_quality_inputs(
    sample_path: Path,
    result_specs: dict[str, tuple[Path, str]],
) -> tuple[dict, dict[str, dict[str, dict]]]:
    envelope = read_json(sample_path)
    samples = envelope.get("samples")
    if not isinstance(samples, list) or len(samples) != 300:
        raise PipelineError("Frozen CMRC sample must contain exactly 300 rows")

    sample_by_id: dict[str, dict] = {}
    strata: dict[str, int] = {"short": 0, "medium": 0, "long": 0}
    for sample in samples:
        sample_id = sample.get("id")
        if not isinstance(sample_id, str) or sample_id in sample_by_id:
            raise PipelineError(f"Invalid or duplicate frozen sample ID: {sample_id}")
        stratum = sample.get("stratum")
        if stratum not in strata:
            raise PipelineError(f"Unexpected CMRC stratum for {sample_id}: {stratum}")
        strata[stratum] += 1
        sample_by_id[sample_id] = sample
    if strata != {"short": 100, "medium": 100, "long": 100}:
        raise PipelineError(f"Frozen CMRC strata changed: {strata}")

    records_by_label: dict[str, dict[str, dict]] = {}
    expected_ids = set(sample_by_id)
    for label, (path, expected_variant) in result_specs.items():
        records = load_unique_jsonl(path)
        observed_ids = set(records)
        if observed_ids != expected_ids:
            raise PipelineError(
                f"Result ID set mismatch for {label}: "
                f"missing={sorted(expected_ids - observed_ids)}, "
                f"extra={sorted(observed_ids - expected_ids)}"
            )
        for sample_id, sample in sample_by_id.items():
            record = records[sample_id]
            if record.get("error") is not None:
                raise PipelineError(f"Recorded generation error for {label}/{sample_id}")
            if record.get("variant") != expected_variant:
                raise PipelineError(
                    f"Variant mismatch for {label}/{sample_id}: {record.get('variant')}"
                )
            for key in (
                "datasetRowIndex",
                "ordinal",
                "stratum",
                "contextCharacterCount",
            ):
                if record.get(key) != sample.get(key):
                    raise PipelineError(
                        f"Sample metadata mismatch for {label}/{sample_id}/{key}"
                    )
            if not isinstance(record.get("content"), str):
                raise PipelineError(f"Missing generated text for {label}/{sample_id}")
            input_tokens = record.get("inputTokens")
            if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) \
                    or input_tokens <= 0:
                raise PipelineError(
                    f"Invalid input-token count for {label}/{sample_id}: {input_tokens}"
                )
            output_tokens = record.get("outputTokens")
            if not isinstance(output_tokens, int) or isinstance(output_tokens, bool) \
                    or not 0 <= output_tokens < 128:
                raise PipelineError(
                    f"Invalid or capped output-token count for {label}/{sample_id}: "
                    f"{output_tokens}"
                )
            cached_tokens = record.get("cachedInputTokens")
            if (
                not isinstance(cached_tokens, int)
                or isinstance(cached_tokens, bool)
                or cached_tokens != 0
            ):
                raise PipelineError(f"Unexpected cached input for {label}/{sample_id}")
            reasoning_tokens = record.get("reasoningTokens")
            if (
                not isinstance(reasoning_tokens, int)
                or isinstance(reasoning_tokens, bool)
                or reasoning_tokens != 0
            ):
                raise PipelineError(f"Unexpected reasoning output for {label}/{sample_id}")
        records_by_label[label] = records

    labels = list(records_by_label)
    for sample_id in expected_ids:
        input_counts = {
            records_by_label[label][sample_id].get("inputTokens") for label in labels
        }
        if len(input_counts) != 1:
            raise PipelineError(f"Input-token mismatch across profiles for {sample_id}")
    return envelope, records_by_label


def load_locked_scorer(path: Path) -> dict:
    namespace = {"__name__": "locked_cmrc_scorer", "__file__": str(path)}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
    return namespace


def stratified_bootstrap_interval(
    differences_by_stratum: dict[str, list[float]],
    *,
    seed: int,
) -> dict:
    expected = {"short": 100, "medium": 100, "long": 100}
    observed = {key: len(value) for key, value in differences_by_stratum.items()}
    if observed != expected:
        raise PipelineError(f"Paired bootstrap strata changed: {observed}")

    generator = random.Random(seed)
    means: list[float] = []
    for _ in range(10_000):
        selected: list[float] = []
        for stratum in ("short", "medium", "long"):
            values = differences_by_stratum[stratum]
            selected.extend(values[generator.randrange(len(values))] for _ in values)
        means.append(statistics.fmean(selected))
    means.sort()
    all_differences = [
        value
        for stratum in ("short", "medium", "long")
        for value in differences_by_stratum[stratum]
    ]
    return {
        "observedPoints": statistics.fmean(all_differences),
        "lower95Points": linear_quantile(means, 0.025),
        "upper95Points": linear_quantile(means, 0.975),
        "resamples": len(means),
        "seed": seed,
        "method": "paired percentile bootstrap stratified by context-length band",
        "quantileDefinition": "Hyndman-Fan type 7 linear interpolation",
        "resampleUnit": "example within stratum",
        "stratumSampleSizes": expected,
    }


def linear_quantile(values: list[float], probability: float) -> float:
    if not values:
        raise PipelineError("Cannot compute a quantile of an empty sequence")
    if not 0.0 <= probability <= 1.0:
        raise PipelineError(f"Invalid quantile probability: {probability}")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def build_stratified_quality_analysis(
    scorer_path: Path,
    envelope: dict,
    records_by_label: dict[str, dict[str, dict]],
    published: dict,
) -> dict:
    scorer = load_locked_scorer(scorer_path)
    samples = envelope["samples"]
    scored = {
        label: scorer["score_variant"](samples, records)
        for label, records in records_by_label.items()
    }
    labels = list(scored)
    if labels != ["W8_ANE", "INT4_GPU"]:
        raise PipelineError(f"Unexpected profile order for paired analysis: {labels}")

    left_by_id = {row["id"]: row for row in scored[labels[0]]["rows"]}
    right_by_id = {row["id"]: row for row in scored[labels[1]]["rows"]}
    f1_differences = {"short": [], "medium": [], "long": []}
    em_differences = {"short": [], "medium": [], "long": []}
    for sample in samples:
        sample_id = sample["id"]
        stratum = sample["stratum"]
        left = left_by_id[sample_id]
        right = right_by_id[sample_id]
        f1_differences[stratum].append(100.0 * (left["f1"] - right["f1"]))
        em_differences[stratum].append(100.0 * (left["em"] - right["em"]))

    result = json.loads(json.dumps(published))
    result["schemaVersion"] = 2
    result["analysisProvenance"] = {
        "status": "post-review reanalysis",
        "publishedScoringReproducedByteIdentically": True,
        "newModelOutputsCreated": False,
        "newDeviceMeasurementsCreated": False,
        "description": (
            "Paired uncertainty was recomputed after manuscript review from the "
            "unchanged published predictions and locked scorer."
        ),
    }
    result["metric"] = (
        "Documented Python 3 adaptation of the official CMRC2018 EM/F1 formula; "
        "NLTK Treebank tokenization without sentence splitting"
    )
    result["comparison"]["f1DifferenceFirstMinusSecond"] = (
        stratified_bootstrap_interval(f1_differences, seed=20260721)
    )
    result["comparison"]["emDifferenceFirstMinusSecond"] = (
        stratified_bootstrap_interval(em_differences, seed=20260722)
    )
    result["comparison"]["signTest"] = {
        "method": "exact two-sided paired sign test",
        "tiesExcluded": True,
        "f1PValue": result["comparison"]["f1WinSignTestPValue"],
        "emPValue": result["comparison"]["emWinSignTestPValue"],
    }
    return result


def rebuild_and_score_quality(
    lock: dict,
    comparison_repo: Path,
    dataset_path: Path,
    generated_dir: Path,
) -> dict:
    dataset = lock["dataset"]
    data_dir = comparison_repo / "Data"
    data_dir.mkdir(exist_ok=True)
    approved_source = data_dir / "cmrc2018_dev_official.json"
    shutil.copyfile(dataset_path, approved_source)

    freeze_stdout = str(
        run(
            [sys.executable, "benchmarks/tools/freeze_cmrc.py"],
            cwd=comparison_repo,
        )
    )
    freeze_result = json.loads(freeze_stdout)
    sample_path = data_dir / "cmrc2018-quality-300.json"
    require_hash(sample_path, dataset["frozenSampleSHA256"])
    if freeze_result["sourceRowsSHA256"] != dataset["canonicalRowsSHA256"]:
        raise PipelineError("Canonical CMRC row hash changed during sample reconstruction")
    if freeze_result["rows"] != dataset["expectedRows"]:
        raise PipelineError("CMRC row count changed during sample reconstruction")
    if freeze_result["uniqueContexts"] != dataset["expectedUniqueContexts"]:
        raise PipelineError("CMRC context count changed during sample reconstruction")

    result_specs = {
        "W8_ANE": (
            comparison_repo
            / "benchmarks/results/raw/w8-ane-no-thinking-results.jsonl",
            "W8_ANE",
        ),
        "INT4_GPU": (
            comparison_repo
            / "benchmarks/results/raw/int4-gpu-no-thinking-results.jsonl",
            "INT4_GPU",
        ),
    }
    envelope, records_by_label = validate_quality_inputs(sample_path, result_specs)

    score_output = bytes(
        run(
            [
                sys.executable,
                "benchmarks/tools/score_frozen_cmrc_py3.py",
                str(sample_path),
                "W8_ANE=benchmarks/results/raw/w8-ane-no-thinking-results.jsonl",
                "INT4_GPU=benchmarks/results/raw/int4-gpu-no-thinking-results.jsonl",
            ],
            cwd=comparison_repo,
            capture_bytes=True,
        )
    )
    recomputed_path = generated_dir / "quality-recomputed.json"
    recomputed_path.parent.mkdir(parents=True, exist_ok=True)
    recomputed_path.write_bytes(score_output)
    require_hash(recomputed_path, lock["expectedPublishedQualitySHA256"])

    published_path = comparison_repo / "benchmarks/results/quality-comparison.json"
    if score_output != published_path.read_bytes():
        raise PipelineError(
            "Recomputed quality JSON is not byte-identical to the published result"
        )

    published = read_json(recomputed_path)
    analysis = build_stratified_quality_analysis(
        comparison_repo / "benchmarks/tools/score_frozen_cmrc_py3.py",
        envelope,
        records_by_label,
        published,
    )
    analysis_path = generated_dir / "quality-analysis-v2.json"
    write_json(analysis_path, analysis)

    verification = {
        "schemaVersion": 2,
        "dataset": {
            "officialSourceSHA256": dataset["officialSourceSHA256"],
            "canonicalRowsSHA256": dataset["canonicalRowsSHA256"],
            "frozenSampleSHA256": dataset["frozenSampleSHA256"],
            "rows": freeze_result["rows"],
            "uniqueContexts": freeze_result["uniqueContexts"],
            "samples": freeze_result["samples"],
        },
        "runtime": lock["runtime"],
        "publishedQualitySHA256": sha256(published_path),
        "recomputedQualitySHA256": sha256(recomputed_path),
        "paperAnalysisSHA256": sha256(analysis_path),
        "byteIdenticalToPublished": True,
        "paperAnalysisStatus": "post-review reanalysis",
        "qualityInputValidation": {
            "sampleIDsUnique": True,
            "resultIDsUnique": True,
            "resultIDSetsExact": True,
            "recordedErrors": 0,
            "maximumResponseTokenHits": 0,
            "inputTokenCountsPositive": True,
            "pairedInputTokenCountsEqual": True,
            "reportedCachedInputTokensNonzero": 0,
            "reasoningTokenCountsNonzero": 0,
            "stratumSampleSizes": {"short": 100, "medium": 100, "long": 100},
        },
        "newModelOutputsCreated": False,
        "newDeviceMeasurementsCreated": False,
    }
    write_json(generated_dir / "quality-verification.json", verification)
    return analysis


def markdown_table(document: str, heading: str) -> list[list[str]]:
    lines = document.splitlines()
    try:
        heading_index = lines.index(heading)
    except ValueError as error:
        raise PipelineError(f"Missing speed-report heading: {heading}") from error

    rows: list[list[str]] = []
    started = False
    for line in lines[heading_index + 1 :]:
        if line.startswith("#") and started:
            break
        if not line.startswith("|"):
            if started and not line.strip():
                break
            continue
        started = True
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        raise PipelineError(f"No data table found after heading: {heading}")
    return rows


NUMBER = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def first_number(value: str) -> float:
    match = NUMBER.search(value)
    if not match:
        raise PipelineError(f"Expected number in table cell: {value}")
    return float(match.group(0).replace(",", ""))


def parse_integer(value: str) -> int:
    parsed = first_number(value)
    if parsed != int(parsed):
        raise PipelineError(f"Expected integer in table cell: {value}")
    return int(parsed)


def normalized_variant(value: str) -> str:
    mapping = {"W8/ANE": "W8_ANE", "INT4/GPU": "INT4_GPU"}
    try:
        return mapping[value]
    except KeyError as error:
        raise PipelineError(f"Unexpected speed-report variant: {value}") from error


def parse_speed_samples(document: str, heading: str, workload_id: str) -> list[dict]:
    rows = markdown_table(document, heading)
    header = rows[0]
    samples: list[dict] = []
    for cells in rows[1:]:
        if len(cells) != len(header):
            raise PipelineError(f"Malformed row in {heading}: {cells}")
        row = dict(zip(header, cells))
        sample = {
            "workload": workload_id,
            "variant": normalized_variant(row["Variant"]),
            "run": parse_integer(row["Run"]),
            "inputTokens": parse_integer(row["Input"]),
            "outputTokens": parse_integer(row["Output"]),
            "ttftSeconds": first_number(row["TTFT s"]),
            "totalSeconds": first_number(row["Total s"]),
            "endToEndOutputTokensPerSecond": first_number(row["E2E tok/s"]),
        }
        if "Visible decode tok/s" in row:
            sample["visibleDecodeTokensPerSecond"] = first_number(
                row["Visible decode tok/s"]
            )
        if "Resident MiB" in row:
            sample["residentMiB"] = first_number(row["Resident MiB"])
        samples.append(sample)
    if len(samples) != 6:
        raise PipelineError(f"Expected six accepted samples for {workload_id}")
    return samples


def median_by_variant(samples: list[dict]) -> dict:
    result: dict[str, dict[str, float]] = {}
    fields = [
        "ttftSeconds",
        "totalSeconds",
        "visibleDecodeTokensPerSecond",
        "endToEndOutputTokensPerSecond",
        "residentMiB",
    ]
    for variant in ("W8_ANE", "INT4_GPU"):
        selected = [sample for sample in samples if sample["variant"] == variant]
        if len(selected) != 3:
            raise PipelineError(f"Expected three accepted samples for {variant}")
        result[variant] = {}
        for field in fields:
            values = [sample[field] for sample in selected if field in sample]
            if values:
                result[variant][field] = statistics.median(values)
    return result


def verify_headline_medians(document: str, workloads: dict) -> None:
    rows = markdown_table(document, "## Main comparison")
    by_name = {row[0]: row for row in rows[1:]}
    checks = {
        "Business, 161 input / 60 output: TTFT": ("business_161_60", "ttftSeconds"),
        "Business: total": ("business_161_60", "totalSeconds"),
        "Business: visible decode": (
            "business_161_60",
            "visibleDecodeTokensPerSecond",
        ),
        "Near 4K, 3,790 input / 10 output: TTFT": ("near_4k_3790_10", "ttftSeconds"),
        "Near 4K: total": ("near_4k_3790_10", "totalSeconds"),
        "Sustained decode, 120 input / 256 output: TTFT": (
            "decode_120_256",
            "ttftSeconds",
        ),
        "Sustained decode: total": ("decode_120_256", "totalSeconds"),
        "Sustained decode: visible decode": (
            "decode_120_256",
            "visibleDecodeTokensPerSecond",
        ),
    }
    for label, (workload_id, field) in checks.items():
        if label not in by_name:
            raise PipelineError(f"Missing headline speed row: {label}")
        published = by_name[label]
        expected = {
            "W8_ANE": first_number(published[1]),
            "INT4_GPU": first_number(published[2]),
        }
        for variant, value in expected.items():
            computed = workloads[workload_id]["medians"][variant][field]
            if computed != value:
                raise PipelineError(
                    f"Speed median mismatch for {label} / {variant}: "
                    f"published {value}, computed {computed}"
                )


def extract_speed(comparison_repo: Path, generated_dir: Path) -> dict:
    speed_path = comparison_repo / "docs/speed-result.md"
    document = speed_path.read_text(encoding="utf-8")
    definitions = [
        ("### Business medium", "business_161_60"),
        ("### Near-4K prefill", "near_4k_3790_10"),
        ("### Sustained decode", "decode_120_256"),
    ]
    workloads: dict[str, dict] = {}
    for heading, workload_id in definitions:
        samples = parse_speed_samples(document, heading, workload_id)
        workloads[workload_id] = {
            "inputTokens": samples[0]["inputTokens"],
            "outputTokens": samples[0]["outputTokens"],
            "acceptedSamples": samples,
            "medians": median_by_variant(samples),
        }
    verify_headline_medians(document, workloads)

    memory_rows = markdown_table(document, "## Memory and storage")
    memory_by_name = {row[0]: row for row in memory_rows[1:]}
    storage_and_memory = {}
    for key, label in (
        ("compiledModelBundleMiB", "Compiled model bundle"),
        ("peakProcessResidentMiB", "Peak process resident memory"),
        ("businessMedianResidentMiB", "Business median resident memory"),
        ("allocationHeadroomAfterLoadMiB", "Allocation headroom immediately after load"),
    ):
        if label not in memory_by_name:
            raise PipelineError(f"Missing storage/memory row: {label}")
        row = memory_by_name[label]
        storage_and_memory[key] = {
            "W8_ANE": first_number(row[1]),
            "INT4_GPU": first_number(row[2]),
        }

    short_attempt = "One W8 attempt stopped voluntarily at 24 output tokens."
    repeated_prompt = "Those samples were treated as engine-level repeat-input/cache contamination"
    if short_attempt not in document or repeated_prompt not in document:
        raise PipelineError("Published speed exclusions are missing or changed")

    output = {
        "schemaVersion": 1,
        "source": {
            "repositoryCommit": "34a4c08a9282bd076b8b5fe154c5507e6a8b3774",
            "path": "docs/speed-result.md",
            "sha256": sha256(speed_path),
        },
        "workloads": workloads,
        "storageAndMemory": storage_and_memory,
        "exclusions": {
            "oneShortW8DecodeAttemptExcludedAndReplaced": True,
            "repeatedPromptDiagnosticPassExcluded": True,
        },
        "newDeviceMeasurementsCreated": False,
    }
    write_json(generated_dir / "speed-normalized.json", output)
    return output


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def generate_tables(
    w8_repo: Path,
    comparison_repo: Path,
    public_w8_validation: Path,
    quality: dict,
    speed: dict,
    generated_dir: Path,
) -> None:
    tables_dir = generated_dir / "tables"
    public_status = read_json(PUBLIC_STATUS_PATH)
    t1 = {
        "schemaVersion": 1,
        "auditedAt": public_status["auditedAt"],
        "officialApple": public_status["officialApple"],
        "communitySnapshots": public_status["communitySnapshots"],
        "rows": public_status["tableRows"],
        "claimBoundary": (
            "Dated public-source status only; community evidence uses different "
            "devices and protocols unless explicitly paired in this work"
        ),
    }
    write_json(tables_dir / "t1-public-status.json", t1)

    w8_artifact = read_json(w8_repo / "results/artifact-summary.json")
    w8_quality = read_json(w8_repo / "results/quality-summary.json")
    w8_device = read_json(w8_repo / "results/device-runtime-summary.json")
    int4_artifact = read_json(
        comparison_repo / "benchmarks/results/artifact-summary.json"
    )
    public_w8 = read_json(public_w8_validation)

    t2 = {
        "schemaVersion": 1,
        "common": {
            "baseModel": w8_artifact["source"]["model"],
            "baseRevision": w8_artifact["source"]["revision"],
            "tokenizerSHA256": w8_artifact["source"]["tokenizer_sha256"],
            "architecture": "h16p",
            "platform": "iOS 27",
        },
        "profiles": {
            "W8_ANE": {
                "transformerWeights": w8_artifact["recipe"]["projection_weight_recipe"],
                "embedding": w8_artifact["recipe"]["embedding_recipe"],
                "compute": w8_artifact["recipe"]["compute_precision"],
                "kvCache": "FP16 fixed-size",
                "contextTokens": w8_artifact["recipe"]["maximum_context_tokens"],
                "graphShape": "static",
                "preferredCompute": "neural-engine",
                "historicalSourceArtifactSHA256": w8_artifact[
                    "device_validated_artifact"
                ]["source_aimodel_sha256"],
            },
            "INT4_GPU": {
                "transformerWeights": int4_artifact["conversion"]["weightCompression"],
                "embedding": "not separately reported in the artifact summary",
                "compute": int4_artifact["conversion"]["computeDataType"],
                "kvCache": "FP16 growing/dynamic",
                "contextTokens": int4_artifact["conversion"]["contextTokens"],
                "graphShape": "dynamic",
                "preferredCompute": int4_artifact["conversion"]["preferredCompute"],
                "sourceArtifactSHA256": int4_artifact["artifact"]["sourceHash"],
            },
        },
        "causalIsolationClaimed": False,
    }
    write_json(tables_dir / "t2-profile-definitions.json", t2)

    t3 = {
        "schemaVersion": 1,
        "mechanism": w8_quality["mechanism"],
        "selectionEvidence": w8_quality["selection_evidence"],
        "evaluations": w8_quality["evaluations"],
        "claimBoundary": "Conversion fidelity under frozen inputs, not general capability",
    }
    write_json(tables_dir / "t3-w8-fidelity.json", t3)

    t4 = {
        "schemaVersion": 1,
        "historicalArtifact": {
            "identity": w8_artifact["device_validated_artifact"],
            "device": w8_device["device"],
            "suite": w8_device["standalone_model_suite"],
            "trace": w8_device["execution_trace"],
        },
        "publicArtifact": public_w8,
        "mechanismRelationship": "same frozen W8 mechanism",
        "byteIdentical": False,
    }
    write_json(tables_dir / "t4-w8-device-evidence.json", t4)

    t5 = {
        "schemaVersion": 2,
        "publishedQualitySHA256": sha256(generated_dir / "quality-recomputed.json"),
        "paperAnalysisSHA256": sha256(generated_dir / "quality-analysis-v2.json"),
        "metric": quality["metric"],
        "variants": quality["variants"],
        "comparison": quality["comparison"],
        "equivalenceEstablished": False,
    }
    write_json(tables_dir / "t5-paired-quality.json", t5)
    write_csv(
        tables_dir / "t5-paired-quality.csv",
        ["variant", "samples", "exact_match_count", "em", "f1", "skipped"],
        [
            [
                variant,
                values["summary"]["total"],
                values["summary"]["exactMatchCount"],
                values["summary"]["em"],
                values["summary"]["f1"],
                values["summary"]["skip"],
            ]
            for variant, values in quality["variants"].items()
        ],
    )

    t6 = {
        "schemaVersion": 1,
        "unit": "MiB",
        "measurements": {
            key: speed["storageAndMemory"][key]
            for key in ("compiledModelBundleMiB", "peakProcessResidentMiB")
        },
        "rssMeaning": "Peak process resident memory in the disclosed benchmark",
    }
    write_json(tables_dir / "t6-size-rss.json", t6)
    write_csv(
        tables_dir / "t6-size-rss.csv",
        ["metric", "unit", "W8_ANE", "INT4_GPU"],
        [
            [key, "MiB", values["W8_ANE"], values["INT4_GPU"]]
            for key, values in t6["measurements"].items()
        ],
    )

    t7 = {
        "schemaVersion": 1,
        "workloads": speed["workloads"],
        "samplePolicy": "one warm-up followed by three accepted measured samples",
        "p95Claimed": False,
    }
    write_json(tables_dir / "t7-workload-performance.json", t7)
    t7_rows: list[list[object]] = []
    for workload_id, workload in speed["workloads"].items():
        for variant, medians in workload["medians"].items():
            t7_rows.append(
                [
                    workload_id,
                    workload["inputTokens"],
                    workload["outputTokens"],
                    variant,
                    medians.get("ttftSeconds"),
                    medians.get("totalSeconds"),
                    medians.get("visibleDecodeTokensPerSecond"),
                    medians.get("endToEndOutputTokensPerSecond"),
                ]
            )
    write_csv(
        tables_dir / "t7-workload-performance.csv",
        [
            "workload",
            "input_tokens",
            "output_tokens",
            "variant",
            "median_ttft_seconds",
            "median_total_seconds",
            "median_visible_decode_tokens_per_second",
            "median_end_to_end_output_tokens_per_second",
        ],
        t7_rows,
    )


def svg_document(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        '<rect width="100%" height="100%" fill="#ffffff"/>\n'
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;fill:#161616}'
        '.title{font-size:24px;font-weight:700}.label{font-size:15px}.small{font-size:12px;fill:#555}'
        '.axis{stroke:#777;stroke-width:1}.grid{stroke:#ddd;stroke-width:1}.w8{fill:#d94a42}.int4{fill:#315b9a}'
        '.w8point{fill:#fff;stroke:#8f211b;stroke-width:2}.int4point{fill:#fff;stroke:#173b73;stroke-width:2}'
        '</style>\n'
        f"{body}\n</svg>\n"
    )


def generate_figures(quality: dict, speed: dict, generated_dir: Path) -> None:
    figures_dir = generated_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    comparison = quality["comparison"]
    width, height = 980, 470
    left, right = 170, 900
    minimum, maximum = -4.0, 7.0

    def x_position(value: float) -> float:
        return left + (value - minimum) * (right - left) / (maximum - minimum)

    f3_parts = [
        '<text x="40" y="48" class="title">Paired quality difference: Static-W8 minus Dynamic-INT4</text>',
        '<text x="40" y="75" class="small">95% bootstrap intervals; both intervals cross zero</text>',
    ]
    for tick in range(-4, 8):
        x = x_position(float(tick))
        f3_parts.append(f'<line x1="{x:.2f}" y1="105" x2="{x:.2f}" y2="390" class="grid"/>')
        f3_parts.append(f'<text x="{x:.2f}" y="414" text-anchor="middle" class="small">{tick}</text>')
    zero_x = x_position(0.0)
    f3_parts.append(f'<line x1="{zero_x:.2f}" y1="100" x2="{zero_x:.2f}" y2="395" stroke="#111" stroke-width="2"/>')
    series = [
        ("F1", comparison["f1DifferenceFirstMinusSecond"], comparison["f1WinSignTestPValue"], 190),
        ("Exact match", comparison["emDifferenceFirstMinusSecond"], comparison["emWinSignTestPValue"], 310),
    ]
    for label, interval, p_value, y in series:
        low = x_position(interval["lower95Points"])
        high = x_position(interval["upper95Points"])
        observed = x_position(interval["observedPoints"])
        f3_parts.extend(
            [
                f'<text x="40" y="{y + 5}" class="label">{html.escape(label)}</text>',
                f'<line x1="{low:.2f}" y1="{y}" x2="{high:.2f}" y2="{y}" stroke="#315b9a" stroke-width="5"/>',
                f'<line x1="{low:.2f}" y1="{y - 10}" x2="{low:.2f}" y2="{y + 10}" stroke="#315b9a" stroke-width="2"/>',
                f'<line x1="{high:.2f}" y1="{y - 10}" x2="{high:.2f}" y2="{y + 10}" stroke="#315b9a" stroke-width="2"/>',
                f'<circle cx="{observed:.2f}" cy="{y}" r="8" fill="#d94a42"/>',
                f'<text x="{right}" y="{y + 30}" text-anchor="end" class="small">Δ {interval["observedPoints"]:.2f} points · p={p_value:.3f}</text>',
            ]
        )
    f3_parts.append('<text x="40" y="452" class="small">No equivalence test was performed.</text>')
    (figures_dir / "f3-paired-quality.svg").write_text(
        svg_document(width, height, "\n".join(f3_parts)), encoding="utf-8"
    )

    workload_order = ["business_161_60", "near_4k_3790_10", "decode_120_256"]
    workload_labels = ["161 / 60", "3,790 / 10", "120 / 256"]
    f4_parts = [
        '<text x="40" y="45" class="title">Workload-dependent latency</text>',
        '<text x="40" y="70" class="small">Input / output tokens; bars are medians and circles are individual accepted samples</text>',
    ]

    def bar_panel(field: str, title: str, top: int, panel_height: int) -> None:
        values = [
            speed["workloads"][workload]["medians"][variant][field]
            for workload in workload_order
            for variant in ("W8_ANE", "INT4_GPU")
        ]
        maximum_value = max(values) * 1.12
        base_y = top + panel_height
        f4_parts.append(f'<text x="40" y="{top - 12}" class="label">{html.escape(title)}</text>')
        f4_parts.append(f'<line x1="90" y1="{base_y}" x2="1040" y2="{base_y}" class="axis"/>')
        group_width = 290
        for index, (workload, label) in enumerate(zip(workload_order, workload_labels)):
            center = 215 + index * group_width
            for offset, variant, css in ((-38, "W8_ANE", "w8"), (38, "INT4_GPU", "int4")):
                value = speed["workloads"][workload]["medians"][variant][field]
                bar_height = value / maximum_value * (panel_height - 35)
                x = center + offset - 25
                y = base_y - bar_height
                f4_parts.append(f'<rect x="{x}" y="{y:.2f}" width="50" height="{bar_height:.2f}" class="{css}"/>')
                samples = [
                    sample[field]
                    for sample in speed["workloads"][workload]["acceptedSamples"]
                    if sample["variant"] == variant
                ]
                point_css = f"{css}point"
                for point_offset, sample in zip((-12, 0, 12), samples):
                    sample_y = base_y - sample / maximum_value * (panel_height - 35)
                    f4_parts.append(
                        f'<circle cx="{center + offset + point_offset}" cy="{sample_y:.2f}" '
                        f'r="4.5" class="{point_css}"/>'
                    )
                f4_parts.append(f'<text x="{center + offset}" y="{y - 6:.2f}" text-anchor="middle" class="small">{value:.3f}</text>')
            f4_parts.append(f'<text x="{center}" y="{base_y + 22}" text-anchor="middle" class="small">{label}</text>')

    bar_panel("ttftSeconds", "Time to first token (seconds)", 125, 195)
    bar_panel("totalSeconds", "Total generation time (seconds)", 420, 195)
    f4_parts.extend(
        [
            '<rect x="790" y="40" width="14" height="14" class="w8"/><text x="812" y="52" class="small">Static-W8</text>',
            '<rect x="900" y="40" width="14" height="14" class="int4"/><text x="922" y="52" class="small">Dynamic-INT4</text>',
        ]
    )
    (figures_dir / "f4-workload-latency.svg").write_text(
        svg_document(1100, 680, "\n".join(f4_parts)), encoding="utf-8"
    )

    f5_values = speed["storageAndMemory"]
    metrics = [
        ("Compiled bundle", f5_values["compiledModelBundleMiB"]),
        ("Peak process RSS", f5_values["peakProcessResidentMiB"]),
    ]
    f5_parts = [
        '<text x="40" y="48" class="title">Storage and peak process memory</text>',
        '<text x="40" y="75" class="small">MiB; RSS is process resident memory, not total system RAM</text>',
        '<line x1="90" y1="420" x2="840" y2="420" class="axis"/>',
    ]
    max_value = 3000.0
    for index, (label, values) in enumerate(metrics):
        center = 270 + index * 380
        for offset, variant, css in ((-55, "W8_ANE", "w8"), (55, "INT4_GPU", "int4")):
            value = values[variant]
            bar_height = value / max_value * 300
            x = center + offset - 38
            y = 420 - bar_height
            f5_parts.append(f'<rect x="{x}" y="{y:.2f}" width="76" height="{bar_height:.2f}" class="{css}"/>')
            f5_parts.append(f'<text x="{center + offset}" y="{y - 8:.2f}" text-anchor="middle" class="small">{value:,.1f}</text>')
        f5_parts.append(f'<text x="{center}" y="448" text-anchor="middle" class="label">{html.escape(label)}</text>')
    f5_parts.extend(
        [
            '<rect x="650" y="45" width="14" height="14" class="w8"/><text x="672" y="57" class="small">Static-W8</text>',
            '<rect x="760" y="45" width="14" height="14" class="int4"/><text x="782" y="57" class="small">Dynamic-INT4</text>',
        ]
    )
    (figures_dir / "f5-size-rss.svg").write_text(
        svg_document(900, 500, "\n".join(f5_parts)), encoding="utf-8"
    )


def write_generated_manifest(generated_dir: Path) -> None:
    manifest_path = generated_dir / "MANIFEST.sha256"
    entries = []
    for path in sorted(generated_dir.rglob("*")):
        if path.is_file() and path != manifest_path:
            entries.append(f"{sha256(path)}  {path.relative_to(generated_dir).as_posix()}")
    manifest_path.write_text("\n".join(entries) + "\n", encoding="utf-8")


def validate_generated_manifest(generated_dir: Path) -> None:
    manifest_path = generated_dir / "MANIFEST.sha256"
    if not manifest_path.is_file():
        raise PipelineError("Generated manifest is missing")
    listed: set[str] = set()
    for line_number, line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise PipelineError(f"Malformed generated manifest line {line_number}")
        expected, relative_path = match.groups()
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise PipelineError(f"Invalid generated manifest path: {relative_path}")
        normalized = relative.as_posix()
        if normalized in listed:
            raise PipelineError(f"Duplicate generated manifest path: {normalized}")
        listed.add(normalized)
        require_hash(generated_dir / relative, expected)

    actual = {
        path.relative_to(generated_dir).as_posix()
        for path in generated_dir.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if listed != actual:
        missing = sorted(actual - listed)
        stale = sorted(listed - actual)
        raise PipelineError(
            f"Generated manifest file-set mismatch: unlisted={missing}, missing={stale}"
        )


def run_tests(generated_dir: Path) -> None:
    environment = os.environ.copy()
    environment["ANALYSIS_GENERATED_DIR"] = str(generated_dir)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            str(ANALYSIS_DIR / "tests"),
            "-p",
            "test_*.py",
        ],
        cwd=ROOT,
        env=environment,
        check=True,
    )


def resolve_generated_dir(argument: Path) -> Path:
    candidate = argument if argument.is_absolute() else ROOT / argument
    generated_dir = candidate.resolve()
    if (
        generated_dir.parent != ANALYSIS_DIR
        or not generated_dir.name.startswith("generated")
    ):
        raise PipelineError(
            "--generated-dir must be a direct child of analysis/ whose name starts "
            "with 'generated'"
        )
    return generated_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--generated-dir", type=Path, default=DEFAULT_GENERATED_DIR)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--test-only", action="store_true")
    arguments = parser.parse_args()

    lock = read_json(LOCK_PATH)
    require_hash(PUBLIC_STATUS_PATH, lock["publicStatusLockSHA256"])
    verify_runtime(lock)
    generated_dir = resolve_generated_dir(arguments.generated_dir)
    if arguments.test_only:
        validate_generated_manifest(generated_dir)
        run_tests(generated_dir)
        print("PIPELINE_TESTS_OK")
        return 0

    work_dir = arguments.work_dir.resolve()
    repositories_dir = work_dir / "repositories"
    downloads_dir = work_dir / "downloads"
    repositories_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    repository_paths = {}
    for name, spec in lock["repositories"].items():
        target = repositories_dir / name
        ensure_repository(name, spec, target, arguments.offline)
        repository_paths[name] = target

    dataset_spec = lock["dataset"]
    dataset_path = downloads_dir / "cmrc2018_dev_official.json"
    ensure_download(
        dataset_spec["downloadURL"],
        dataset_path,
        dataset_spec["officialSourceSHA256"],
        arguments.offline,
    )

    public_w8_spec = lock["remoteFiles"]["w8PublicDeviceValidation"]
    public_w8_path = downloads_dir / "w8-public-device-validation.json"
    ensure_download(
        public_w8_spec["url"],
        public_w8_path,
        public_w8_spec["sha256"],
        arguments.offline,
    )

    if generated_dir.exists():
        shutil.rmtree(generated_dir)
    generated_dir.mkdir(parents=True)

    quality = rebuild_and_score_quality(
        lock,
        repository_paths["comparison"],
        dataset_path,
        generated_dir,
    )
    speed = extract_speed(repository_paths["comparison"], generated_dir)
    generate_tables(
        repository_paths["w8"],
        repository_paths["comparison"],
        public_w8_path,
        quality,
        speed,
        generated_dir,
    )
    generate_figures(quality, speed, generated_dir)

    provenance = {
        "schemaVersion": 1,
        "sourceLockSHA256": sha256(LOCK_PATH),
        "publicStatusLockSHA256": sha256(PUBLIC_STATUS_PATH),
        "pipelineSHA256": sha256(Path(__file__)),
        "runtime": lock["runtime"],
        "repositoryCommits": {
            name: spec["commit"] for name, spec in lock["repositories"].items()
        },
        "newModelOutputsCreated": False,
        "newDeviceMeasurementsCreated": False,
    }
    write_json(generated_dir / "provenance.json", provenance)
    write_generated_manifest(generated_dir)
    validate_generated_manifest(generated_dir)
    run_tests(generated_dir)

    print("PIPELINE_OK")
    print(f"source_lock_sha256={sha256(LOCK_PATH)}")
    print(f"quality_sha256={sha256(generated_dir / 'quality-recomputed.json')}")
    print(f"generated_manifest_sha256={sha256(generated_dir / 'MANIFEST.sha256')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PipelineError, subprocess.CalledProcessError) as error:
        print(f"PIPELINE_ABORT: {error}", file=sys.stderr)
        raise SystemExit(1)
