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

Artifact labels are identity-specific: `A-W8-HISTORICAL` denotes compiled main
`0c2dfcfeaae195386f1e61c05e0cf2b4a1ce6ecda1c321803afc0019b1d886d7`;
`A-W8-JULY-PUBLIC` denotes Hub revision
`466ebe2e5cec125fa113ea71503add41bba581a8` and compiled main
`a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`;
`A-W8-CURRENT` denotes Hub revision
`75bbe06906cb5d953e602e3e4fb6364187c81822` and compiled main
`09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`.

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

## Supplementary load compatibility observation (A-W8-JULY-PUBLIC vs A-W8-CURRENT)

On iOS 27 build `24A5424a`, `A-W8-JULY-PUBLIC` failed during
`ANECCompileOffline` in both load-only attempts. The second followed a reboot
request whose completion was not independently verified.

`A-W8-CURRENT` completed one load in 41.932 seconds, reached 2,737.0 MiB peak
process RSS, unloaded, and exited normally. This diagnostic performed no
generation or trace, and a cold-cache state was not established. That boundary
applies only to this diagnostic: Run J subsequently performed generation with
the same `A-W8-CURRENT` compiled main. Because both the artifact bytes and
compiler producer changed between the July and current builds, these outcomes
do not identify whether the OS/runtime, compiler, export, or memory state
caused the failures. The machine-readable record is
`results/w8-aot-compatibility-evidence.json`.

## Current Run J generation and speed evidence (A-W8-CURRENT)

Run J (`speed-v2-20260831-j`) used the `A-W8-CURRENT` identity above and
completed 120 generation measurements across the W8 and INT4 profiles: 20
measurements per profile and workload, with no failed admitted sample.

| Workload | Profile | Median input / output | Token TTFT | Visible TTFT | Total | Visible decode | End-to-end visible |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Medium business | Static-W8 | 150 / 56 | 0.242 s | 0.242 s | 2.234 s | 27.542 tok/s | 25.066 tok/s |
| Medium business | Dynamic-INT4 | 150 / 22 | 1.643 s | 1.643 s | 2.099 s | 45.841 tok/s | 10.479 tok/s |
| Near-4K prefill | Static-W8 | 3,778 / 6 | 3.720 s | 3.720 s | 3.952 s | 21.394 tok/s | 1.518 tok/s |
| Near-4K prefill | Dynamic-INT4 | 3,778 / 6 | 13.393 s | 13.393 s | 13.522 s | 38.556 tok/s | 0.444 tok/s |
| Sustained decode | Static-W8 | 108 / 256 | 0.205 s | 0.205 s | 9.675 s | 26.931 tok/s | 26.459 tok/s |
| Sustained decode | Dynamic-INT4 | 108 / 256 | 0.390 s | 0.390 s | 6.454 s | 42.210 tok/s | 39.760 tok/s |

Compiled-model storage was 1,711.4 MiB for W8 and 924.6 MiB for INT4. Maximum
after-unload peak process RSS was 3,409.1 MiB for W8 and 1,978.0 MiB for INT4.
These are Run J artifact and process measurements, not universal device
requirements or evidence of exclusive Neural Engine execution.
