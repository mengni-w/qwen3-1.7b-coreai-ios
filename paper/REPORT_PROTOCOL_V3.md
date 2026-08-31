# Qwen3-1.7B on iPhone with Apple Core AI

## Technical Report Protocol v3

**Status:** prospective speed-evidence admission protocol
**Date:** 2026-08-31
**Amends:** `REPORT_PROTOCOL_V1.md` and `REPORT_PROTOCOL_V2.md` only for the
new public-artifact speed-confirmation result
**Does not alter:** the historical speed dataset, paired CMRC2018 predictions,
fidelity-v2 evidence, compatibility observations, or ANE-trace evidence

## 1. Purpose and chronology

The original report used an earlier three-sample speed comparison. A separate
repository subsequently defined `public-artifact-speed-confirmation-v2`, an
eight-block, paired, physical-device acquisition intended to replace that
historical comparison in the report's current-performance tables and figures.
This document freezes the report-side acceptance and reduction rules before a
successful run is admitted. It does not select a run ID and contains no result
values.

An interrupted attempt, including Run I, remains part of the acquisition
history but cannot supply a timing, memory, or storage statistic. This protocol
does not reinterpret an aborted or nonconformant attempt as a partial result.

## 2. Frozen acquisition identity

The report may admit only an acquisition whose public analyzer summary records
all of the following identities:

- protocol: `public-artifact-speed-confirmation-v2`;
- speed protocol commit:
  `14e4067a960cbac5a06b372b502355074304d0d4`;
- clean benchmark source commit embedded in both Release applications:
  `29271b8d9ca9a2d36d6752debc0ac37416aa8c59`;
- runtime commit: `85e2f2d8c6433825e64219a32693ed1a4aed519f`;
- patched runtime source SHA-256:
  `11cf90c72b4b4b6695c6fdbc63e58dc7d41633a7bba9ffa5273852cc079cf0e0`;
- target device identifier: `iPhone16,1`;
- build configuration: Release;
- context length: 4096; and
- architecture: `h16p`.

The admitted profile identities are:

| Profile | Repository revision | Artifact-manifest SHA-256 |
| --- | --- | --- |
| `W8_ANE` | `75bbe06906cb5d953e602e3e4fb6364187c81822` | `91c68e82e280a36d39aaeef9b8726ab1d59e52760b6f970db67c334a674d47b2` |
| `INT4_GPU` | `c32b6342c98e5e23363f692e614bccca37f24234` | `18c22f4f35ae54421a58593af2858979c13b0cf6f5a15d18c044469007fa86ae` |

Artifact names such as W8 and INT4 describe the frozen profiles. They do not,
by themselves, establish that all measured operations executed exclusively on
ANE or GPU. Device-execution claims remain governed by separate trace evidence.

## 3. Publication-only evidence interface

The paper pipeline accepts a copied publication bundle, not the private
acquisition directory. Its root contains exactly:

- `FINALIZED.json`; and
- the acquisition's byte-identical `public/` directory.

Files under the private `host/`, build-result, or device-control paths are not
pipeline inputs. The public finalization certificate may retain its
content-addressed binding to a private evidence index, but the pipeline neither
resolves nor reads that private path.

The pipeline recomputes the SHA-256 and byte count of every file enumerated by
`public/evidence-index.json`. The index must enumerate every regular file under
`public/` except itself, with no duplicate, absolute, parent-traversing, or
symlink path. The finalization certificate must bind the exact public index and
the exact `public/host/host-run-record.json`; the public index must bind the
exact analyzer output at `public/results/speed-v2-summary.json`.

## 4. Admission gate

A bundle is admissible only if all of these conditions hold:

1. `FINALIZED.json` has schema version 1 and status `passed`.
2. The public host record has schema version 4, experiment
   `public-artifact-speed-confirmation-v2`, pre-finalization outcome `eligible`,
   and an empty `conformanceErrors` list.
3. The host record and analyzer summary have the same run ID and contain the
   exact identities in Section 2.
4. The host record contains the frozen eight-block physical schedule:
   `W8, INT4, INT4, W8, INT4, W8, W8, INT4`.
5. The analyzer output has schema version 2, analysis name
   `public-artifact-speed-confirmation-v2`, and conformance status `passed`.
6. The analyzer reports 8 physical blocks, 120 planned profile samples, and 60
   paired logical samples. Each profile has four blocks and 20 completed,
   zero-failed samples for each of the three workloads. Each workload has 20
   successful pairs and no unpaired failure.
7. Every profile/workload cell contains the complete frozen analyzer metric set.
   Its metric summaries contain the same 20 logical sample IDs and the same
   sample-to-physical-block assignments. The W8 and INT4 cells for a workload
   contain the same logical sample-ID set.
8. Every paired metric contains exactly those 20 logical IDs. For each ID, its
   recorded A value, B value, and A-minus-B value equal the corresponding public
   profile observations and their difference. The pipeline recomputes the
   paired five-number summary from those differences.
9. The pipeline recomputes every admitted median, first and third quartile,
   minimum, and maximum from the public observation values. It also checks the
   timing order and the two throughput formulas defined in Section 5.
10. Each profile's after-unload peak-RSS summary contains one observation for
   each of that profile's four scheduled physical blocks, with no duplicate or
   out-of-schedule block.

Failure of any gate rejects the bundle as a whole. In particular, `aborted`,
`nonconformant`, `pending-finalization`, missing-finalization, incomplete-block,
or partially successful evidence produces no paper statistic.

## 5. Frozen report reduction

The analyzer's 20 observations per profile and workload are the unit of the
reported descriptive summaries. The paper pipeline does not rescore console
logs or discard an observation after seeing its value.

For each profile and workload, the current-performance table reports:

- median input tokens and median output tokens;
- median token time to first token (`tokenTTFTSeconds`);
- median visible time to first token (`visibleTTFTSeconds`);
- median total generation time (`totalSeconds`);
- median visible decode tokens per second; and
- median end-to-end visible tokens per second.

The reduction retains the acquisition protocol's definitions. Token TTFT is
the interval from stream creation to the first snapshot with a positive output
token count. Visible TTFT ends at the first snapshot with a positive visible
token count. Total time ends when the stream terminates normally. If
`v_first` is the visible-token count at visible TTFT and `v_final` is the final
visible-token count, visible decode throughput is
`(v_final - v_first) / (total - visible TTFT)`. End-to-end visible throughput is
`v_final / total`. The admitted run disables reasoning, so the public summary
must record visible tokens equal to output tokens, and all per-sample timing and
throughput fields must satisfy these identities within the acquisition
protocol's `1e-9` relative and absolute tolerance.

The latency figure shows the analyzer-provided individual observations and
their median for token TTFT and total generation time. It shows all 20 accepted
observations per cell. No p95, hypothesis test, confidence interval, or causal
hardware attribution is added to the speed result.

For each profile, compiled-model storage is the median of the four
`estimatedDiskBytes` values recorded at model load, converted to MiB. The value
is admissible only if all four observations are identical. Peak process RSS is
the maximum of the four after-unload `peakResidentMiB` observations. These are
process and artifact measurements under the acquisition protocol, not total
system memory or application-download size.

## 6. Permitted interpretation

The accepted run may support a descriptive, paired comparison of the two exact
public artifacts on the recorded iPhone 15 Pro, operating-system build,
toolchain, runtime patch, prompts, schedule, and environmental gates. It may
replace the report's historical speed rows when the manuscript, tables,
figures, provenance, evidence index, and claim audit all cite the same accepted
bundle.

## 7. Prohibited interpretation

The report must not use this acquisition to claim:

- universal iPhone performance or compatibility;
- energy efficiency, battery life, or thermal superiority;
- exclusive ANE or GPU execution without the separately admitted trace;
- a quantization-only causal effect, because the profiles differ in static
  versus dynamic execution, KV-cache policy, and target route;
- a cold-start distribution beyond the protocol's recorded load procedure;
- statistical significance or equivalence; or
- any result derived from an interrupted, failed, or nonconformant attempt.

## 8. Change control

After a successful run is copied into the publication-only interface, a later
evidence-integration commit must freeze that bundle's relative path,
finalization SHA-256, public-index SHA-256, and run ID in the report source lock.
Changing the acquisition identity, schedule, reduction rule, or admission gate
requires a new prospective protocol before collecting replacement data.
