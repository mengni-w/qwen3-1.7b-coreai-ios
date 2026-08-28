# Fidelity V2 Amendment 1: Numerical Parity Preflight

Status: **prospective for any corrected fidelity run**

Preceding failed attempt: `37756da4-cfc7-445a-ae6c-7241cfd77037`

Scope: execution controls and failure evidence for Section 2 of
`EXPERIMENT_PROTOCOL_V1.md`

This amendment was written after the first formal evaluator process failed and
before any corrected evaluator or corrected model output was produced. The
failed attempt remains public under
`paper/evidence/fidelity-v2/attempts/37756da4-cfc7-445a-ae6c-7241cfd77037`.
It is not a fidelity result.

## 1. Reason for the amendment

The first three FP16 reference cases in the failed attempt each produced 64
token IDs equal to zero. Their teacher-forced logit files also had one common
SHA-256. Inspection during the run showed all-zero FP16 arrays of shape
`(64, 151936)`. The orchestrator was interrupted during the fourth reference
case and preserved the attempt as a failed process.

The postmortem diagnosis is consistent with an unfrozen control in the pinned
Apple iOS `RMSNorm` implementation. The class chooses its numerical path when
the module is constructed. By default, it squares the input in the input
dtype. When `USE_HF_IMPL=true`, it first promotes the input to FP32, matching
the path used by Apple's iOS primitive and model-comparison tests. The failed
evaluator neither fixed nor recorded this environment variable. In FP16, a
sufficiently large activation can overflow during squaring and normalize to
exact zero while remaining finite. A synthetic input `[300, -300]` reproduced
that mechanism. No layer-level activation trace was retained from the failed
1.7B process, so the evidence does not prove that this was its only cause.

The failed run also exposed two procedural gaps. The checkpoint snapshot was
owner-writable even though the run instructions required a read-only source,
and an interrupted worker did not emit the full failure matrix described in
Section 2.4. These facts are retained in the failed-attempt supplement.

## 2. Unchanged registered inputs and estimands

The following V1 choices remain unchanged:

- source checkpoint and revision;
- Apple `coreai-models` commit, paper patch, and W8 recipe;
- source weights and W8-plus-INT8 compression definitions;
- ten cases, prompts, tuning/holdout split, and serialization;
- greedy decoding, 64-token limit, 1,024-token context, and no truncation;
- shared-reference-history teacher forcing;
- metric formulas, binary64 metric computation, aggregation, and direction;
- prohibition on selective case replacement or metric-driven reruns.

The corrected candidate still applies the same W8 K-means recipe to the same
196 projection weights and the same Apple INT8 tied-embedding path. This
amendment changes no weight, token, case, or registered metric. It does revise
the numerical execution control used by both authoring models after the failed
process. A successful corrected result therefore answers this amended
protocol; it must not be described as an untouched execution of V1.

## 3. Frozen numerical parity control

Every corrected evaluator process, formal worker, and palettization child must
run with:

```text
USE_HF_IMPL=true
```

The evaluator must set this value before constructing any Apple model and
must reject an inherited value other than `true`. The value is recorded in
the environment evidence and in each spawned-child determinism probe.

For CPU evaluation, the flag selects the FP32-accumulating RMSNorm parity path
and Apple's Hugging Face parity construction for the RoPE cache. The CUDA-only
HF SDPA branch is not selected on the registered CPU device. Both reference
and candidate use the same setting. The setting governs numerical evaluation
of Apple's PyTorch authoring model; it neither changes the disclosed W8
artifact nor turns this study into a compiled Core AI logit measurement.

Every normalized logit matrix must satisfy all of the following before a
completion token or metric is accepted:

- the registered FP16 dtype and layout;
- all entries finite;
- a strictly positive FP32 Euclidean norm for every row;
- strictly positive within-row dynamic range.

Failure of any condition fails the case immediately. A finite-value test alone
is insufficient.

## 4. Pre-UUID health probe

Before a corrected formal UUID may be claimed, the corrected evaluator must
run one non-metric health probe against the pinned checkpoint. The probe uses
the first 16 token IDs of the already frozen `semantic_zh_01` serialized input.
It performs no completion, loads no candidate, and computes no registered
fidelity aggregate.

The probe loads the models sequentially:

1. Apple `Qwen3ForCausalLMForiOS`, FP16, embedding quantization disabled,
   `USE_HF_IMPL=true`;
2. the pinned Hugging Face Qwen3 reference in FP16 with eager attention.

For the final prefix position, both logit vectors must be finite, have
positive FP32 norm and dynamic range, and select the same greedy token. Their
binary64 cosine must be at least `0.99`. This is an author-selected diagnostic
floor, not an Apple threshold or a registered fidelity result. The probe
records both models' before/after source revalidations, input-token hash,
vector summaries, top-1 token IDs, cosine, environment identity, and evaluator
identity. It retains no full logit vector.

Every probe receives a UUID, new output directory, process record, and evidence
manifest. Successful and failed probe attempts are retained and published in
chronological order. The `0.99` floor and same-top-1 rule may not be changed in
response to probe output. A failed probe may be repeated only after another
prospective amendment and corrected evaluator commit, not by changing UUIDs
under the same implementation.

The formal command must verify and copy a successful probe produced by the
same evaluator commit, source lock, Apple checkout, environment lock, and
serialized-input manifest. A missing, failed, altered, or mismatched probe is
a preflight failure and cannot claim a formal UUID.

Synthetic regression tests must separately prove that the Apple default FP16
RMSNorm path can yield finite zeros for `[300, -300]`, while the frozen parity
path yields finite nonzero output. These small tests are implementation checks,
not model results.

## 5. Source immutability and failure records

Before either the health probe or a formal run, the evaluator must reject:

- a source-lock file with any write bit set;
- a source-model root directory with any write bit set;
- any locked source payload with any write bit set.

The observed permission modes are recorded. Byte-level source validation and
the before/after load revalidations remain mandatory.

After the outer preflight succeeds and before worker launch, the orchestrator
must place the fixed environment, locks, prompt manifest, and serialized-input
manifest in the new output directory. A worker-preflight failure, launch
failure, catchable interruption, or model failure must still produce one
model-run record for every case and role, ten comparison records, unavailable
aggregates, process metadata, and an evidence manifest. Fields that were never
computed remain `null` or explicitly `not_started`; they are not fabricated.

## 6. Corrected-attempt boundary

The failed UUID is never reused, deleted, or relabelled. A corrected run uses a
new UUID and output directory. It may begin only after this amendment and the
corrected evaluator are separate commits, all non-model tests pass, the health
probe passes, and an independent readiness review finds no blocking issue.

All formal attempts are published in chronological order. The corrected run,
if successful, answers the amended confirmation question. The first failed
process remains an implementation-failure record and is excluded from metric
aggregation because it produced no valid reference comparison.
