# Manuscript build and review

The manuscript is an English technical report governed by
[`../REPORT_PROTOCOL_V1.md`](../REPORT_PROTOCOL_V1.md). It reuses frozen public
evidence and does not authorize new model outputs or device measurements.

## Build

Requirements:

- Python 3;
- the locked analysis environment documented in [`../analysis/README.md`](../analysis/README.md);
- Google Chrome `150.0.7871.115` for SVG-to-PDF conversion;
- [Tectonic](https://tectonic-typesetting.github.io/) `0.17.0` for LaTeX compilation.

Evidence reconstruction and document compilation are separate operations.
Rebuild the quantitative evidence first when a pipeline, source lock, or input
has changed:

```sh
./analysis/run.sh
```

Then compile the manuscript from the checked generated outputs:

Run:

```sh
TECTONIC=/absolute/path/to/tectonic ./manuscript/build.sh
```

If the checked-in vector figure PDFs have already passed visual review and no
figure source changed:

```sh
TECTONIC=/absolute/path/to/tectonic ./manuscript/build.sh --use-pre-rendered
```

The final PDF is written to
`manuscript/output/pdf/qwen3-coreai-report.pdf`.

## Review controls

- `CLAIM_AUDIT.md` is the human sentence-level review ledger.
- `claim_audit.py` checks evidence IDs, citations, required sections, all seven
  tables, all five figures, provenance disclosure, forbidden claim classes,
  unresolved placeholders, and generated-asset hashes.
- `generated/MANIFEST.sha256` locks every generated manuscript asset.
- Evidence markers such as `CL-14` remain in the LaTeX source for the claim
  audit but are hidden in the submission PDF.
- The build fails on overfull boxes, undefined control sequences, undefined
  citations, or undefined cross-references; underfull warnings from narrow
  table columns and long bibliography URLs remain non-fatal and are checked
  visually.

Compilation checks the committed analysis outputs and proves that the paper
and its references resolve; it does not rerun evidence reconstruction. Final
acceptance also requires rendering every PDF page to an image and inspecting
it for clipping, overlap, unreadable tables, and blank pages.
