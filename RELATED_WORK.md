# Related public work

Audit date: 2026-07-19

Qwen3-1.7B can now be found in several Apple-Silicon and Core AI projects. This
file explains why this repository is complementary rather than duplicative.
The comparison uses only claims disclosed by each project's own model card or
repository at the audit date.

## Direct Core AI comparisons

| Dimension | `mlboydaisuke/qwen3-1.7b-CoreAI-official` | `kevinqz/Qwen3-1.7B-CoreAI` | This repository |
| --- | --- | --- | --- |
| Primary goal | Distribute a ready-to-run compiled model | Distribute a catalogued converted model | Add a reproducible Qwen3-1.7B onboarding to Apple's official authoring repository |
| Published artifact | `h18p` `.aimodelc` with tokenizer | INT8 `.aimodel` with tokenizer | Apple-main patch, recipe, tests, evidence, and resource-free companion; no weights or compiled model |
| Execution path | Dynamic INT4 GPU (`coreai-pipelined`) | Stateful KV-cache Core AI asset produced by `coreai-fabric`; reproduction manifest uses `--platform macOS` and records no AOT target | Static-shape, W8 per-tensor projections, separate INT8 embedding, FP16 compute/KV, `h16p`, Neural Engine preferred |
| Context shape | Dynamic GPU graph; model card reports 40,960 maximum context | Model metadata reports 40,960 maximum context; no iPhone AOT target disclosed | Fixed 4,096-token FP16 KV; 34 AOT functions across prompt, extend, context, and query buckets |
| Disclosed device evidence | iPhone 17 Pro; GPU path | Model card says real-hardware load/generation passed; no iPhone throughput published and the reproduction manifest is macOS-path | iPhone 15 Pro; four complete six-case suites plus product-runtime acceptance |
| Disclosed quality evidence | Eight checkable questions, 8/8 | Numeric accuracy `not_run` | Corrected formal authoring-model fidelity on six tuning and four holdout inputs; holdout mean cosine 0.996897, min cosine 0.953391, top-1 96.97%, NLL delta 0.008880 |
| Static ANE result | Model card says the static ANE bundle loaded but did not invoke, so it was omitted | No static `h16p` ANE result disclosed | Static `h16p` artifact invoked on A17 Pro; Core AI trace showed Neural Engine participation |
| Apple-main integration | No Apple-main onboarding patch disclosed | No Apple-main onboarding patch disclosed | Patch adds preset, metadata, recipe, docs, focused tests, and iOS conversion-matrix coverage against locked Apple main |
| Strongest disclosed advantage | Small dynamic INT4 bundle and high reported GPU throughput on iPhone 17 Pro | Reusable catalog/install workflow and downloadable INT8 asset | Highest disclosed conversion-fidelity evidence, A17 Pro static-path validation, and upstream-ready Apple-main integration |

Sources:

- [`mlboydaisuke/qwen3-1.7b-CoreAI-official`](https://huggingface.co/mlboydaisuke/qwen3-1.7b-CoreAI-official)
- [`kevinqz/Qwen3-1.7B-CoreAI`](https://huggingface.co/kevinqz/Qwen3-1.7B-CoreAI)
- [`kevinqz` parity report](https://huggingface.co/kevinqz/Qwen3-1.7B-CoreAI/blob/main/int8/parity-report.json)
- [`kevinqz` reproduction manifest](https://huggingface.co/kevinqz/Qwen3-1.7B-CoreAI/blob/main/int8/reproduce-manifest.json)

Despite the first repository's name, it is a community Hugging Face repository,
not an Apple-published model. Neither project is represented here as deficient:
they optimize for downloadable artifacts and, in the first case, GPU speed.
This project optimizes for upstream reproducibility, high conversion fidelity,
and a validated static iPhone path.

## Why the static Neural Engine path matters

The first public Core AI comparison explicitly falls back to a dynamic GPU
bundle because its static ANE bundle loaded but did not invoke. The second
publishes a macOS-path `.aimodel` without a recorded AOT target or public ANE
trace. By contrast, this project validates the `h16p` static artifact on A17 Pro
and records Neural Engine participation through Core AI Instruments.

This is a materially more constrained deployment path, not just a different
compute-unit flag. It requires:

- static prompt and extend shapes;
- context and query-size entry-point buckets;
- mutable FP16 KV state across chunks;
- device-specific `h16p` AOT compilation and on-device specialization;
- a real `CoreAILanguageModel` and `LanguageModelSession` stream;
- cancellation, unload/reload, long-context, and memory-pressure behavior.

Completing that chain is the main technical advantage of this contribution.
It does not, by itself, prove that ANE is faster or more energy efficient than
the published GPU path: those claims require a controlled test using the same
device, precision, context, prompt, and measurement method.

## Why the quality evidence matters

The final W8 recipe was not selected because it merely produced readable text.
The investigation froze real product-shaped prompts, generated an uncompressed
reference, and compared quantized logits and NLL under the same inputs.

Rejected candidates included uniform and mixed W4/W8 recipes. Representative
candidate mean cosine values ranged from 0.856886 to 0.981232 and did not pass
the quality contract. Only after those failures was the W8 mechanism frozen.
It then produced:

| Evaluation | Mean cosine | Min cosine | Top-1 agreement | Mean NLL delta |
| --- | ---: | ---: | ---: | ---: |
| W8 tuning set (6 cases) | 0.997300 | 0.963419 | 98.96% | 0.004190 |
| W8 holdout (4 cases) | 0.996897 | 0.953391 | 96.97% | 0.008880 |

This is evidence of fidelity to the uncompressed authoring-model reference
under the disclosed test contract. It is not a compiled-device-logit result or
a downstream capability leaderboard, and it should not be directly compared
with another project's prompt score or throughput because the hardware,
execution path, precision, context shape, and evaluation sets differ.

## Adjacent but not direct comparisons

[`basecompute/Qwen3-1.7B`](https://huggingface.co/basecompute/Qwen3-1.7B)
publishes Q4 and Q8 BaseRT artifacts for a Metal-native runtime. It is relevant
to the broader Apple-Silicon ecosystem, but it is not a Core AI conversion and
does not address Apple `coreai-models` onboarding.

## Claim boundary

The contribution is not the first public Qwen3-1.7B artifact for Apple Silicon,
nor the first public Qwen3-1.7B Core AI conversion. Its distinct claim is:

> A high-fidelity, reproducible Qwen3-1.7B W8 onboarding for Apple Core AI's
> official iOS authoring path, validated through static `h16p` AOT and a real
> `LanguageModelSession` on iPhone 15 Pro.
