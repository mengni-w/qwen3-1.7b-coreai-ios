# Experiment Protocol V1: Prospective W8 Fidelity and ANE Confirmation

Status: **frozen before evaluator implementation and new measurement**  
Scope: the public Static-W8 authoring recipe and a trace of the exact public
Static-W8 artifact  
Out of scope: speed, energy, downstream task quality, and causal comparison
with the Dynamic-INT4 profile

This document prospectively specifies two confirmation studies prompted by a
review of the earlier evidence. The first recomputes conversion fidelity for
the currently published W8-plus-INT8 authoring path. The second records a new
Core AI trace whose inference window and event matching can be independently
audited. Results will be reported as observed; neither study may be redesigned
after its outputs are inspected.

This protocol is a new-data addendum to `REPORT_PROTOCOL_V1.md`. It does not
alter the retrospective boundary of that document. Its commit must precede
the prompt-manifest commit, evaluator implementation, model outputs, trace,
and analysis. The prompt manifest described below must itself be committed
before the evaluator or any result data.

## 1. Frozen identities

### 1.1 Reference and W8 authoring candidate

Both models begin with the unquantized `Qwen/Qwen3-1.7B` checkpoint at Hugging
Face revision:

```text
70d244cc86ccca08cf5af4e1e306ecf908b1ad5e
```

The reference is that checkpoint evaluated in FP16 without weight
compression. The candidate is the in-memory authoring model produced by the
public iOS recipe on Apple `coreai-models` commit:

```text
04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a
```

The repository inputs are:

| Input | SHA-256 |
| --- | --- |
| `patches/qwen3-1.7b-coreai-main.patch` | `bc8f135d5637d629beac727e4d10b0b6e909ebcc77206c39c971d8967d4360d4` |
| `recipes/qwen3_1_7b_w8_per_tensor.yaml` | `dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72` |

The candidate applies eight-bit, per-tensor K-means palettization to the 196
transformer projection weights. Embedding modules are excluded from that
K-means pass. The tied embedding table is instead quantized separately with
the iOS per-tensor INT8 path. Compute remains FP16. The evaluator must execute
the repository recipe and authoring implementation; a separately written
numerical approximation is not an interchangeable candidate.

This study evaluates the authoring model before Core ML conversion and AOT
compilation. It does **not** measure logits from the compiled `.aimodel` or
prove numerical equivalence of the downloadable `h16p` artifact. The result
may support fidelity of the disclosed public authoring recipe only.

### 1.2 Trace target

The trace study targets the W8 artifact pinned to Hugging Face revision:

```text
massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p
466ebe2e5cec125fa113ea71503add41bba581a8
```

The complete downloaded file manifest, each payload SHA-256, and the SHA-256
of the sorted manifest must be recorded before installation. The instrumented
companion's source commit, project-file hash, source-file hashes, Release app
bundle hash, executable hash, code-signing identity summary, and installed
bundle identifier must also be recorded. A trace is inadmissible if these
identities are missing or if its installed artifact differs from the manifest.

## 2. Fidelity confirmation

### 2.1 Frozen cases and later prompt manifest

The recovered valid evaluation set contains exactly ten cases. Its split is:

**Tuning (six)**

1. `semantic_zh_01`
2. `semantic_zh_02`
3. `semantic_en_01`
4. `echo_zh_01`
5. `retrieval_zh_01`
6. `schema_zh_01`

**Holdout (four)**

1. `semantic_zh_holdout`
2. `echo_mixed_holdout`
3. `selection_holdout`
4. `injection_holdout`

`long_context_holdout` is excluded. The recovered generator described that
case but supplied no prompt, and the historical evaluator skipped it. It may
not be reconstructed, substituted, or counted in either split.

The exact recovered user-prompt text is not yet present in this protocol
commit. A separate pre-data commit must add a UTF-8 prompt manifest containing
the ten case IDs, split labels, complete prompt text, per-prompt SHA-256, and a
SHA-256 over its canonical serialization. That commit must precede evaluator
code and all inference. After that commit, no case, split, whitespace, Unicode
normalization, or prompt content may be changed in response to a result.

### 2.2 Conversation serialization and decoding

Every case uses this exact system message, including punctuation, spacing,
capitalization, and the final `/no_think` token sequence:

```text
你是 e1 的本地语义引擎。只完成用户要求的书签语义任务，严格遵守输出格式。不要输出推理过程。/no_think
```

The system and user messages are serialized once with the pinned upstream
tokenizer's Qwen chat template, `add_generation_prompt=true`, and
`enable_thinking=false`. Failure to apply the no-thinking template is a failed
case, not permission to fall back to another template. The serialized UTF-8
text and token IDs used by the two models must be byte-for-byte and
element-for-element identical.

The remaining controls are frozen as follows:

- seed: `0` for Python, NumPy, and the model framework;
- deterministic framework execution enabled, with nondeterministic operations
  treated as errors where the framework exposes that control;
- decoding: greedy (`do_sample=false`), with no temperature, top-p, or top-k
  sampling;
- maximum new tokens: `64`;
- maximum total context: `1,024` tokens;
- no input truncation; a case that cannot fit is reported as failed;
- termination: the first EOS token or the 64-token limit;
- no retry, replacement case, or selective rerun.

Both reference and candidate must run independently for every case, and both
completion lengths and token-ID hashes must be retained. For the numerical
comparison, the reference greedy completion defines the token sequence
`y_i = (y_i1, ..., y_iT_i)`. The exact same serialized prompt and preceding
reference tokens are teacher-forced through both models. Thus reference logits
`r_it` and candidate logits `q_it` at position `t` are conditioned on identical
token histories. Positions after reference EOS are not included.

### 2.3 Metrics

For case `i` and reference-completion position `t`, let `r_it` be the reference
logit vector, `q_it` the candidate logit vector, and `y_it` the reference
completion token. With `T_i` evaluated positions:

```text
C_i       = (1 / T_i) sum_t cosine(q_it, r_it)
C_i_min   = min_t cosine(q_it, r_it)
A_i       = (1 / T_i) sum_t 1[argmax(q_it) = argmax(r_it)]
NLL_i(q)  = -(1 / T_i) sum_t log softmax(q_it)[y_it]
NLL_i(r)  = -(1 / T_i) sum_t log softmax(r_it)[y_it]
Delta_i   = NLL_i(q) - NLL_i(r)
```

A positive `Delta_i` means the candidate assigns lower probability to the
reference completion and is worse under this definition; a negative value
means the opposite.

Aggregate metrics are case-level macros, not token-weighted summaries:

```text
mean cosine   = arithmetic mean_i(C_i)
minimum cosine = minimum_i(C_i_min)
top-1 agreement = arithmetic mean_i(A_i)
mean NLL delta  = arithmetic mean_i(Delta_i)
```

The four aggregates are computed separately for tuning and holdout. Full
precision values are retained in machine-readable output; manuscript rounding
is presentation only. No acceptance threshold is specified. Confidence
intervals, hypothesis tests, or a new quality gate may not be added after the
values are known and then presented as preregistered.

### 2.4 Required fidelity records

The run must publish or retain, at minimum:

- environment lock: operating system, hardware, Python, framework,
  `coremltools`, `coreai-opt`, tokenizer, dependency lock, source revisions,
  recipe hash, patch hash, and evaluator commit/hash;
- canonical prompt manifest and serialized-input manifest;
- one raw record for every one of the ten case-model runs, including failures;
- a per-case comparison record containing split, case ID, reference and
  candidate completion lengths, serialized-input SHA-256, input-token-ID
  SHA-256, both completion-token-ID SHA-256 values, `T_i`, `C_i`, `C_i_min`,
  `A_i`, `NLL_i(q)`, `NLL_i(r)`, `Delta_i`, and the literal direction
  `candidate_minus_reference`;
- the four tuning and four holdout aggregates defined above;
- stdout/stderr, peak-memory record, wall-clock run metadata, and SHA-256 for
  every raw and derived evidence file.

Token-ID arrays must use a documented canonical byte encoding before hashing;
the encoding is an unsigned 64-bit big-endian token count followed by each
token ID as an unsigned 32-bit big-endian integer. JSON number formatting is
not an acceptable implicit encoding. Metric computation casts both logit
vectors to IEEE-754 binary64, evaluates cosine as the unregularized dot product
divided by the two Euclidean norms, and evaluates log-softmax in binary64. A
zero norm or non-finite result fails the case. Logits need not be published,
but any retained logits must be tied to the case and position by hash. Failed
cases remain in the record and are not silently removed from a macro result.

### 2.5 Interpretation and replacement rule

This confirmation is not a downstream capability benchmark and is not an
ANE-versus-GPU comparison. Its purpose is to test whether the current public
W8 authoring recipe reproduces high logit-level fidelity relative to the
pinned FP16 reference under the recovered ten-case contract.

The confirmatory result replaces the manuscript's mismatched historical
fidelity values regardless of whether it is numerically stronger or weaker.
The earlier summary may remain in provenance only if explicitly labelled
historical and superseded. The tuning/holdout split, formulas, or candidate may
not be changed to preserve a preferred conclusion.

## 3. ANE trace confirmation

### 3.1 Run boundary and capture

The instrumented companion must create exactly one signpost interval around
one measured generation. The frozen signpost identity is:

```text
subsystem: io.massif.qwen3.coreai.trace-confirmation
category: inference
name: PUBLIC_W8_TRACE_CONFIRMATION_V1
```

The signpost begins immediately before the measured generation request and
ends only after its terminal completion or error. Model download, verification,
load, smoke test, session creation, and warm-up occur before the interval. The
run UUID is included in both signpost endpoints and all app-side records.

Capture uses a Release build on the stated iPhone 15 Pro and an Instruments
template that includes Core AI events and Points of Interest. The record must
include the device model and identifier class (not a personal device name),
OS version and build, Xcode/Instruments version and build, Core AI build,
thermal state, Low Power Mode state, wall-clock timestamps, app PID, run UUID,
request input-token count, emitted-token count, terminal state, trace start/end,
and exact capture/export commands. The app PID is taken from the captured
process, not inferred later from a process name.

The raw `.trace` bundle is retained with its SHA-256. If it cannot be publicly
released after privacy review, the reason is stated and its deterministic
exports, capture metadata, commands, and hashes are published instead.

### 3.2 Windowing and deterministic event join

The exported signpost table must contain one complete interval with the frozen
name, matching UUID, and captured app PID. Its beginning is `RUN_BEGIN` and its
end is `RUN_END`. Only Core AI intervals satisfying

```text
event_start >= RUN_BEGIN and event_end <= RUN_END
```

are eligible. Events from load, warm-up, another request, another PID, or
outside the owned signpost window are excluded before matching.

Export the MPSGraph Program and Apple Neural Engine Prediction tables without
discarding their original timestamp, duration, program label, channel, state,
process, PID, and any native correlation/program identifier. Convert start and
duration to integer nanoseconds using the exported units and define
`relative_start_ns = start_ns - RUN_BEGIN_ns`.

If both tables expose the same stable, non-null native correlation/program
identifier, the exact multiset join key is:

```text
(native_identifier, relative_start_ns, duration_ns)
```

Otherwise the preregistered fallback key is:

```text
(relative_start_ns, duration_ns)
```

No tolerance, fuzzy timestamp match, row-order pairing, or post-result key
change is allowed. Each side is represented as a multiset of keys; the match
count for a key is the minimum of its two multiplicities. Keys and retained
rows are sorted lexicographically only to make the exported result
deterministic. The output must contain every matched row, every unmatched
MPSGraph row, every unmatched ANE row, duplicate multiplicities, the selected
key mode, and counts derived from those rows. Equal total counts alone do not
constitute a match.

### 3.3 Permitted conclusion

There is no preregistered minimum interval count. If the owned inference window
contains at least one exact MPSGraph-to-Apple-Neural-Engine match under the
rule above, the trace may support only this conclusion:

> The Apple Neural Engine participated in the traced inference program.

The trace does not establish exclusive ANE execution, proportion of work on
ANE, absence of CPU/GPU work, a performance or energy advantage, or behavior
outside this artifact, app build, device, OS, and recorded run. If the exact
join yields no match, the confirmation is reported as such and the ANE
participation sentence is not made from this run.

## 4. Change control and publication order

The required order is:

1. commit this protocol alone;
2. commit the complete ten-prompt manifest and its hashes, still with no
   evaluator or output;
3. implement and review the fidelity evaluator and trace instrumentation;
4. record immutable environment and artifact/app identities;
5. run the reference and candidate fidelity evaluation;
6. capture the trace;
7. commit raw records, deterministic derivations, and a results note;
8. update the manuscript and evidence index from those committed records.

A protocol correction made before data collection must be a separately dated
amendment that states what changed and why. After any model output or trace is
viewed, this protocol is immutable; deviations are reported beside the result
rather than edited away.
