# Manuscript build and review

The manuscript is an English technical report governed by
[`../REPORT_PROTOCOL_V1.md`](../REPORT_PROTOCOL_V1.md) and the explicitly
separated supplementary protocols. Its deterministic build performs no model
inference or device measurement; newly admitted evidence remains governed by
its own protocol.

## Build

Requirements:

- Python 3;
- the locked analysis environment documented in [`../analysis/README.md`](../analysis/README.md);
- Google Chrome `151.0.7922.174` for SVG-to-PDF conversion;
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
CHROME=/absolute/path/to/chrome-151 \
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
- `claim_audit.py` checks evidence IDs, citations, required sections, all eight
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

## arXiv source package

Create the minimal upload archive, containing only the main TeX file,
bibliography, eight generated table fragments, five figure PDFs, a short upload
note, and its manifest:

```sh
python3 manuscript/package_arxiv.py \
  --tectonic /absolute/path/to/tectonic-0.17.0
```

The archive is written to
`manuscript/output/arxiv/qwen3-coreai-report-arxiv.tar.gz`. Upload the extracted
contents at the archive root; do not upload the repository tree or
`manuscript/tmp`. The local compile check does not replace arXiv's own TeX Live
preview, which must be inspected before final submission.
