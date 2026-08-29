# Fidelity confirmation evaluator

This directory implements Section 2 of `paper/EXPERIMENT_PROTOCOL_V1.md` as
revised prospectively by `paper/FIDELITY_V2_AMENDMENT_1.md`. It
is intentionally separate from the retrospective analysis pipeline. The
evaluator measures the currently disclosed authoring mechanism: Apple’s iOS
Qwen3 implementation with an INT8 tied embedding and the exact W8 K-means
recipe in this repository.

The evaluator does not load a compiled `.aimodel`, measure device behavior, or
approximate Apple’s compression numerically. It imports the pinned
`coreai-models` source and invokes `coreai-opt`'s `KMeansPalettizer` directly.

## Published attempts and current result

- `attempts/37756da4-cfc7-445a-ae6c-7241cfd77037` preserves the interrupted,
  all-zero-reference implementation failure. It is not a fidelity result.
- `attempts/c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24` is the corrected formal
  attempt. It completed 10/10 reference cases, 10/10 candidate cases, and
  10/10 comparisons successfully.
- `results/fidelity-v2-summary.json` is the machine-readable public summary
  derived only from the sealed corrected attempt.

The corrected holdout macro is mean cosine `0.9968972864500013`, minimum
cosine `0.9533912271441090`, top-1 agreement `0.9696691176470589`, and mean
NLL delta `0.008879966197800114` in the registered candidate-minus-reference
direction. These are conversion-fidelity measurements under frozen inputs,
not a downstream capability result.

## Execution boundary

The official run must occur only after this evaluator has been reviewed and
committed. The command checks the required Git history:

1. the experiment protocol is a standalone earlier commit;
2. the prompt manifest is a later standalone commit;
3. the evaluator is committed after both;
4. the prospective amendment precedes the corrected evaluator commit;
5. all protocol, amendment, prompt, evaluator, patch, recipe, and lock files match the
   committed versions.

The official output directory must be new or empty. A UUID identifies the
single attempt. A failed or interrupted attempt is retained as a failed run;
its cases may not be replaced or selectively repeated.

After preflight succeeds, the orchestrator atomically claims the UUID under
the repository's Git common directory. Reusing that UUID with another output
directory in the same checkout or linked worktree fails. The claim is copied
into the evidence directory. An independent clone cannot enforce shared local
state, so publication review must also reject duplicate claim records bearing
the same UUID.

## 1. Prepare the pinned Apple checkout

Use a fresh checkout. `git apply --index` leaves `HEAD` at the pinned Apple
commit and stages exactly the paper patch, including its two new files; the
evaluator compares the staged stable patch ID as well as the source and recipe
hashes.

```bash
git clone https://github.com/apple/coreai-models.git /path/to/coreai-models-fidelity-v2
git -C /path/to/coreai-models-fidelity-v2 checkout 04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a
git -C /path/to/coreai-models-fidelity-v2 apply --index \
  /path/to/qwen3-1.7b-coreai-ios/patches/qwen3-1.7b-coreai-main.patch
cd /path/to/coreai-models-fidelity-v2
uv sync --frozen --python 3.12
```

Do not commit the staged patch in the Apple checkout and do not add any other
tracked or staged changes. The frozen package versions are listed in
`environment.lock.json` and must match the Apple checkout’s `uv.lock`.
The evaluator also requires `sys.prefix` and the executing Python path to
belong to this checkout's `.venv`; matching package version strings from an
unrelated environment are insufficient. A full installed-distribution
snapshot is written alongside the checked top-level pins and upstream lock.

## 2. Download and lock the source checkpoint

This step requests the full 40-character Hugging Face revision and hashes
every downloaded payload. Put the lock outside the model directory so that it
does not become an extra model payload.

```bash
cd /path/to/coreai-models-fidelity-v2
uv run --frozen --python 3.12 python \
  /path/to/qwen3-1.7b-coreai-ios/paper/evidence/fidelity-v2/run_fidelity_v2.py \
  prepare-source \
  --model-dir /path/to/qwen3-1.7b-source-70d244cc \
  --source-lock /path/to/qwen3-1.7b-source-70d244cc.lock.json
```

The lock records the requested repository and revision, each relative file
name, byte size, SHA-256, and a canonical manifest SHA-256. The run rehashes
the directory and rejects missing, changed, or additional payload files.
Use a read-only source snapshot for the official run. In addition to initial
preflight, the worker rehashes the complete checkpoint immediately before and
after each of the two sequential model loads. Those phase records make a
background synchronization or accidental edit fail closed rather than allow
reference and candidate to consume different bytes.

After downloading, remove write permission from the model root, every payload,
and the lock file. Corrected preflight rejects any write bit on those paths.

## 3. Validate without inference

After the evaluator commit exists, run the complete preflight. It loads the
tokenizer and runs a two-layer synthetic `Conv2d` model through the exact Apple
recipe parser and `KMeansPalettizer.prepare` path. It does not construct or
execute either 1.7B model. The synthetic pass also proves that every spawned
worker starts with seed 0, deterministic Torch error mode, and the frozen
thread controls.

```bash
cd /path/to/coreai-models-fidelity-v2
uv run --frozen --python 3.12 python \
  /path/to/qwen3-1.7b-coreai-ios/paper/evidence/fidelity-v2/run_fidelity_v2.py \
  check \
  --coreai-repo /path/to/coreai-models-fidelity-v2 \
  --model-dir /path/to/qwen3-1.7b-source-70d244cc \
  --source-lock /path/to/qwen3-1.7b-source-70d244cc.lock.json
```

Preflight rejects a tokenizer that ignores `enable_thinking=false`. For each
case, it requires the Qwen template’s explicit empty thinking block, verifies
that text templating and direct token templating produce identical token IDs,
and confirms that the full 64-token allowance fits within 1,024 tokens without
truncation.

## 4. Run the one-shot numerical health probe

The amendment requires one non-metric probe before a corrected formal UUID is
claimed. It compares the final logit vector for the first 16 frozen tokens of
`semantic_zh_01` between Apple’s iOS FP16 model and the pinned Hugging Face
FP16 eager-attention model. `USE_HF_IMPL=true` is set before model construction
and recorded. Both vectors must be nonzero and nonconstant, select the same
top-1 token, and have binary64 cosine at least `0.99`.

```bash
uv run --frozen --python 3.12 python \
  /path/to/qwen3-1.7b-coreai-ios/paper/evidence/fidelity-v2/run_fidelity_v2.py \
  health-probe \
  --probe-id 00000000-0000-4000-8000-000000000000 \
  --coreai-repo /path/to/coreai-models-fidelity-v2 \
  --model-dir /path/to/qwen3-1.7b-source-70d244cc \
  --source-lock /path/to/qwen3-1.7b-source-70d244cc.lock.json \
  --output-dir /path/to/fidelity-v2-health-probe
```

The probe UUID and output directory are single use. Every attempted probe is
retained; a failed probe cannot be replaced under the same amendment.

## 5. Execute the single official run

Freeze a UUID before starting. Do not reuse an output directory.

```bash
cd /path/to/coreai-models-fidelity-v2
uv run --frozen --python 3.12 python \
  /path/to/qwen3-1.7b-coreai-ios/paper/evidence/fidelity-v2/run_fidelity_v2.py \
  run \
  --run-id 00000000-0000-4000-8000-000000000000 \
  --coreai-repo /path/to/coreai-models-fidelity-v2 \
  --model-dir /path/to/qwen3-1.7b-source-70d244cc \
  --source-lock /path/to/qwen3-1.7b-source-70d244cc.lock.json \
  --health-probe-dir /path/to/fidelity-v2-health-probe \
  --output-dir /path/to/fidelity-v2-official-run
```

Replace the example UUID once, before execution. The orchestrator launches a
fresh child process with `PYTHONHASHSEED=0` and one-thread settings for the
common numerical runtimes, then captures its complete stdout and stderr. It
writes a manifest only after the child exits, including a failed or partially
completed child. A graceful terminal interruption is forwarded to the worker,
waited to quiescence, and still produces `process-result.json` and the evidence
manifest. An uncatchable `SIGKILL`, host failure, or power loss can leave only
partial files; the already-created UUID claim still prohibits treating a
replacement run as the same attempt.

The 32-worker K-means path uses Python's `spawn` start method, which does not
inherit process-global random or deterministic state. During each Apple
`prepare` call, the evaluator injects a narrowly scoped startup bootstrap via
`PYTHONPATH`. Each child independently applies the frozen Python, NumPy, and
Torch controls and writes a temporary state probe. The candidate is rejected
unless exactly 32 probes match the expected state.

## Model and metric implementation

The reference calls Apple’s `Qwen3ForCausalLMForiOS.from_hf` directly with its
public `disable_embedding_quantization=True` option; Apple’s state-dict
mutation, forward path, and FP16 compute remain in use. The candidate calls the
same Apple class with its default INT8 tied embedding. The candidate is then
passed to the pinned `KMeansPalettizer.prepare` implementation with the recipe
parsed by Apple’s own export CLI. This is the representation that
`coreai-opt` specifies for PyTorch numerical evaluation; `finalize(CoreAI)` is
reserved for constructing the export representation. Before compression, the
evaluator requires exactly 196 named Qwen3 projection `Conv2d` modules. After
preparation, it also requires palettization parametrizations on those 196
modules and no others.

For memory control, the models are never resident together:

1. run all ten independent reference completions;
2. teacher-force each reference history and retain its FP16 logits in a
   temporary directory;
3. unload the reference model;
4. load and palettize the candidate;
5. run all ten independent candidate completions and compare both models on
   the saved reference histories;
6. remove the temporary logits when the process leaves the isolated temporary
   directory.

Each comparison casts both logit matrices to NumPy `float64`. Cosine uses the
unregularized dot product divided by both Euclidean norms. NLL uses a binary64
max-shifted log-softmax. Zero norms, non-finite values, shape mismatches, and
out-of-range target tokens fail the case. Split summaries are unavailable if
any frozen case fails; there is no partial macro.

Reference and candidate generation both consume the same token array from the
serialized-input manifest. Reference teacher forcing consumes that prompt plus
its own greedy completion except the final target token. Candidate teacher
forcing consumes the same array, rather than its independently generated
completion. Both model-run records retain the teacher-forced input count and
canonical token-ID hash, and the comparison record verifies their equality.
Failed comparisons keep the protocol field names with unavailable numerical
values represented as JSON `null`; they are never removed from aggregation.

## Evidence files

The run directory contains:

- `environment.json`: hardware, OS, Python, exact dependencies, source model,
  Apple checkout, recipe, patch, evaluator, and Git-order identities;
- `environment.lock.json` and `coreai-models-uv.lock`: the evaluator pins and
  the exact upstream dependency lock whose hash was checked at preflight;
- `prompt-manifest.json`: the committed canonical ten-case prompt manifest;
- `serialized-inputs.json`: exact serialized text, token IDs, UTF-8 hashes, and
  canonical token-ID hashes for all ten cases;
- `model-runs.jsonl`: one reference and one candidate record per case,
  including failures;
- `case-comparisons.jsonl`: per-case hashes and protocol metrics;
- `aggregates.json`: tuning and holdout case-level macros;
- `ephemeral-logits.json`: hashes tying temporary reference-logit files to
  their cases and recording that they were not retained;
- `worker-run.json`, `process-result.json`, `stdout.log`, and `stderr.log`;
- `source-model-lock.json` and `source-model-revalidations.jsonl`;
- `run-id-claim.json` and `MANIFEST.sha256`.

`worker-run.json` reports Darwin `ru_maxrss` separately for the worker and
terminated direct children. `process-result.json` additionally samples the
worker and all observed descendants every 100 ms and reports the maximum sum
of their resident sets. The latter is a sampled process-tree peak, not an
instantaneous kernel accounting identity; both semantics are stated in the
machine-readable fields.

Token-ID hashes use the protocol encoding: an unsigned 64-bit big-endian count
followed by each ID as an unsigned 32-bit big-endian integer.

## Non-Qwen tests

The tests use synthetic logits, scripted Torch models, and the small two-layer
authoring smoke model. They never construct Qwen3-1.7B. They cover cosine and
NLL formulas, delta direction, case-level aggregation, failure behavior,
canonical token encoding, prompt-manifest validation, source-file lock
mutation, fail-closed no-thinking serialization, teacher-forcing boundaries,
cache offsets and causal masks, FP16 logit layout, preflight failure
cardinality, UUID reuse, and the exact Apple parser/KMeans spawn path.

```bash
cd /path/to/coreai-models-fidelity-v2
uv run --frozen --python 3.12 python -m unittest discover \
  -s /path/to/qwen3-1.7b-coreai-ios/paper/evidence/fidelity-v2/tests \
  -p 'test_*.py'
```

Running only with NumPy outside the frozen Apple environment skips the Torch
and authoring integration cases and is not the final pre-run test evidence.
