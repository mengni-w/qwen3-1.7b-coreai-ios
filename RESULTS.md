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
| W8 tuning | 0.997067 | 0.967261 | 98.44% | 0.002985 | pass |
| W8 frozen holdout | 0.996598 | 0.959625 | 98.37% | 0.003167 | pass |

These are frozen logits/NLL comparison gates. They are not a substitute for a
complete public benchmark suite. Full WikiText-2 perplexity was not completed
and is intentionally not presented as a pass.

## Standalone physical-device suite

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

## Product-runtime confirmation

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

## AOT and execution

- 34 AOT functions;
- static-shape, chunked execution;
- prompt/extend context buckets: 256, 512, 1,024, 2,048, 4,096;
- query token shapes: 8, 16, 64;
- 547 MPSGraph intervals matched 547 Apple Neural Engine Prediction intervals
  in a Core AI Instruments trace.

The supported conclusion is Neural Engine participation. Exclusive ANE
execution is not claimed.
