# Qwen3-1.7B on Apple Core AI for iOS

This repository documents a reproducible Qwen3-1.7B onboarding for Apple's
`coreai-models` iOS path.

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
- `patches/` — reference patch against the locked Apple main revision.
- `recipes/` — frozen W8 recipe.
- `results/` — sanitized machine-readable evidence.
- `companion/` — unsigned, resource-free iOS validation app.
- `licenses/` — third-party notices and Apple BSD license text.

## License

Original material in this repository is available under BSD 3-Clause.
Apple-derived source context in the reference patch remains subject to Apple's
BSD 3-Clause license. Qwen3-1.7B weights are not redistributed.
