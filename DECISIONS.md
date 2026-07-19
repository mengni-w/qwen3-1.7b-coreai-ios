# Decision history and superseded hypotheses

This file records material changes discovered across the complete implementation
history. It prevents an early hypothesis from being presented as the final
technical conclusion.

## 1. Unsupported architecture → missing onboarding

Early discussion treated Qwen3-1.7B's absence from Apple's model list as possible
architectural incompatibility. Inspection and export showed that Qwen3-1.7B
uses the already supported Qwen3 architecture. The missing surface is the
catalog preset, metadata, recipe, tests, and published validation.

Final conclusion: this contribution is model onboarding, not a new Qwen3
runtime implementation.

## 2. 8K target → 4K product baseline

The initial target was 8K. On iPhone 15 Pro, FP16 KV would consume about
896 MiB at 8K before weights and runtime memory. The validated first release was
reduced to 4K, where fixed FP16 KV occupies 448 MiB.

Final conclusion: 4K is the frozen contribution mechanism. KV quantization and
8K are separate future experiments.

## 3. Generic W4 → W8 per-tensor

Several 4-bit and mixed W4/W8 candidates exported and ran, but failed the
quality contract. Representative rejected candidates ranged from mean cosine
0.856886 to 0.981232. W8 passed the frozen holdout at mean cosine 0.996598 and
98.37% top-1 agreement.

Final conclusion: W8 is the verified baseline. This repository does not market
it as a 4-bit recipe.

## 4. RMSNorm runtime-bug hypothesis → not supported

An early FP16 ablation implicated RMSNorm numerical behavior. Subsequent W8
export and device validation succeeded without an RMSNorm primitive change.
The complete evidence therefore does not support claiming a Core AI RMSNorm
runtime bug.

Final conclusion: no RMSNorm or compiler fix is part of this contribution.

## 5. “Embedding unquantized” → separate INT8 embedding

Early notes incorrectly interpreted the YAML `null` entries as disabling
embedding quantization. Structural inspection showed that iOS import performs
separate INT8 embedding quantization before the later K-means pass.

Final conclusion: W8 transformer projections plus a separate INT8 tied
embedding table.

## 6. Early stream hangs → integration lifecycle findings

An early standalone companion matrix recorded incomplete response streams. The
later product-runtime investigation identified independent integration
conditions: low-memory cancellation and overlapping access to a shared
engine/KV cursor during cancellation. A single-permit engine lifecycle and
atomic cancellation behavior closed those product gates.

Final conclusion: the old matrix is not evidence of Qwen3-1.7B numerical
instability or a Core AI model bug. It is not used as the current model verdict,
and no runtime bug report is bundled with this Model Request.

## 7. Model runtime completion ≠ product-value completion

The model artifact and local runtime/delivery foundation are complete. The
application's final bookmark-analysis prompt, schema, derived storage, and
user-facing value loop remain a separate product workstream.

Final conclusion: unfinished product semantics do not invalidate the model
onboarding evidence, and they are not included in this repository.
