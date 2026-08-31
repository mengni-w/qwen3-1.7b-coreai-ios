#!/usr/bin/env python3
"""Generate manuscript tables and figure PDFs from frozen normalized evidence."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT = ROOT / "manuscript"
EVIDENCE = ROOT / "analysis" / "generated"
OUTPUT = MANUSCRIPT / "generated"
EXPECTED_CHROME_VERSION = "Google Chrome 150.0.7871.115"
EXPECTED_GENERATED_FILES = {
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


class AssetError(RuntimeError):
    pass


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tex(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in text)


def table_document(caption: str, label: str, claims: str, body: str) -> str:
    return (
        "\\begin{table}[H]\n"
        "\\centering\n"
        "\\small\n"
        "\\setlength{\\tabcolsep}{4pt}\n"
        f"{body}\n"
        f"\\caption{{{caption} \\evidence{{{claims}}}}}\n"
        f"\\label{{{label}}}\n"
        "\\end{table}\n"
    )


def generate_tables() -> None:
    out = OUTPUT / "tables"
    out.mkdir(parents=True, exist_ok=True)

    t1 = read_json(EVIDENCE / "tables" / "t1-public-status.json")
    rows = []
    for row in t1["rows"]:
        rows.append(
            "{} & {} & {} & {} \\\\".format(
                tex(row["work"]),
                tex(row["route"]),
                tex(row["publishedEvidence"]),
                tex(row["comparisonBoundary"]),
            )
        )
    body = "\n".join(
        [
            r"\begin{tabularx}{\textwidth}{@{}"
            r">{\raggedright\arraybackslash}p{0.17\textwidth}"
            r">{\raggedright\arraybackslash}p{0.19\textwidth}"
            r">{\raggedright\arraybackslash}X "
            r">{\raggedright\arraybackslash}p{0.23\textwidth}@{}}",
            r"\toprule",
            r"Work & Route & Public evidence & Boundary \\",
            r"\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )
    audited = t1["auditedAt"][:10]
    write(
        out / "t1-public-status.tex",
        table_document(
            f"Public Qwen3-1.7B Core AI status audited {audited}. Community model-card claims are contextual, not re-measured results.",
            "tab:public-status",
            "CL-01,CL-02,CL-24,CL-25",
            body,
        ),
    )

    t2 = read_json(EVIDENCE / "tables" / "t2-profile-definitions.json")
    w8 = t2["profiles"]["W8_ANE"]
    int4 = t2["profiles"]["INT4_GPU"]
    profile_rows = [
        ("Transformer weights", w8["transformerWeights"], int4["transformerWeights"]),
        ("Embedding", w8["embedding"], int4["embedding"]),
        ("Compute", w8["compute"], int4["compute"]),
        ("KV cache", w8["kvCache"], int4["kvCache"]),
        ("Graph", w8["graphShape"], int4["graphShape"]),
        ("Context cap", f'{w8["contextTokens"]:,} tokens', f'{int4["contextTokens"]:,} tokens'),
        ("Preferred compute", w8["preferredCompute"], int4["preferredCompute"]),
        ("AOT target", t2["common"]["architecture"], t2["common"]["architecture"]),
    ]
    body = "\n".join(
        [
            r"\begin{tabularx}{\textwidth}{@{}p{0.21\textwidth}XX@{}}",
            r"\toprule",
            r"Dimension & Static-W8 & Dynamic-INT4 \\",
            r"\midrule",
            *[
                f"{tex(name)} & {tex(first)} & {tex(second)} \\\\"
                for name, first, second in profile_rows
            ],
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )
    write(
        out / "t2-profile-definitions.tex",
        table_document(
            "Compared deployment profiles. The rows are coupled system choices, not independently randomized factors.",
            "tab:profiles",
            "CL-03,CL-04,CL-11",
            body,
        ),
    )

    t3 = read_json(EVIDENCE / "tables" / "t3-w8-fidelity.json")
    fidelity_rows = []
    for key, label in (("w8_tuning", "Tuning"), ("w8_frozen_holdout", "Frozen holdout")):
        value = t3["evaluations"][key]
        fidelity_rows.append(
            f'{label} & {value["mean_cosine"]:.6f} & {value["minimum_cosine"]:.6f} & '
            f'{100 * value["top1_agreement"]:.2f}\\% & {value["mean_nll_delta"]:.6f} \\\\'
        )
    body = "\n".join(
        [
            r"\begin{tabular}{@{}lrrrr@{}}",
            r"\toprule",
            r"Evaluation & Mean cosine & Min. cosine & Top-1 agree. & Mean $\Delta$NLL \\",
            r"\midrule",
            *fidelity_rows,
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )
    write(
        out / "t3-w8-fidelity.tex",
        table_document(
            "W8 authoring-model conversion fidelity relative to the frozen uncompressed reference. Values are case-level macro-averages from the corrected formal fidelity-v2 run, not compiled-device logits or a capability benchmark.",
            "tab:w8-fidelity",
            "CL-06,CL-07",
            body,
        ),
    )

    t4 = read_json(EVIDENCE / "tables" / "t4-w8-device-evidence.json")
    historical = t4["historicalArtifact"]
    public = t4["publicArtifact"]
    device_rows = [
        ("Historical suites", "4 complete", "6 per suite", "Pass; zero recorded hard failures"),
        (
            "Historical final suite",
            f'{historical["suite"]["final_peak_resident_mib"]:,.1f} MiB peak RSS',
            f'{historical["suite"]["after_unload_resident_mib"]:,.1f} MiB after unload',
            "A-W8-HISTORICAL",
        ),
        (
            "Historical trace",
            str(historical["trace"]["mpsgraph_program_intervals"]),
            str(historical["trace"]["apple_neural_engine_prediction_intervals"]),
            "ANE participation; non-exclusive",
        ),
        (
            "Public rebuild suite",
            f'{public["suite"]["cases_completed"]} / 6 cases',
            f'{public["suite"]["peak_resident_mib"]:,.1f} MiB peak RSS',
            "A-W8-PUBLIC",
        ),
        (
            "Public near-4K case",
            "3,790 input / 10 output",
            f'{public["suite"]["cases"][4]["ttft_seconds"]:.3f} s TTFT',
            "Tail marker retrieved",
        ),
    ]
    body = "\n".join(
        [
            r"\begin{tabularx}{\textwidth}{@{}p{0.22\textwidth}p{0.22\textwidth}p{0.22\textwidth}X@{}}",
            r"\toprule",
            r"Evidence object & Measure A & Measure B & Interpretation / identity \\",
            r"\midrule",
            *[
                f"{tex(a)} & {tex(b)} & {tex(c)} & {tex(d)} \\\\"
                for a, b, c, d in device_rows
            ],
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )
    write(
        out / "t4-w8-device-evidence.tex",
        table_document(
            "Physical-device evidence on iPhone 15 Pro / iOS 27. Historical and public W8 payloads use the same mechanism but are not byte-identical.",
            "tab:device-evidence",
            "CL-08,CL-09,CL-10,CL-22",
            body,
        ),
    )

    t5 = read_json(EVIDENCE / "tables" / "t5-paired-quality.json")
    quality_rows = []
    for key, label in (("W8_ANE", "Static-W8"), ("INT4_GPU", "Dynamic-INT4")):
        summary = t5["variants"][key]["summary"]
        quality_rows.append(
            f'{label} & {summary["total"]} & {summary["em"]:.2f} & {summary["f1"]:.2f} '
            f'& {summary["exactMatchCount"]} \\\\'
        )
    comparison = t5["comparison"]
    quality_rows.append(
        f'Static-W8 $-$ Dynamic-INT4 & {comparison["pairedSamples"]} & '
        f'{comparison["emDifferenceFirstMinusSecond"]["observedPoints"]:+.2f} & '
        f'{comparison["f1DifferenceFirstMinusSecond"]["observedPoints"]:+.2f} & -- \\\\'
    )
    body = "\n".join(
        [
            r"\begin{tabular}{@{}lrrrr@{}}",
            r"\toprule",
            r"Profile & $n$ & EM & F1 & Exact matches \\",
            r"\midrule",
            *quality_rows,
            r"\bottomrule",
            r"\end{tabular}",
            r"\vspace{3pt}\par\footnotesize W8-minus-INT4 95\% bootstrap intervals: "
            + f'EM [{comparison["emDifferenceFirstMinusSecond"]["lower95Points"]:+.2f}, '
            + f'{comparison["emDifferenceFirstMinusSecond"]["upper95Points"]:+.2f}], '
            + f'F1 [{comparison["f1DifferenceFirstMinusSecond"]["lower95Points"]:+.2f}, '
            + f'{comparison["f1DifferenceFirstMinusSecond"]["upper95Points"]:+.2f}]. '
            + f'Sign-test $p$: EM {comparison["emWinSignTestPValue"]:.3f}, '
            + f'F1 {comparison["f1WinSignTestPValue"]:.3f}.',
        ]
    )
    write(
        out / "t5-paired-quality.tex",
        table_document(
            "Paired CMRC2018 quality on the frozen 300-example subset. Both intervals include zero; no equivalence test was performed.",
            "tab:paired-quality",
            "CL-12,CL-13,CL-14",
            body,
        ),
    )

    t6 = read_json(EVIDENCE / "tables" / "t6-size-rss.json")
    size_rows = []
    for key, label in (
        ("compiledModelBundleMiB", "Compiled bundle"),
        ("peakProcessResidentMiB", "Peak process RSS"),
    ):
        values = t6["measurements"][key]
        reduction = values["W8_ANE"] - values["INT4_GPU"]
        percentage = reduction / values["W8_ANE"] * 100
        size_rows.append(
            f'{label} & {values["W8_ANE"]:,.1f} & {values["INT4_GPU"]:,.1f} '
            f'& {reduction:,.1f} ({percentage:.1f}\\%) \\\\'
        )
    body = "\n".join(
        [
            r"\begin{tabular}{@{}lrrr@{}}",
            r"\toprule",
            r"Metric (MiB) & Static-W8 & Dynamic-INT4 & Dynamic-INT4 reduction \\",
            r"\midrule",
            *size_rows,
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )
    write(
        out / "t6-size-rss.tex",
        table_document(
            "Compiled resource-directory logical size and peak process resident memory in the disclosed benchmark.",
            "tab:size-rss",
            "CL-15,CL-16",
            body,
        ),
    )

    t7 = read_json(EVIDENCE / "tables" / "t7-workload-performance.json")
    labels = {
        "business_161_60": "161 / 60",
        "near_4k_3790_10": "3,790 / 10",
        "decode_120_256": "120 / 256",
    }
    performance_rows = []
    for workload_key in ("business_161_60", "near_4k_3790_10", "decode_120_256"):
        workload = t7["workloads"][workload_key]
        for profile_key, profile_label in (("W8_ANE", "Static-W8"), ("INT4_GPU", "Dynamic-INT4")):
            medians = workload["medians"][profile_key]
            decode = medians.get("visibleDecodeTokensPerSecond")
            decode_text = "--" if decode is None else f"{decode:.3f}"
            performance_rows.append(
                f'{labels[workload_key]} & {profile_label} & {medians["ttftSeconds"]:.3f} '
                f'& {medians["totalSeconds"]:.3f} & {decode_text} \\\\'
            )
    body = "\n".join(
        [
            r"\begin{tabular}{@{}llrrr@{}}",
            r"\toprule",
            r"Input / output & Profile & TTFT (s) & Total (s) & Visible decode (tok/s) \\",
            r"\midrule",
            *performance_rows,
            r"\bottomrule",
            r"\end{tabular}",
        ]
    )
    write(
        out / "t7-workload-performance.tex",
        table_document(
            "Workload medians after one warm-up and three accepted samples. Near-4K decode rate is omitted because only nine visible tokens remained.",
            "tab:workload-performance",
            "CL-17,CL-18,CL-19,CL-20",
            body,
        ),
    )

    t8 = read_json(EVIDENCE / "tables" / "t8-w8-compatibility.json")
    old = t8["oldPublicArtifact"]
    current = t8["currentCandidate"]
    compatibility_rows = [
        (
            "Earlier public AOT",
            f'{old["producer"]}; {old["compiledMainSHA256"][:12]}...',
            str(old["attempts"]),
            (
                "Both stopped during ANECCompileOffline; the second followed a "
                "full-reboot request and observed reconnection"
            ),
        ),
        (
            "Current-toolchain candidate",
            f'{current["producer"]}; {current["compiledMainSHA256"][:12]}...',
            str(current["attempts"]),
            (
                f'Load {current["loadSeconds"]:.3f} s; peak process RSS '
                f'{current["peakProcessResidentMiB"]:,.1f} MiB; unload completed; exit 0'
            ),
        ),
    ]
    body = "\n".join(
        [
            r"\begin{tabularx}{\textwidth}{@{}p{0.20\textwidth}p{0.25\textwidth}p{0.08\textwidth}X@{}}",
            r"\toprule",
            r"Artifact & Producer; compiled-main SHA & Loads & Observation \\",
            r"\midrule",
            *[
                f"{tex(artifact)} & {tex(identity)} & {tex(attempts)} & {tex(observation)} \\\\"
                for artifact, identity, attempts, observation in compatibility_rows
            ],
            r"\bottomrule",
            r"\end{tabularx}",
        ]
    )
    write(
        out / "t8-w8-compatibility.tex",
        table_document(
            (
                "Supplementary load-only compatibility observations on one iPhone 15 Pro "
                "running iOS 27 build 24A5424a. The candidate result is not a cold-start "
                "benchmark, generation test, or Instruments trace; cache state was "
                "uncontrolled, and artifact bytes and compiler producer both changed."
            ),
            "tab:w8-compatibility",
            "CL-28,CL-29",
            body,
        ),
    )


def svg_document(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        '<rect width="100%" height="100%" fill="#ffffff"/>\n'
        '<style>text{font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;fill:#171717}'
        '.title{font-size:25px;font-weight:700}.label{font-size:16px;font-weight:600}.body{font-size:14px}'
        '.small{font-size:12px;fill:#555}.box{fill:#f7f7f5;stroke:#777;stroke-width:1.5}'
        '.w8{fill:#f9ecea;stroke:#d94a42;stroke-width:2}.int4{fill:#edf2fa;stroke:#315b9a;stroke-width:2}'
        '.arrow{stroke:#333;stroke-width:2;fill:none}</style>\n'
        f"{body}\n</svg>\n"
    )


def generate_architecture_figures() -> list[Path]:
    figure_dir = OUTPUT / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    t2 = read_json(EVIDENCE / "tables" / "t2-profile-definitions.json")
    common = t2["common"]
    w8 = t2["profiles"]["W8_ANE"]
    int4 = t2["profiles"]["INT4_GPU"]

    stages = [
        ("Frozen source", "Qwen3-1.7B", common["baseRevision"][:8]),
        ("Apple-main onboarding", "preset + metadata", "recipe + tests"),
        ("Core AI export", "static .aimodel", "FP16 fixed KV"),
        ("h16p AOT", "ANE preferred", "34 functions"),
        ("iPhone runtime", "CoreAILanguageModel", "LanguageModelSession"),
        ("Validation", "six-case suites", "ANE trace"),
    ]
    f1 = [
        '<text x="40" y="45" class="title">Static W8 authoring-to-device path</text>',
        '<text x="40" y="70" class="small">Version-locked source, recipe, AOT target, runtime, and evidence</text>',
    ]
    for index, (title, first, second) in enumerate(stages):
        x = 35 + index * 175
        f1.extend(
            [
                f'<rect x="{x}" y="125" width="145" height="120" rx="8" class="box"/>',
                f'<text x="{x + 72.5}" y="157" text-anchor="middle" class="label">{html.escape(title)}</text>',
                f'<text x="{x + 72.5}" y="190" text-anchor="middle" class="body">{html.escape(first)}</text>',
                f'<text x="{x + 72.5}" y="216" text-anchor="middle" class="small">{html.escape(second)}</text>',
            ]
        )
        if index < len(stages) - 1:
            f1.extend(
                [
                    f'<line x1="{x + 145}" y1="185" x2="{x + 170}" y2="185" class="arrow"/>',
                    f'<polygon points="{x + 170},185 {x + 160},179 {x + 160},191" fill="#333"/>',
                ]
            )
    f1.extend(
        [
            '<rect x="210" y="300" width="680" height="70" rx="8" class="w8"/>',
            f'<text x="550" y="330" text-anchor="middle" class="label">{html.escape(w8["transformerWeights"])}</text>',
            f'<text x="550" y="354" text-anchor="middle" class="body">{html.escape(w8["embedding"])} · {html.escape(w8["kvCache"])} · {w8["contextTokens"]:,} tokens</text>',
        ]
    )
    f1_path = figure_dir / "f1-static-pipeline.svg"
    write(f1_path, svg_document(1100, 410, "\n".join(f1)))

    f2 = [
        '<text x="40" y="45" class="title">Coupled deployment profiles</text>',
        '<text x="40" y="70" class="small">The comparison does not isolate precision, graph shape, KV strategy, or compute unit causally</text>',
        '<rect x="45" y="115" width="480" height="315" rx="10" class="w8"/>',
        '<rect x="575" y="115" width="480" height="315" rx="10" class="int4"/>',
        '<text x="285" y="155" text-anchor="middle" class="title">Static-W8</text>',
        '<text x="815" y="155" text-anchor="middle" class="title">Dynamic-INT4</text>',
    ]
    aspects = [
        ("Weights", w8["transformerWeights"], int4["transformerWeights"]),
        ("Embedding", w8["embedding"], int4["embedding"]),
        ("KV state", w8["kvCache"], int4["kvCache"]),
        ("Graph", w8["graphShape"], int4["graphShape"]),
        ("AOT", f'{common["architecture"]}; {w8["preferredCompute"]}', f'{common["architecture"]}; {int4["preferredCompute"]}'),
    ]
    for index, (name, first, second) in enumerate(aspects):
        y = 205 + index * 47
        f2.append(f'<text x="75" y="{y}" class="label">{html.escape(name)}</text>')
        f2.append(f'<text x="185" y="{y}" class="body">{html.escape(str(first))}</text>')
        f2.append(f'<text x="605" y="{y}" class="label">{html.escape(name)}</text>')
        f2.append(f'<text x="715" y="{y}" class="body">{html.escape(str(second))}</text>')
    f2.append('<text x="550" y="475" text-anchor="middle" class="small">Shared: base revision, tokenizer, 4,096-token cap, h16p device class, iOS 27, and benchmark controls</text>')
    f2_path = figure_dir / "f2-profile-comparison.svg"
    write(f2_path, svg_document(1100, 505, "\n".join(f2)))
    return [f1_path, f2_path]


def find_chrome() -> Path | None:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    executable = shutil.which("google-chrome") or shutil.which("chromium")
    return Path(executable) if executable else None


def verify_chrome(chrome: Path) -> None:
    observed = subprocess.run(
        [str(chrome), "--version"],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()
    if observed != EXPECTED_CHROME_VERSION:
        raise AssetError(
            f"Chrome version mismatch: expected {EXPECTED_CHROME_VERSION}, observed {observed}"
        )


def convert_svg_to_pdf(svg: Path, pdf: Path, chrome: Path) -> None:
    match = re.search(r'<svg[^>]*width="(\d+)"[^>]*height="(\d+)"', svg.read_text(encoding="utf-8"))
    if not match:
        raise AssetError(f"SVG has no integer width/height: {svg}")
    width, height = int(match.group(1)), int(match.group(2))
    temp_dir = MANUSCRIPT / "tmp" / "pdfs" / svg.stem
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True)
    wrapper = temp_dir / "wrapper.html"
    source = svg.read_text(encoding="utf-8")
    wrapper.write_text(
        "<!doctype html><meta charset=\"utf-8\"><style>"
        f"@page{{size:{width}px {height}px;margin:0}}"
        f"html,body{{margin:0;width:{width}px;height:{height}px;overflow:hidden}}"
        "svg{display:block}</style>" + source,
        encoding="utf-8",
    )
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.unlink(missing_ok=True)
    profile = temp_dir / "chrome-profile"
    process = subprocess.Popen(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={pdf}",
            wrapper.as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline:
            if pdf.is_file() and pdf.stat().st_size >= 1000:
                break
            if process.poll() is not None:
                break
            time.sleep(0.2)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
    if not pdf.is_file() or pdf.stat().st_size < 1000:
        raise AssetError(f"Chrome did not create a usable PDF for {svg}")


def generate_figures(render: bool) -> None:
    architecture = generate_architecture_figures()
    evidence_figures = [
        EVIDENCE / "figures" / "f3-paired-quality.svg",
        EVIDENCE / "figures" / "f4-workload-latency.svg",
        EVIDENCE / "figures" / "f5-size-rss.svg",
    ]
    sources = architecture + evidence_figures
    if not render:
        missing = [source.stem for source in sources if not (OUTPUT / "figures" / f"{source.stem}.pdf").is_file()]
        if missing:
            raise AssetError(f"Pre-rendered figure PDFs are missing: {', '.join(missing)}")
        return
    chrome = find_chrome()
    if chrome is None:
        raise AssetError("Chrome or Chromium is required to render generated SVG figures")
    verify_chrome(chrome)
    for source in sources:
        convert_svg_to_pdf(source, OUTPUT / "figures" / f"{source.stem}.pdf", chrome)


def write_manifest() -> None:
    manifest = OUTPUT / "MANIFEST.sha256"
    paths = [path for path in sorted(OUTPUT.rglob("*")) if path.is_file() and path != manifest]
    actual = {path.relative_to(OUTPUT).as_posix() for path in paths}
    if actual != EXPECTED_GENERATED_FILES:
        raise AssetError(
            "generated manuscript file-set mismatch: "
            f"unexpected={sorted(actual - EXPECTED_GENERATED_FILES)}, "
            f"missing={sorted(EXPECTED_GENERATED_FILES - actual)}"
        )
    manifest.write_text(
        "\n".join(f"{sha256(path)}  {path.relative_to(OUTPUT).as_posix()}" for path in paths) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-pre-rendered", action="store_true")
    arguments = parser.parse_args()
    generate_tables()
    generate_figures(render=not arguments.use_pre_rendered)
    write_manifest()
    print("MANUSCRIPT_ASSETS_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssetError, subprocess.CalledProcessError) as error:
        print(f"MANUSCRIPT_ASSETS_ABORT: {error}", file=sys.stderr)
        raise SystemExit(1)
