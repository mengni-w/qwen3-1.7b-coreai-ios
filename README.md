# Qwen3-1.7B on Apple Core AI for iOS

This repository documents a reproducible Qwen3-1.7B onboarding for Apple's
`coreai-models` iOS path.

> **Quality-first result:** the frozen W8 holdout retained `0.996598` mean
> logits cosine, `0.959625` minimum cosine, `98.37%` top-1 agreement, and
> `0.003167` mean NLL delta against the uncompressed reference. Multiple W4 and
> mixed W4/W8 candidates were rejected before this mechanism was frozen.

The tested configuration fills the practical gap between Apple's existing
Qwen3-0.6B and Qwen3-4B iOS presets:

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

## Download the ready-to-run model

The complete, directly downloadable Core AI model bundle is published on
Hugging Face:

**[massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p](https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p)**

```bash
hf download massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p \
  --local-dir Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p
```

The Hugging Face repository contains the compiled `h16p` artifact, tokenizer,
frozen recipe, checksums, machine-readable evidence, and integration example.
This GitHub repository remains the source for the reproducible onboarding
patch, tests, methodology, and Apple contribution material.

## Status

The model recipe, export path, AOT artifact, quality checks, and physical-device
runtime have been validated. The reference onboarding patch applies cleanly to
Apple `coreai-models` main at:

`04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`

Validation against that main revision completed with:

- 28 focused unit tests passed;
- 42 related iOS conversion tests collected;
- Ruff passed;
- the registered preset dry-run resolved to W8, FP16, 4,096 context, and
  embedding quantization enabled.

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
  still pending when audited.

This GitHub repository does not redistribute a compiled model; the verified
artifact is published separately on
[Hugging Face](https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p).
The GitHub project contributes the missing Apple-main onboarding surface: a
locked W8 recipe, preset, metadata, documentation, tests, conversion-matrix
coverage, and a resource-free companion. It additionally validates the static
`h16p` path on iPhone 15 Pro and records Apple Neural Engine participation.

That static Neural Engine result is the main technical distinction. A dynamic
GPU graph can retain flexible shapes and use GPU kernels; the static iOS path
must survive shape specialization, prompt/extend bucketing, mutable KV state,
`h16p` AOT compilation, device specialization, and the Foundation Models event
bridge. This project closes that full path on A17 Pro. It does not infer a
speed or energy win without a controlled cross-runtime measurement.

The fidelity evidence is also deliberately stricter than a prompt-only smoke
test. Multiple W4 and mixed W4/W8 candidates were rejected before export. The
frozen W8 recipe then passed an untouched holdout against the reference model
at `0.996598` mean logits cosine, `0.959625` minimum cosine, `98.37%` top-1
agreement, and `0.003167` mean NLL delta. These are conversion-fidelity
measurements, not a claim of superior downstream benchmark quality.

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

### Frozen quality evidence

| Evaluation | Mean cosine | Min cosine | Top-1 agreement | Mean NLL delta |
| --- | ---: | ---: | ---: | ---: |
| W8 tuning set | 0.997067 | 0.967261 | 98.44% | 0.002985 |
| W8 frozen holdout | 0.996598 | 0.959625 | 98.37% | 0.003167 |

### Standalone iPhone suite

- four complete six-case suites;
- zero empty responses, truncations, degenerate loops, context overflows,
  crashes, OOMs, or assertion failures;
- 3,790-token long-context case retrieved the frozen tail marker;
- final peak resident memory: 2,963.7 MiB;
- subsequent load: 11.312 seconds;
- unload returned the process to 198.7 MiB.

### Product-runtime confirmation

The same frozen artifact was subsequently exercised through a product-grade
single-engine service, asset delivery, cancellation, unload/reload, offline
cold start, background recovery, memory-pressure cancellation, and
delete/reconcile flows. Those integration results support deployability, but
the product implementation is outside this repository.

See `RESULTS.md` and the machine-readable files under `results/`.

## Claim boundaries

This project claims:

- Qwen3-1.7B can be exported, AOT-compiled, and run through a real
  `LanguageModelSession` on iPhone;
- the frozen W8 recipe passed the disclosed quality and device gates;
- the reference onboarding applies to the stated Apple main revision.

This project does not claim:

- a Core AI RMSNorm or compiler bug;
- that W8 is a 4-bit recipe;
- exclusive execution on the Neural Engine;
- complete WikiText-2 perplexity evaluation;
- production support for every iPhone or architecture;
- adoption or endorsement by Apple.

## Repository map

- `MODEL_REQUEST.md` — exact Apple Model Request fields.
- `REPRODUCTION.md` — source, patch, export, AOT, and companion instructions.
- `RESULTS.md` — human-readable evidence and limits.
- `DECISIONS.md` — hypotheses superseded during implementation.
- `RELATED_WORK.md` — comparison with adjacent public Core AI artifacts.
- `patches/` — reference patch against the locked Apple main revision.
- `recipes/` — frozen W8 recipe.
- `results/` — sanitized machine-readable evidence.
- `companion/` — unsigned, resource-free iOS validation app.
- `licenses/` — third-party notices and Apple BSD license text.

## License

Original material in this repository is available under BSD 3-Clause.
Apple-derived source context in the reference patch remains subject to Apple's
BSD 3-Clause license. Qwen3-1.7B weights are not redistributed.
