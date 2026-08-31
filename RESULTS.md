# Validation results

## Configuration

- Model: Qwen3-1.7B
- Transformer projections: W8 per-tensor K-means palettization
- Tied embedding: INT8 per-tensor quantization
- Compute: FP16
- KV cache: fixed-size FP16, 448 MiB
- Context: 4,096 tokens
- AOT architecture: `h16p`
- Device class: iPhone 15 Pro
- OS: iOS 27

## Quality

| Gate | Mean cosine | Min cosine | Top-1 agreement | Mean NLL delta | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| W8 tuning (6 cases) | 0.997300 | 0.963419 | 98.96% | 0.004190 | pass |
| W8 holdout (4 cases) | 0.996897 | 0.953391 | 96.97% | 0.008880 | pass |

Candidate selection used authoring-model fidelity metrics rather than
generation-only smoke tests. Uniform and mixed W4/W8 candidates were rejected;
representative mean-cosine values ranged from 0.856886 to 0.981232. All ten
frozen inputs were evaluated for both the reference and W8 models. The reported
metrics supersede the older W8 values in `results/quality-summary.json`.

These are authoring-model logits/NLL comparisons under frozen inputs, not
compiled-device logits or a downstream capability benchmark. Full WikiText-2
perplexity was not evaluated.

## Standalone physical-device suite (A-W8-HISTORICAL)

Four complete six-case suites passed. The final suite included:

| Case | Input tokens | Output / reasoning | TTFT | Visible decode | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| Structured JSON | 160 | 60 / 1 | 0.564 s | 17.611 tok/s | pass |
| Hot context turn | 241 | 5 / 1 | 0.428 s | 54.205 tok/s | pass |
| Hot rewrite turn | 275 | 5 / 1 | 0.472 s | 49.455 tok/s | pass |
| Injection boundary | 309 | 5 / 1 | 0.474 s | 54.596 tok/s | pass |
| Long context | 3,790 | 10 / 1 | 5.627 s | 15.828 tok/s | pass |
| Reasoning | 69 | 271 / 260 | 15.925 s | 21.370 tok/s | pass |

Final standalone measurements:

- load: 11.312 seconds after specialization cache warm-up;
- peak resident memory: 2,963.7 MiB;
- resident memory after unload: 198.7 MiB;
- minimum observed process-available memory: 837.9 MiB;
- hard failures across the four complete suites: zero.

## Historical product-runtime confirmation (A-W8-HISTORICAL)

The frozen artifact later completed a product-runtime acceptance suite using a
single shared engine and real `LanguageModelSession` calls:

- initial load: 11.513 seconds;
- short TTFT: 0.426 seconds;
- short visible decode: 16.376 tok/s;
- near-4K input: 3,194 tokens;
- near-4K TTFT: 5.138 seconds;
- near-4K visible decode: 13.087 tok/s;
- unload: 0.061 seconds;
- process RSS after five-second recovery: 268,173,312 bytes;
- highest observed thermal state in the accepted baseline: nominal.

Additional accepted paths included offline cold start with an already downloaded
asset, unload/reload, background lazy recovery, cancellation without transcript
commit, session isolation, memory-pressure cancellation, and delete/relaunch
reconciliation.

The product runtime is not distributed here. These results are supporting
evidence for the same frozen model artifact, not a claim that the companion
implements a production service.

## Historical AOT and trace evidence (A-W8-HISTORICAL)

- 34 AOT functions;
- static-shape, chunked execution;
- prompt/extend context buckets: 256, 512, 1,024, 2,048, 4,096;
- query token shapes: 8, 16, 64;
- 547 MPSGraph intervals matched 547 Apple Neural Engine Prediction intervals
  in a Core AI Instruments trace.

The supported conclusion is Neural Engine participation. Exclusive ANE
execution is not claimed.

## Supplementary load compatibility observation (A-W8-PUBLIC vs A-W8-CURRENT-CANDIDATE)

On iOS 27 build `24A5424a`, `A-W8-PUBLIC` failed during
`ANECCompileOffline` in both load-only attempts. The second followed a reboot
request whose completion was not independently verified.

`A-W8-CURRENT-CANDIDATE` completed one load in 41.932 seconds, reached 2,737.0
MiB peak process RSS, unloaded, and exited normally. No generation or trace was
performed, and a cold-cache state was not established. Because both the
artifact bytes and compiler producer changed, these outcomes do not identify
whether the OS/runtime, compiler, export, or memory state caused the failures.
The machine-readable record is `results/w8-aot-compatibility-evidence.json`.
