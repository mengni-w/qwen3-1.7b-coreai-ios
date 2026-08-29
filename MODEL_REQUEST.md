# Apple Model Request — Qwen3-1.7B for iOS

The sections below map one-to-one to Apple's current
`.github/ISSUE_TEMPLATE/model_request.yml`.

## Suggested issue title

Add Qwen3-1.7B support for iOS

## Source link

https://huggingface.co/Qwen/Qwen3-1.7B/tree/70d244cc86ccca08cf5af4e1e306ecf908b1ad5e

## Target platform

iOS

## Use case

Qwen3-1.7B fills the capability and memory gap between the existing
Qwen3-0.6B and Qwen3-4B iOS options. It is useful for private on-device
language tasks such as structured extraction, instruction following, short
conversation, and retrieval over user-provided context without sending that
content to a server.

## Preferred precision / compression

W8 per-tensor K-means-palettized transformer projections, separate INT8
per-tensor quantization for the tied embedding table, FP16 compute, and a
fixed-size FP16 KV cache with a 4,096-token maximum context.

## Additional context

We prepared and validated a standalone Qwen3-1.7B iOS onboarding:

- related community conversions exist, but they do not make this request a
  duplicate: one publishes a dynamic INT4 GPU bundle for `h18p` after its
  static ANE path failed to invoke, while another publishes a third-party INT8
  macOS-path asset with no recorded AOT target and numeric accuracy reported as
  not run; this request is for an Apple-main preset, recipe, metadata, tests,
  and a validated static `h16p` path rather than another hosted compiled model;
- the preset is explicitly experimental and requires `--experimental`;
- the reference patch adds model metadata, the frozen compression recipe,
  registry entry, documentation, focused tests, and the iOS conversion matrix
  entry;
- the patch applies cleanly to Apple `coreai-models` main commit
  `04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`;
- 28 focused unit tests and Ruff pass on that revision, and 42 related iOS
  conversion tests collect successfully;
- clean export and `h16p` AOT compilation completed with 34 functions;
- an iPhone 15 Pro running iOS 27 completed four full six-case suites,
  including a 3,790-token long-context case and a reasoning case;
- the corrected formal W8 holdout produced mean cosine 0.996897, minimum cosine
  0.953391, 96.97% top-1 agreement, and mean candidate-minus-reference NLL
  delta 0.008880 under the disclosed authoring-model fidelity protocol;
- multiple W4 and mixed W4/W8 candidates were rejected before export, so the
  published W8 mechanism is the result of a frozen quality gate rather than a
  successful single-prompt smoke test;
- Apple Neural Engine participation was observed in a Core AI Instruments
  trace; exclusive ANE execution is not claimed;
- the [public reproduction repository](https://github.com/massif-01/qwen3-1.7b-coreai-ios)
  contains no model weights, tokenizer, compiled model, signed app, device
  identifier, local path, private prompt, or product source.

Full WikiText-2 perplexity is not included in the current evidence and is not
represented as complete. The repository provides the recipe, reference patch,
reproduction procedure, sanitized evidence, and resource-free companion app.

Related public artifacts and the limits of cross-project comparison are
documented in
[`RELATED_WORK.md`](https://github.com/massif-01/qwen3-1.7b-coreai-ios/blob/main/RELATED_WORK.md).
