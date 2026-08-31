# Qwen3-1.7B on iPhone with Apple Core AI

## Technical Report Protocol v2

**Status:** post-review evidence-admission protocol
**Date:** 2026-08-29
**Amends for post-review compatibility evidence:** `REPORT_PROTOCOL_V1.md`
**Preserves:** the historical device, CMRC2018, speed, fidelity-v2, and trace
datasets and their original identities

## 1. Purpose and chronology

Protocol v1 governed a retrospective report based on evidence that predated
manuscript drafting. It allowed the separately preregistered fidelity-v2 study
but did not admit a new device measurement. During final review, the previously
published W8 AOT failed to load in the current device environment. A bounded
compatibility investigation then produced the observations recorded in
`W8_COMPATIBILITY_OBSERVATION_1.md`.

This protocol governs whether and how those observations may be added to the
report. It does not retroactively describe them as preregistered. They are a
descriptive post-review compatibility diagnostic, not a confirmatory
performance experiment.

## 2. Preserved evidence boundaries

The following evidence remains unchanged:

- the four historical W8 six-case suites and their historical artifact;
- the historical Core AI trace and its ANE-participation claim;
- the earlier six-case validation of the exact public W8 rebuild in its
  recorded environment;
- the paired W8/INT4 CMRC2018 predictions and statistical analysis;
- the historical speed, bundle-size, and peak-RSS comparison;
- the corrected fidelity-v2 authoring-model evaluation.

The post-review candidate cannot substitute for any of those artifacts or
datasets. It has no generation, quality, or trace evidence.

## 3. Admitted compatibility observation

Protocol v2 admits two new claim classes: `CL-28`, a load-only compatibility
observation tied to exact artifact, compiler, device, and runtime identities;
and `CL-29`, the two-run authoring-export byte-identity observation.

The admissible observed facts are:

1. On an iPhone 15 Pro running iOS 27 build `24A5424a`, the previously
   published W8 AOT produced by `coreai-build-3600.75.3` terminated during
   `ANECCompileOffline` in two load-only attempts. The second followed a full
   reboot request, a host timeout while waiting for the device, and a subsequent
   observation that the same device was again booted and connected.
2. A separately exported candidate built from the same pinned checkpoint and
   W8 recipe and compiled by `coreai-build-3600.83.1` completed one load in
   `41.931619875` seconds, reached `2737.046875 MiB` peak process RSS, completed
   unload, and exited with status `0` on the same phone and OS build.
3. No generation request or Instruments trace was performed with the new
   candidate.
4. The cache state was not controlled or observed sufficiently to characterize
   the candidate load as cache-cold.
5. Two exports made from the same locked inputs and export parameters, with
   only the output directory changed, produced different raw source digests and
   sizes. This is evidence of non-identical raw output in those two runs, not of
   a semantic, structural, weight, or numerical difference.

## 4. Artifact identities

### Previously published W8 AOT

- authoring `main.mlirb` SHA-256 recorded by the AOT metadata:
  `5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73`
- compiled `main-h16p.mlirb` SHA-256:
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`
- compiler producer: `coreai-build-3600.75.3`

### Post-review W8 candidate

- pinned base revision:
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Apple `coreai-models` commit:
  `04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`
- recipe SHA-256:
  `dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72`
- authoring `main.mlirb` SHA-256 recorded by the AOT metadata:
  `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c`
- compiled `main-h16p.mlirb` SHA-256:
  `09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`
- complete `.aimodelc` file-list fingerprint:
  `182336f4654bb735bcad35e45f7832756c34469931ad96d872532dca727ebd8d`
- compiler producer: `coreai-build-3600.83.1`

### Same-parameter repeat export

- first authoring `main.mlirb` SHA-256:
  `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c`
- first authoring `main.mlirb` size: `1,739,655,751 bytes`
- second authoring `main.mlirb` SHA-256:
  `12349a9ad32bf2a1d2f9a6f201ffec3125c28c027786fa9925dc34669d8bc946`
- second authoring `main.mlirb` size: `1,739,655,747 bytes`

Every runtime observation remains bound to its exact compiled artifact. Sharing
a source checkpoint and recipe does not make two exported or compiled outputs
interchangeable.

## 5. Permitted interpretation

The compatibility observation may support the following conclusion:

> In the recorded environment, the previously published AOT failed in two
> load-only attempts, while a separately exported artifact produced by a later
> Core AI compiler completed one load and unload. The two non-identical
> artifact/toolchain combinations had different load outcomes. This contrast is
> consistent with an artifact/compiler/runtime compatibility boundary but does
> not isolate its cause.

The earlier public-artifact six-case pass remains a valid observation for its
recorded artifact and environment. The later failures limit claims of current
or universal compatibility; they do not erase the earlier result.

## 6. Prohibited interpretations

The report must not claim or imply that:

- an iOS update caused the old artifact to fail;
- `coreai-build 3600.83.1` fixed a compiler defect;
- either failure was caused by device memory pressure;
- the reboot request and subsequent reconnect observation establish an
  instrumented boot transition or an absolutely clean cache or system state;
- the `41.931619875`-second observation is a cold-start benchmark;
- the new candidate can generate correctly or execute on ANE;
- the new candidate has a trace, quality, or speed result;
- the two source exports are semantically or numerically different;
- this check establishes path-independent export nondeterminism beyond the two
  observed runs;
- recipe identity establishes byte-identical artifact identity.

## 7. Manuscript placement

The observation may appear in:

- the Abstract, in a compressed form that includes the non-causal boundary;
- Methods, explicitly labelled load-only and post-review;
- Results, with the one-attempt and two-attempt counts;
- Discussion, as a compatibility-specific contrast with an explicit causal
  boundary;
- Reproducibility, with exact identities;
- Limitations, with no cold-cache, generation, trace, or causal claim; and
- Appendix Table T8, separate from the historical suite and trace table.

Before final submission, the evidence index and sentence-level claim audit must
admit and audit `CL-28` and `CL-29`, and all numerical values must resolve to a
machine-readable repository evidence object. Until then, the manuscript
integration is provisional.

## 8. Change control

This protocol admits only the compatibility observation above. Any later
generation, trace, speed, energy, thermal, or cross-device result requires its
own prospective amendment or successor protocol before data collection. An ANE
trace of the new candidate cannot be inferred from the historical trace and may
be admitted only after the exact new trace target is frozen and the trace is
collected under its own protocol.
