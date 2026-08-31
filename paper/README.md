# Qwen3-1.7B Core AI Technical Report

This directory is the independent research workspace for a technical report on
deploying Qwen3-1.7B on iPhone through Apple Core AI.

Authors: Yi Shi ([ORCID 0009-0002-7894-2703](https://orcid.org/0009-0002-7894-2703),
`massif0601@gmail.com`) and Mengni Wu
([ORCID 0009-0004-7465-9067](https://orcid.org/0009-0004-7465-9067),
`mengninolab@gmail.com`). Both authors are independent researchers.

The report documents the completed implementation and evaluation of two 4K
deployment profiles on the same iPhone 15 Pro:

- W8 projections, fixed FP16 KV, static-shape execution, Neural Engine preferred;
- INT4 block-32 weights, growing FP16 KV, dynamic execution, GPU preferred.

The comparison is between deployable system profiles. It does not attribute an
observed difference to precision, KV strategy, graph shape, or compute device
in isolation.

## Current status

- [`REPORT_PROTOCOL_V1.md`](REPORT_PROTOCOL_V1.md) freezes the claims,
  evidence map, provenance boundaries, and writing workflow.
- [`REPORT_PROTOCOL_V2.md`](REPORT_PROTOCOL_V2.md) separately governs the
  post-review W8 load-compatibility observation; it is not presented as
  preregistration or part of the historical comparison.
- [`EVIDENCE_INDEX.md`](EVIDENCE_INDEX.md) maps every admitted manuscript claim
  to a versioned source, exact evidence object, allowed wording, and limit.
- [`analysis/README.md`](analysis/README.md) documents the deterministic
  evidence pipeline that rebuilds paper tables and figures without new model
  or device runs.
- [`evidence/fidelity-v2/README.md`](evidence/fidelity-v2/README.md) documents
  the corrected formal authoring-model fidelity run; its public summary is the
  sole numerical source for manuscript Table T3.
- [`evidence/w8-compatibility/README.md`](evidence/w8-compatibility/README.md)
  documents the sanitized event-level records for the post-review load-only
  diagnostic and their boundary to the private source captures.
- [`manuscript/qwen3-coreai-report.tex`](manuscript/qwen3-coreai-report.tex) is
  the English technical report; [`manuscript/README.md`](manuscript/README.md)
  documents its reproducible build and visual-review gates.
- [`manuscript/CLAIM_AUDIT.md`](manuscript/CLAIM_AUDIT.md) records the final
  sentence-level claim-to-evidence review.
- [`manuscript/output/pdf/qwen3-coreai-report.pdf`](manuscript/output/pdf/qwen3-coreai-report.pdf)
  is the compiled report PDF.
- The main comparison reuses completed public experiments. A later, separately
  labeled load-only diagnostic is recorded in
  [`W8_COMPATIBILITY_OBSERVATION_1.md`](W8_COMPATIBILITY_OBSERVATION_1.md).
- No e1/Marker product source belongs in this repository.

## Explicit scope boundary

Product-only model variants, product integration, background execution,
Qwen3.5, and other device architectures are outside this report.
