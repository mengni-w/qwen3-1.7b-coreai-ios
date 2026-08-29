# Qwen3-1.7B on iPhone with Apple Core AI

## Technical Report Protocol v1

**Status:** Frozen before manuscript drafting; amended after review to admit the
separately governed fidelity-v2 confirmation
**Protocol version:** 1.0
**Date:** 2026-08-28
**Study type:** Retrospective systems technical report based on completed,
publicly documented experiments

## 1. Purpose

This protocol defines how the existing Qwen3-1.7B Core AI work will be turned
into a technical report. It does not define a new device experiment.

The report will document a reproducible static iOS deployment path for
Qwen3-1.7B on iPhone and compare it with a separately validated dynamic GPU
deployment profile. It will use the already published artifacts, source,
per-example predictions, statistical results, device measurements, traces,
and Apple upstream record.

No new empirical result was required when Protocol v1 was frozen. Existing raw
evidence could be rechecked or reanalyzed without changing the original
measurements. Manuscript review later identified a fidelity-evidence gap. The
resulting confirmation was authorized prospectively by
`EXPERIMENT_PROTOCOL_V1.md` and `FIDELITY_V2_AMENDMENT_1.md`; Section 12 records
its admission without changing the device, CMRC, speed, or trace datasets.

## 2. Central report claim

The report's central claim is:

> A high-fidelity Qwen3-1.7B model was reproducibly onboarded to Apple Core
> AI's static iOS authoring path, AOT-compiled for `h16p`, and validated through
> a real `LanguageModelSession` on iPhone 15 Pro with measured Apple Neural
> Engine participation. A second public INT4 dynamic-KV GPU profile demonstrates
> that deployment trade-offs are workload-dependent rather than universally
> favoring one profile.

This is a systems and deployment contribution. It is not a new model
architecture, training method, or quantization algorithm.

## 3. Contributions supported by existing evidence

### C1 — Missing official support surface

At the dated repository snapshot, Apple's public Qwen3 support matrix does not
include Qwen3-1.7B. Apple PR #196 attempted Qwen3-1.7B macOS and iOS support,
reported an iOS regression, and closed without merge. Issue #116 remains the
public model request.

Supported wording:

- Apple had no registered Qwen3-1.7B preset in the audited main revision.
- Apple's public iOS mixed-precision attempt was not merged after a reported
  local regression.

Unsupported wording:

- Apple proved Qwen3-1.7B impossible on iOS.
- No third party had ever converted Qwen3-1.7B.
- Apple adopted or endorsed this work.

### C2 — Reproducible static iOS onboarding

The W8 contribution includes a locked recipe, Apple-main onboarding patch,
metadata, tests, dry-run resolution, export and AOT instructions, a resource-
free companion application, integrity hashes, and physical-device validation.

### C3 — High-fidelity W8 selection

The W8 mechanism was selected using frozen logits and NLL comparisons rather
than prompt smoke alone. Uniform W4 and mixed W4/W8 candidates were rejected.
The earlier `results/quality-summary.json` remains evidence of that selection
sequence, but its W8 tuning and holdout numbers are superseded.

The corrected formal fidelity-v2 run evaluated the fixed W8 mechanism with six
tuning and four holdout inputs. The holdout reported:

- mean logits cosine: `0.9968972864500013`;
- minimum logits cosine: `0.953391227144109`;
- top-1 agreement: `0.9696691176470589`;
- mean candidate-minus-reference NLL delta: `0.008879966197800114`.

These values support conversion fidelity of the fake-palettized PyTorch
authoring model under the disclosed holdout. They do not measure compiled-device
logits or establish general downstream superiority.

### C4 — Physical iPhone static-path validation

The W8 artifact completed four full six-case suites on iPhone 15 Pro / iOS 27,
including structured output, multi-turn state, prompt-injection boundary,
near-4K context, reasoning output, unload, and reload. The final standalone
suite reported zero hard failures, `2,963.7 MiB` peak process RSS, and
`198.7 MiB` RSS after unload.

A Core AI trace recorded `547` MPSGraph program intervals matched by `547`
Apple Neural Engine Prediction intervals. This supports ANE participation, not
exclusive ANE execution.

### C5 — Paired W8/ANE and INT4/GPU comparison

The completed comparison used the same base model revision, tokenizer,
physical iPhone 15 Pro, iOS 27, frozen CMRC2018 sample, and controlled speed
workloads.

Existing paired quality result, 300 examples:

| Metric | W8 / static KV / ANE | INT4 / dynamic KV / GPU |
| --- | ---: | ---: |
| Exact Match | 59.33 | 57.67 |
| F1 | 81.70 | 81.42 |
| Byte-identical predictions | — | 187 / 300 |

Existing uncertainty result:

- W8-minus-INT4 F1: `+0.28`, 95% bootstrap interval `[-2.44, +3.00]`,
  paired sign-test `p = 0.614`;
- W8-minus-INT4 EM: `+1.67`, 95% bootstrap interval `[-3.00, +6.33]`,
  paired test `p = 0.576`.

Supported conclusion: the 300-example experiment did not establish a
statistically detectable difference. It also did not establish equivalence.

Existing size, memory, and workload measurements:

| Measurement | W8 / ANE | INT4 / GPU |
| --- | ---: | ---: |
| Compiled bundle | 1,714.4 MiB | 924.6 MiB |
| Peak process RSS | 2,865.0 MiB | 1,995.3 MiB |
| 161 input / 60 output, total | 3.259 s | 2.592 s |
| 161 input / 60 output, TTFT | 0.431 s | 1.221 s |
| 3,790 input / 10 output, total | 6.116 s | 13.717 s |
| 120 input / 256 output, total | 13.292 s | 7.159 s |
| 120 input / 256 output, visible decode | 19.615 tok/s | 38.487 tok/s |

Supported conclusion: INT4/GPU reduced bundle size and peak RSS and delivered
higher sustained decode throughput, while W8/ANE delivered lower TTFT and much
faster near-4K prefill. Neither profile was the universal winner.

## 4. Frozen artifact identities

Both profiles derive from:

- base model: `Qwen/Qwen3-1.7B`;
- base revision: `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`;
- tokenizer SHA-256:
  `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`.

### Public W8/ANE 4K artifact

- Hub repository: `massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p`
- Hub revision: `466ebe2e5cec125fa113ea71503add41bba581a8`
- compiled `main-h16p.mlirb` SHA-256:
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`
- recipe SHA-256:
  `dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72`

Post-freeze documentation amendment: Hub revision
`be6b5aad19e18bb71be3199eadceb27db7e69724` removes a local device nickname
from the model card. The empirical freeze remains the revision above; the
model payload and admitted validation object are unchanged.

### Public INT4/GPU 4K artifact

- Hub repository: `massif/Qwen3-1.7B-CoreAI-GPU-INT4-4K-h16p`
- Hub revision: `c32b6342c98e5e23363f692e614bccca37f24234`
- compiled `main-h16p.mlirb` SHA-256:
  `ad953b6bc902accc1f1200a8870012c5dec6b488f0f4ec0f10a9916b16cb56ef`
- `resources.bin` SHA-256:
  `37c7f2fcf85625abb32d83ca24e7a9facd33a37f79dbc3afec64d41eb900f8bc`

The comparison repository originally recorded Hub revision
`cb25b3226ee679ee92d0e5af7467d579a6bff66a`. Revision `c32b6342...` is its
documentation-only successor; the compiled payload hashes above are
unchanged.

## 5. Authoritative evidence sources

### W8 implementation and validation

- GitHub: `https://github.com/massif-01/qwen3-1.7b-coreai-ios`
- frozen repository commit:
  `46668db811559ce21b0006f07706a6d0bde08656`
- Hugging Face:
  `https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p`

Primary files:

- `REPRODUCTION.md`;
- `RESULTS.md`;
- `RELATED_WORK.md`;
- `patches/qwen3-1.7b-coreai-main.patch`;
- `recipes/qwen3_1_7b_w8_per_tensor.yaml`;
- `results/artifact-summary.json`;
- `results/device-runtime-summary.json`;
- `results/quality-summary.json`;
- `results/fidelity-v2-summary.json`;
- `paper/EXPERIMENT_PROTOCOL_V1.md`;
- `paper/FIDELITY_V2_AMENDMENT_1.md`;
- `paper/evidence/fidelity-v2/attempts/c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24/`;
- `results/upstream-validation.json`.

### Paired W8/INT4 comparison

- GitHub: `https://github.com/massif-01/qwen3-1.7b-coreai-reproduction`
- frozen repository commit:
  `34a4c08a9282bd076b8b5fe154c5507e6a8b3774`
- Hugging Face:
  `https://huggingface.co/massif/Qwen3-1.7B-CoreAI-GPU-INT4-4K-h16p`

Primary files:

- `docs/quality-protocol.md`;
- `docs/quality-result.md`;
- `docs/speed-protocol.md`;
- `docs/speed-result.md`;
- `benchmarks/results/quality-comparison.json`;
- `benchmarks/results/raw/w8-ane-no-thinking-results.jsonl`;
- `benchmarks/results/raw/int4-gpu-no-thinking-results.jsonl`;
- `benchmarks/results/raw/SHA256SUMS`;
- `benchmarks/tools/score_frozen_cmrc_py3.py`;
- `benchmarks/results/artifact-summary.json`.

The reproduction repository's integrity verifier passed across 38 files, and
its three published-metric tests passed during the 2026-08-28 evidence audit.

### Apple public status

- repository: `https://github.com/apple/coreai-models`;
- audited current-main commit:
  `7062017c8e86c6cf4f49b721ddc3494efcdb7c7d`;
- model request:
  `https://github.com/apple/coreai-models/issues/116`;
- closed, unmerged attempt:
  `https://github.com/apple/coreai-models/pull/196`.

Apple repository status is time-sensitive. The manuscript must attach an audit
date to every statement about official support.

## 6. Required provenance disclosure

The W8 artifact used in the historical A/B comparison had source identity:

`66325b4cc0657e1f89a7a0a92f37899d01ddc37d168295dbbad0d71bef7f75e3`

The current public W8 release was rebuilt under a neutral path and has source
identity:

`5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73`

They use the same frozen W8 mechanism but are not byte-identical. The historical
A/B data remains auditable through its raw predictions, protocols, aggregate
results, and recorded hashes. The current public W8 release separately passed
a six-case physical-device suite.

The report must not silently present the public W8 payload as the exact binary
used in the historical A/B run. This limitation is disclosed in Methods,
Reproducibility, and Limitations.

No new A/B device run is scheduled under Protocol v1. The fidelity-v2
confirmation is an authoring-model experiment and does not alter the paired
device outputs.

## 7. Existing data use and verification rules

Allowed without creating a new experiment:

- verify repository checksums;
- rerun deterministic scoring and statistical scripts against the existing raw
  prediction files;
- regenerate tables and figures from existing JSON/JSONL evidence;
- inspect existing trace summaries and manifests;
- verify links, commits, licenses, and Apple public status;
- correct transcription or arithmetic errors while recording the correction.

The corrected fidelity-v2 run is the sole post-freeze exception. It was
governed by its own prospectively committed protocol and amendment, uses a
separate attempt identity, and does not merge new outputs into the historical
device or paired-comparison datasets.

Not allowed to be merged into the existing dataset:

- newly generated model answers;
- new timing, RSS, trace, thermal, or energy runs;
- results from product-only model variants;
- product runtime measurements not already included in the frozen evidence;
- measurements from other devices or toolchain revisions.

If manuscript review later reveals that a core claim truly lacks evidence,
that work requires a separately approved `EXPERIMENT_PROTOCOL_V1.md`; it is not
implicitly authorized by this report protocol.

## 8. Planned manuscript structure

1. **Abstract** — problem, static iPhone result, paired trade-off, boundaries.
2. **Introduction** — missing Qwen3-1.7B official preset and deployment gap.
3. **Background** — Core AI static and dynamic language-model paths.
4. **Method** — W8 onboarding, quality-first selection, AOT, runtime profiles.
5. **Evidence and evaluation protocol** — existing frozen quality and speed
   procedures.
6. **Results** — fidelity, device validation, paired quality, size, memory,
   latency, and throughput.
7. **Discussion** — workload-dependent W8/ANE versus INT4/GPU trade-offs.
8. **Reproducibility** — artifacts, commits, hashes, applications, scripts.
9. **Limitations and threats to validity**.
10. **Conclusion**.

The abstract is written last, after all tables and claim wording are frozen.

## 9. Planned tables and figures

### Tables

- T1: Apple and community Qwen3-1.7B Core AI status at the audit date.
- T2: W8/ANE and INT4/GPU profile definitions.
- T3: corrected formal W8 tuning and holdout fidelity; historical selection
  evidence remains separate.
- T4: W8 physical-device suite and trace evidence.
- T5: paired CMRC2018 EM/F1 with confidence intervals and tests.
- T6: bundle size and peak RSS.
- T7: workload-specific TTFT, total time, and decode throughput.

### Figures

- F1: authoring-to-device pipeline for the static W8 path.
- F2: static fixed-KV ANE-preferred versus dynamic growing-KV GPU-preferred
  system profiles.
- F3: paired quality difference with bootstrap confidence intervals.
- F4: workload-dependent latency comparison.
- F5: bundle-size and peak-RSS comparison.

Every numerical table and chart must be generated from a cited machine-readable
evidence file. No manually typed chart values.

## 10. Limitations that must remain visible

- One device class: iPhone 15 Pro / A17 Pro / `h16p`.
- iOS 27 and Xcode 27-era prerelease tooling.
- CMRC2018 frozen 300-example paired quality sample, not a general capability
  benchmark and not proof of equivalence.
- W8 and INT4 profiles differ across several system dimensions; causal
  ANE-versus-GPU attribution is unsupported.
- No controlled numerical energy or battery-cost comparison.
- No complete WikiText-2 perplexity matrix.
- No claim of exclusive ANE execution.
- Historical A/B W8 binary and current public W8 binary are not byte-identical.
- No cross-device, production-background, or product-task generalization.

These are report boundaries, not automatic requirements for new experiments.

## 11. Writing and review workflow

1. Freeze this protocol in the initial repository commit.
2. Create an evidence index that maps every manuscript claim to an exact source
   file, commit, and hash.
3. Recompute existing quality statistics from the published raw JSONL files.
4. Generate Tables T2–T7 and Figures F3–F5 from machine-readable evidence.
5. Draft Methods and Results first.
6. Draft Background, Discussion, and Limitations.
7. Draft Introduction, Conclusion, title, and Abstract last.
8. Run an independent claim audit: every empirical sentence must resolve to
   evidence; every unsupported inference must be removed or labeled.
9. Produce the arXiv manuscript and public artifact links.

## 12. Change control

This protocol was frozen before manuscript drafting. Editorial fixes may amend
v1 through Git history. Changes to the central claim, included models, included
datasets, or evidence admission rules require `REPORT_PROTOCOL_V2.md`.

### Amendment 1 — corrected formal fidelity evidence

Manuscript review found that the earlier W8 summary did not provide a sufficient
formal record for the paper's fidelity claim. Before corrected model output was
produced, `EXPERIMENT_PROTOCOL_V1.md`, a frozen prompt manifest, and
`FIDELITY_V2_AMENDMENT_1.md` defined a one-shot confirmation with explicit
reference/candidate construction, shared serialized inputs, teacher-forcing
history, binary64 metrics, and a numerical-parity preflight. Corrected attempt
`c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24` completed all ten comparisons.

This amendment admits `results/fidelity-v2-summary.json` as the sole source for
reported W8 tuning and holdout values. The older
`results/quality-summary.json` remains historical evidence for W4 and mixed-W4/W8
rejection but no longer supplies manuscript fidelity metrics. All device,
trace, CMRC, speed, artifact-identity, and claim-boundary provisions of Protocol
v1 remain unchanged.
