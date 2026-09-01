# Qwen3-1.7B on Apple Core AI for iOS

This repository documents a version-pinned Qwen3-1.7B integration with Apple's
`coreai-models` iOS path.

> **Conversion-fidelity result:** the formal fidelity-v2 W8 holdout reached
> `0.996897` mean logits cosine, `0.953391` minimum cosine, `96.97%` top-1
> agreement, and `0.008880` mean candidate-minus-reference NLL delta against
> the uncompressed authoring-model reference. Multiple W4 and mixed W4/W8
> candidates were rejected before this mechanism was frozen.

At the version-pinned Apple revision, no Qwen3-1.7B iOS preset was listed. This
repository evaluates the following configuration:

- Qwen3-1.7B;
- 8-bit per-tensor K-means palettization for transformer projection weights;
- separate INT8 quantization for the tied embedding table;
- FP16 compute and a fixed-size FP16 KV cache;
- 4,096-token context;
- `h16p` AOT specialization;
- physical-device validation on iPhone 15 Pro running iOS 27.

This work originated while building the on-device privacy engine for **e¹
(E to the one)**. The repository is intentionally standalone: it contains no
product source, model weights, tokenizer payloads, compiled models, signing
material, device identifiers, or user data.

## Download the published model artifact

The complete, directly downloadable Core AI model bundle is published on
Hugging Face:

**[massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p](https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p)**

```bash
hf download massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p \
  --revision 75bbe06906cb5d953e602e3e4fb6364187c81822 \
  --local-dir Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p
```

This command pins `A-W8-CURRENT`, the artifact used by Run J. The Hugging Face
repository contains the compiled `h16p` artifact, tokenizer, frozen recipe,
checksums, machine-readable evidence, and integration example.
This GitHub repository remains the source for the reproducible onboarding
patch, tests, methodology, and Apple contribution material.

Three W8 artifact identities are used throughout this repository:

- `A-W8-HISTORICAL`: compiled main
  `0c2dfcfeaae195386f1e61c05e0cf2b4a1ce6ecda1c321803afc0019b1d886d7`,
  used by the historical device suites, trace, and CMRC2018 comparison;
- `A-W8-JULY-PUBLIC`: Hub revision
  `466ebe2e5cec125fa113ea71503add41bba581a8`, compiled main
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`,
  used by the July six-case public-artifact suite and the later compatibility
  diagnostic;
- `A-W8-CURRENT`: Hub revision
  `75bbe06906cb5d953e602e3e4fb6364187c81822`, compiled main
  `09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`,
  used by the accepted Run J generation and speed measurements.

They share the checkpoint and W8 recipe but are not byte-interchangeable. In
the earlier load-only diagnostic on iOS 27 build `24A5424a`,
`A-W8-JULY-PUBLIC` stopped during `ANECCompileOffline` twice, whereas
`A-W8-CURRENT` loaded and unloaded once. That protocol did not perform
generation or tracing. Run J later performed generation with the exact same
`A-W8-CURRENT` compiled payload, so the load-only boundary must not be read as
an artifact-wide absence of generation evidence. Neither run isolates an iOS,
compiler, export, or memory cause for the July compatibility result.

## Status

The model recipe, export path, AOT artifact, quality checks, and physical-device
runtime have been validated for the recorded artifacts and environments. The reference onboarding patch applies cleanly to
Apple `coreai-models` main at:

`04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`

Validation against that main revision completed with:

- 28 focused unit tests passed;
- 42 related iOS conversion tests collected;
- Ruff passed;
- the registered preset dry-run resolved to W8, FP16, 4,096 context, and
  embedding quantization enabled.

A subsequent Xcode 27 Beta 6 run completed the full export and `h16p` AOT
compilation at the same pinned Apple commit. The resulting `A-W8-CURRENT`
artifact is published at the revision pinned above and completed Run J. It
does not replace the binaries used by the historical device and CMRC2018
results.

Apple's current repository does not accept code pull requests. The intended
upstream channel is a **Model request** issue; `MODEL_REQUEST.md` contains the
copy-ready issue fields.

## Why this is a distinct contribution

Community Qwen3-1.7B Core AI artifacts now exist on Hugging Face, but they
solve different deployment problems:

- [`mlboydaisuke/qwen3-1.7b-CoreAI-official`](https://huggingface.co/mlboydaisuke/qwen3-1.7b-CoreAI-official)
  publishes a dynamic INT4 GPU bundle specialized for `h18p` and reports an
  eight-question prompt check on iPhone 17 Pro. Its model card explicitly says
  that its static ANE export did not invoke successfully, so it intentionally
  ships the GPU path.
- [`kevinqz/Qwen3-1.7B-CoreAI`](https://huggingface.co/kevinqz/Qwen3-1.7B-CoreAI)
  publishes a third-party fabric-generated INT8 `.aimodel`. Its reproduction
  manifest exports the macOS path and records no AOT target; its model card
  reports that numeric accuracy was not run and that iPhone throughput was
  still pending at the cited revision.

This GitHub repository does not redistribute a compiled model;
`A-W8-CURRENT`, the artifact used by Run J, is published separately at the
[revision-pinned Hugging Face tree](https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p/tree/75bbe06906cb5d953e602e3e4fb6364187c81822).
The GitHub repository contains the Apple-main onboarding components: a version-pinned
W8 recipe, preset, metadata, documentation, tests, conversion-matrix coverage,
and a resource-free companion. It also records static `h16p` execution on an
iPhone 15 Pro and Neural Engine participation in one trace.

The historical A17 Pro run documents the static path from export through
generation and unload, including ANE participation in one trace. This result is
specific to that artifact and environment; no broader compatibility, speed, or
energy conclusion is drawn.

Conversion fidelity was evaluated separately from prompt-level generation
checks. Multiple W4 and mixed W4/W8 candidates were rejected before export. A
formal evaluation of the frozen recipe then completed six tuning and four
holdout comparisons. The holdout reached `0.996897` mean logits cosine,
`0.953391` minimum cosine, `96.97%` top-1 agreement, and `0.008880` mean
candidate-minus-reference NLL delta. These measurements apply to the
fake-palettized PyTorch authoring model under the frozen inputs; they are not
compiled-device logits or a claim of superior downstream benchmark quality.

See `RELATED_WORK.md` for the dated, scope-aware comparison.

## Frozen mechanism

| Component | Frozen value |
| --- | --- |
| Source model | `Qwen/Qwen3-1.7B` |
| Source revision | `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e` |
| Projection weights | W8 per-tensor K-means palettization |
| Tied embedding | INT8 per-tensor quantization |
| Compute | FP16 |
| KV cache | FP16, fixed size, 448 MiB at 4K |
| Maximum context | 4,096 tokens |
| iOS specialization | `h16p` |
| Preferred compute | Neural Engine |
| Minimum tested OS | iOS 27 |

The `null` embedding entries in the YAML exclude embeddings from the later
K-means palettization pass. They do **not** disable the earlier iOS INT8
embedding quantization.

## Evidence summary

### Corrected formal fidelity evidence

| Evaluation | Mean cosine | Min cosine | Top-1 agreement | Mean NLL delta |
| --- | ---: | ---: | ---: | ---: |
| W8 tuning set (6 cases) | 0.997300 | 0.963419 | 98.96% | 0.004190 |
| W8 holdout (4 cases) | 0.996897 | 0.953391 | 96.97% | 0.008880 |

The older `results/quality-summary.json` is retained as historical evidence of
the W4 and mixed-W4/W8 selection sequence. Its W8 values are superseded by
`results/fidelity-v2-summary.json`.

### Standalone iPhone suite (A-W8-HISTORICAL)

- four complete six-case suites;
- zero empty responses, truncations, degenerate loops, context overflows,
  crashes, OOMs, or assertion failures;
- 3,790-token long-context case retrieved the frozen tail marker;
- final peak resident memory: 2,963.7 MiB;
- subsequent load: 11.312 seconds;
- unload returned the process to 198.7 MiB.

### Historical product-runtime confirmation (A-W8-HISTORICAL)

`A-W8-HISTORICAL` also completed a non-public product-runtime acceptance suite
covering a single-engine service, asset delivery, cancellation, unload/reload,
offline cold start, background recovery, memory-pressure cancellation, and
delete/reconcile flows. Because that runtime is not distributed, this serves as
supporting integration evidence rather than an independently reproducible
result.

See `RESULTS.md` and the machine-readable files under `results/`.

### Current published speed run (A-W8-CURRENT)

Run J (`speed-v2-20260831-j`) used Hub revision
`75bbe06906cb5d953e602e3e4fb6364187c81822` and compiled main
`09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`.
Across both compared profiles it completed 120 generation measurements—20 per
profile and workload—with no failed admitted sample. These measurements support
the current storage, process-RSS, TTFT, total-time, and visible-decode results;
they do not establish exclusive Neural Engine execution or energy use.

### Supplementary load compatibility (A-W8-JULY-PUBLIC vs A-W8-CURRENT)

See `RESULTS.md` and `results/w8-aot-compatibility-evidence.json` for the
earlier load-only outcomes and their limits. No generation, trace, cold-start,
or comparative-performance measurement was performed within that diagnostic;
the later Run J generation evidence is separate.

## Claim boundaries

This project claims:

- the disclosed route exported and AOT-compiled Qwen3-1.7B, and its historical
  artifact ran through a real `LanguageModelSession` on iPhone;
- the frozen W8 recipe passed the disclosed quality and device gates;
- the reference onboarding applies to the stated Apple main revision.

This project does not claim:

- a Core AI RMSNorm or compiler bug;
- that W8 is a 4-bit recipe;
- exclusive execution on the Neural Engine;
- complete WikiText-2 perplexity evaluation;
- production support for every iPhone or architecture;
- adoption or endorsement by Apple;
- that the current compatibility difference was caused by an iOS upgrade,
  compiler defect, model-export change, or system-wide memory shortage;
- ANE participation for `A-W8-CURRENT` without a separately admitted trace;
- path-independent byte reproducibility from the two exports that used
  different output directories.

## Repository map

- `MODEL_REQUEST.md` — exact Apple Model Request fields.
- `REPRODUCTION.md` — source, patch, export, AOT, and companion instructions.
- `RESULTS.md` — human-readable evidence and limits.
- `DECISIONS.md` — hypotheses superseded during implementation.
- `RELATED_WORK.md` — comparison with adjacent public Core AI artifacts.
- `patches/` — reference patch against the version-pinned Apple main revision.
- `recipes/` — frozen W8 recipe.
- `results/` — sanitized machine-readable evidence.
- `companion/` — unsigned, resource-free iOS validation app.
- `licenses/` — third-party notices and Apple BSD license text.
- `paper/` — technical report source, evidence pipeline, generated tables and
  figures, claim audit, and compiled PDF.

## Technical report

The complete technical report and its reproducibility materials are available
under [`paper/`](paper/). The compiled report is
[`paper/manuscript/output/pdf/qwen3-coreai-report.pdf`](paper/manuscript/output/pdf/qwen3-coreai-report.pdf).

## License

Original material in this repository is available under BSD 3-Clause.
Apple-derived source context in the reference patch remains subject to Apple's
BSD 3-Clause license. Qwen3-1.7B weights are not redistributed.
