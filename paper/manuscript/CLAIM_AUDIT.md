# Manuscript Claim Audit

- Manuscript: `qwen3-coreai-report.tex`
- Governing protocols: `../REPORT_PROTOCOL_V1.md`,
  `../REPORT_PROTOCOL_V2.md`, and `../REPORT_PROTOCOL_V3.md`
- Evidence ledger: `../EVIDENCE_INDEX.md`
- Audit date: 2026-09-01
- Audit result: **PASS**

## Audit method

This is a sentence-level audit of factual and empirical manuscript language,
not a summary of the paper. Each row identifies the sentence or tightly coupled
sentence family, the admitted claim IDs, the primary evidence class, and the
qualification that keeps the wording inside the governing protocol. Conceptual
statements that make no empirical assertion are not listed.

The companion `claim_audit.py` performs the mechanical half of the audit: it
rejects unknown claim IDs, missing citations, missing tables or figures,
generated-asset hash or inventory drift, unresolved placeholders, absent provenance
disclosures, and selected forbidden positive-claim patterns. Protocol v2 is a
retrospective post-review compatibility amendment. Protocol v3 is the
prospective admission protocol for the finalized speed-v2 Run J evidence only;
it does not change the historical quality, device-suite, trace, or compatibility
records. This file records the human semantic review that a pattern matcher
cannot replace.

## Sentence-level ledger

| Manuscript locus and sentence locator | Claim IDs | Primary evidence | Audit decision and mandatory boundary |
| --- | --- | --- | --- |
| Abstract — Apple repository lacked a 1.7B preset at the audited commit | CL-01 | Apple README and registry at `7062017c…` | Admitted only as dated repository state; no impossibility inference |
| Abstract — static W8 authoring-path definition | CL-03, CL-04, CL-05 | Locked recipe, manifests, patch, upstream validation | Admitted as a coupled static profile; “preferred” is retained |
| Abstract — corrected formal W8 holdout cosine, top-1, and NLL values | CL-06, CL-07 | `results/fidelity-v2-summary.json` and sealed corrected attempt | Admitted as authoring-model conversion fidelity under ten frozen inputs only; no compiled-device-logit claim |
| Abstract — four historical suites and 547/547 trace intervals | CL-08, CL-09 | Historical device summary and sanitized trace summary | Admitted with historical artifact identity and non-exclusive ANE wording |
| Abstract — separate public W8 suite | CL-10, CL-22 | Public-release device-validation JSON | Admitted as separate validation, not substituted into the A/B run |
| Abstract — later old-AOT failures and A-W8-CURRENT load-only diagnostic | CL-22, CL-28 | Post-review compatibility JSON | Admitted as two July-public-artifact failures and one A-W8-CURRENT load only; exported bytes and compiler producer both changed, so no cause is isolated; the later speed-v2 generation evidence is separate |
| Abstract — paired same-device setup | CL-11, CL-12 | INT4 artifact summary and quality protocol | Admitted as a profile comparison, not isolated hardware causality |
| Abstract — EM/F1 and zero-crossing interpretation | CL-13, CL-14 | Raw JSONL plus recomputed quality JSON | Admitted; reports both intervals crossing zero without an equivalence claim |
| Abstract — current storage, RSS, TTFT, prefill, and decode trade-off | CL-15, CL-16, CL-17, CL-18, CL-19, CL-20 | Protocol v3 and accepted speed-v2 Run J public bundle | Eight blocks, 120 observations, 60 pairs, and 20 observations per cell; admitted as workload-dependent and profile-level, with no energy or exclusive-compute claim |
| Introduction — shared base revision and tokenizer identity | CL-03 | W8 and comparison artifact summaries | Admitted; exact revision and hash are printed |
| Introduction — Apple sizes present, issue open, PR closed unmerged | CL-01, CL-02 | Apple commit plus dated API objects | Admitted; PR regression root cause remains undisclosed |
| Introduction — community dynamic GPU and stateful INT8 routes exist | CL-24, CL-25 | Frozen community model cards and manifests | Context only; no same-device comparison is inferred |
| Introduction contribution 1 — patch, recipe, tests, dry run, AOT procedure | CL-04, CL-05 | W8 repository objects | Admitted as reference implementation, not accepted upstream work |
| Introduction contribution 2 — historical model selection, corrected fidelity, device suites, trace, and later compatibility observation | CL-06, CL-07, CL-08, CL-09, CL-10, CL-28 | Historical selection record, fidelity-v2 attempt, device records, and compatibility JSON | Admitted with evaluator, artifact, trace, and load-only boundaries |
| Introduction contribution 3 — paired quality data and current public-artifact speed measurements | CL-11, CL-12, CL-13, CL-14, CL-15, CL-16, CL-17, CL-18, CL-19 | Historical comparison repository plus accepted speed-v2 Run J public bundle | Historical quality predictions remain retrospective; current speed measurements are the separately governed Protocol-v3 run |
| Introduction contribution 4 — public materials and identity boundary | CL-22, CL-23 | Public Git and Hub revisions | Admitted; exact historical W8 binary is not distributed |
| Background — Apple authoring/runtime surface and launch contribution policy | CL-26 | Apple root README at audited commit | Context only and time-bounded; no Apple endorsement |
| Background — ANE and palettization documentation interpretation | CL-09 | Apple documentation plus trace summary | Documentation motivates the route; trace, not documentation, supports participation |
| Related work — `mlboydaisuke` dynamic INT4/GPU h18p artifact | CL-24 | Frozen model-card snapshot | Community, iPhone 17 Pro, and not re-measured are all explicit |
| Related work — `kevinqz` stateful INT8 artifact and `not_run` gate | CL-25 | Model card, parity report, reproduction manifest | Context only; no comparable iPhone result is asserted |
| Shared source identity — revisions, tokenizer hash, 4,096 cap, h16p | CL-03, CL-04, CL-11 | Profile manifests | Admitted; remaining dimensions are explicitly said to differ |
| Static W8 — unquantized source, 196 projections, embedding treatment | CL-04 | Recipe and artifact summary | Admitted; excludes generic INT8/GPTQ/W4A16 shorthand |
| Static W8 — patch contents, Apple-main validation counts, and later full export/AOT | CL-05, CL-28, CL-29 | Patch, upstream-validation JSON, and compatibility JSON | The later output is a separately identified artifact; recipe identity is not treated as byte identity |
| Static W8 — 34 AOT functions and Swift runtime classes | CL-04, CL-08 | Artifact and device-runtime summaries | Admitted; architectural/runtime facts, not performance causality |
| Dynamic INT4 — block-32, dynamic KV, GPU-preferred, selected engine | CL-11 | Comparison artifact and feasibility summaries | Admitted with no exclusive-GPU inference |
| Dynamic INT4 — chat-template no-thinking control | CL-21 | Runtime patch, `NO_THINKING.md`, quality protocol | Admitted for the pinned benchmark only |
| Methods — retrospective evidence, compatibility diagnostic, and prospective speed admission | CL-07, CL-15, CL-16, CL-17, CL-18, CL-19, CL-20, CL-23, CL-28 | Protocols v1--v3, deterministic pipeline provenance, compatibility JSON, and accepted speed-v2 Run J bundle | The paper pipeline performs no model inference or device measurement; Protocol v2 governs only the load diagnostic, while Protocol v3 governs the separate current speed run |
| Methods — historical/public W8 payloads are not byte-identical | CL-22 | Artifact identity registry | Artifact identities remain separate |
| W8 selection — rejected W4/mixed candidates and mean-cosine range | CL-06 | Historical `quality-summary.json` and results narrative | Admitted only as model-selection history; its W8 headline metrics are superseded |
| W8 fidelity method — corrected formal protocol, ten inputs, shared teacher-forcing history, and binary64 macro | CL-07 | `FIDELITY_V2_AMENDMENT_1.md`, evaluator, and sealed corrected attempt | Admitted for the fake-palettized authoring model on CPU; not compiled-device logits or downstream capability |
| W8 fidelity method — 10/10 comparisons and supersession of the earlier W8 values | CL-06, CL-07 | `results/fidelity-v2-summary.json` and historical relationship field | Admitted; the older summary remains model-selection history only |
| Device method — six case types, four suites, zero final hard failures | CL-08 | Historical device summary | Admitted for A-W8-HISTORICAL only |
| Device method — trace summary supports participation, not exclusivity | CL-09 | Sanitized trace summary | Mandatory non-exclusivity qualifier present |
| Device method — separate public rebuild suite | CL-10, CL-22 | Public-release device-validation JSON | Admitted; not substituted for historical A/B |
| Device method — two later July-public-AOT failures and one A-W8-CURRENT load | CL-22, CL-28 | Compatibility JSON | The diagnostic is load-only on one device/runtime and supports no generation, trace, cold-cache, or single-factor causal claim; later speed-v2 generation is admitted separately under Protocol v3 |
| CMRC method — dataset task, 300 examples, strata, sample hash | CL-12, CL-27 | CMRC paper/source and frozen protocol | Admitted as subset-level Chinese span extraction only |
| CMRC method — shared controls and exact Python-3 reanalysis | CL-12, CL-13 | Protocol, raw JSONL, source lock, recomputed JSON | Admitted; explicitly not Python-2 byte parity |
| CMRC method — bootstrap/sign-test procedure and zero interpretation | CL-14 | Published scorer and recomputed JSON | Admitted; no equality or non-inferiority conclusion |
| CMRC method — initial -1.0 heuristic and -1.67 EM failure | CL-13, CL-14 | Frozen feasibility protocol and recomputed results | Admitted alongside the distinct non-significant paired test |
| Speed method — public profiles, controls, and fixed eight-block schedule | CL-17, CL-18, CL-19 | Protocol v3 and accepted speed-v2 Run J public bundle | Schedule W8, INT4, INT4, W8, INT4, W8, W8, INT4; four blocks per profile, 120 completed observations, 60 pairs, and 20 completed observations per profile/workload cell |
| Speed method — workloads and complete Protocol-v3 metric set | CL-17, CL-18, CL-19 | Accepted speed-v2 Run J analyzer summary | Per-cell medians cover input tokens, output tokens, token TTFT, visible TTFT, total time, visible-decode throughput, and end-to-end visible throughput; no P95 or discarded accepted observation |
| Results — corrected formal W8 tuning and holdout values | CL-07 | Generated T3 from `results/fidelity-v2-summary.json` | Admitted as authoring-model fidelity; no compiled-device logits, capability benchmark, or full perplexity claim |
| Results — Apple-main validation and later export/AOT | CL-05, CL-28, CL-29 | Upstream-validation and compatibility JSON | Reports completion in the main text; exact repeated-export identities and the byte-determinism boundary remain in the appendix |
| Results — historical load/RSS/unload and long-context TTFT | CL-08 | Historical device summary | Admitted for specialization-cache-warm historical suite |
| Results — trace counts and public rebuild RSS/TTFT | CL-09, CL-10 | Separate historical trace and public validation records | Admitted with separate identities |
| Results — post-review compatibility values | CL-28 | Generated T8 and compatibility JSON | Two July-public-AOT failures; one 41.932-second A-W8-CURRENT load; 2,737.0 MiB peak process RSS; unload and exit zero; this diagnostic is not comparative performance |
| Results — 300 completions, EM/F1, exact counts, identical responses | CL-13 | Raw predictions and generated T5 | Admitted for frozen subset only |
| Results — observed differences, intervals, and p-values | CL-14 | Recomputed paired analysis and generated F3 | Admitted; zero crossing and no-equivalence statement retained |
| Results — compiled-model storage | CL-15 | Accepted speed-v2 Run J public bundle and generated T6 | W8 1,711.4 MiB and INT4 924.6 MiB; each value is the median of four identical `estimatedDiskBytes` observations converted to MiB, not application-download size |
| Results — peak process RSS | CL-16 | Accepted speed-v2 Run J public bundle and generated T6 | W8 3,409.1 MiB and INT4 1,978.0 MiB; each is the maximum after-unload process peak across four blocks, not system RAM |
| Results — business 150/56 versus 150/22 medians | CL-17 | Accepted speed-v2 Run J and generated T7 | W8 token/visible TTFT 0.242277/0.242277 s, total 2.234118 s, visible decode 27.542 tok/s, E2E visible 25.066 tok/s; INT4 1.643390/1.643390 s, 2.099392 s, 45.841 tok/s, and 10.479 tok/s; differing output medians preclude a fixed-output total-time claim |
| Results — near-4K 3,778/6 medians | CL-18 | Accepted speed-v2 Run J and generated T7 | W8 token/visible TTFT 3.719729/3.719729 s, total 3.952369 s, visible decode 21.394 tok/s, E2E visible 1.518 tok/s; INT4 13.392772/13.392772 s, 13.521936 s, 38.556 tok/s, and 0.444 tok/s; only five post-first visible tokens make decode secondary |
| Results — sustained-decode 108/256 medians | CL-19 | Accepted speed-v2 Run J and generated T7 | W8 token/visible TTFT 0.205123/0.205124 s, total 9.675167 s, visible decode 26.931 tok/s, E2E visible 26.459 tok/s; INT4 0.390175/0.390175 s, 6.453672 s, 42.210 tok/s, and 39.760 tok/s; this workload measures sustained throughput, not answer quality |
| Results — no universal winner | CL-20 | CL-15 through CL-19 | Admitted as profile-level synthesis only |
| Discussion — workload-specific explanations | CL-17, CL-18, CL-19, CL-20 | Three workload result groups | Admitted as interpretation of observed workloads, not a causal hardware result |
| Discussion — profiles change together | CL-04, CL-11 | Profile manifests and T2 | Mandatory confounding boundary retained |
| Discussion — lower INT4 storage/RSS and higher decode medians versus lower W8 TTFT and near-4K total | CL-15, CL-16, CL-17, CL-18, CL-19 | Accepted speed-v2 Run J | INT4's visible-decode median is higher in all three workloads; W8's token TTFT is lower in all three and its near-4K total is lower; limited to measured workload shapes with no routing threshold |
| Discussion — CMRC does not settle bookmark-task quality | CL-12, CL-13, CL-14, CL-27 | CMRC task definition and paired result | Admitted scope statement; failed heuristic remains visible |
| Discussion — artifact/compiler/runtime compatibility boundary | CL-22, CL-28, CL-29 | Compatibility JSON and three-artifact registry | Observation is consistent with a compatibility boundary but does not attribute an OS, compiler, artifact, or memory cause |
| Reference implementation — path and public materials | CL-04, CL-05, CL-06, CL-08, CL-09, CL-23 | W8 Git/Hub materials | Admitted; no Apple acceptance or regression-fix claim |
| Reference implementation — community GPU and INT8 context | CL-24, CL-25 | Frozen community objects | Context only; no deficiency or superiority inference |
| Reproducibility — Git, historical Hub, and current speed-v2 profile revisions | CL-22, CL-23 | Frozen public repositories and S-SPEED-V2 | Separately identifies A-W8-HISTORICAL, A-W8-JULY-PUBLIC, A-W8-CURRENT at `75bbe…`, and INT4 at `c32b…` |
| Reproducibility — recipe and compiled-file hashes | CL-22, CL-23 | Hub manifests and checksum locks | Admitted exact identifiers |
| Reproducibility — locked fidelity-v2 summary, deterministic pipeline, and byte-identical Python-3 CMRC JSON | CL-07, CL-12, CL-13, CL-23 | Source lock, corrected fidelity summary, generated provenance, and tests | Admitted; the pipeline performs no model inference or device measurement |
| Reproducibility — dataset is reconstructed, not redistributed | CL-12, CL-27 | Official CMRC commit/hashes | Admitted dataset-boundary statement |
| Reproducibility — historical/public W8 identity distinction | CL-22 | Artifact identity registry | Exact historical replay requires the historical binary |
| Appendix — A-W8-CURRENT diagnostic identity and repeated-export hashes | CL-22, CL-28, CL-29 | Compatibility JSON | The load-only observation predates publication and speed-v2 use of the same artifact; two unequal raw exports do not establish a semantic or numerical difference |
| Limitations — one device and version-specific toolchains | CL-08, CL-10, CL-11, CL-17, CL-18, CL-19 | Historical and speed-v2 device records | Admitted for one device class; universal compatibility is rejected |
| Limitations — post-review compatibility scope | CL-22, CL-28, CL-29 | Compatibility JSON | One runtime, two July-public-artifact attempts, and one A-W8-CURRENT load attempt; the diagnostic itself has no generation, trace, cold-cache, or causal claim, and remains separate from later speed-v2 |
| Limitations — coupled profiles | CL-04, CL-11 | Profile manifests | Admitted; causal attribution rejected |
| Limitations — trace non-exclusivity | CL-09 | Trace summary | Mandatory qualification retained |
| Limitations — ten-input authoring fidelity plus 300-example CMRC scope, zero-crossing intervals, and failed heuristic | CL-07, CL-12, CL-13, CL-14 | Fidelity-v2 and frozen CMRC evidence | Admitted; compiled-device-logit, equivalence, and full-task generalization claims rejected |
| Limitations — 20 timing observations per profile/workload cell | CL-17, CL-18, CL-19 | Accepted speed-v2 Run J | Four blocks per profile and 20 completed observations per cell; P95, significance, universal compatibility, and cold-load-distribution claims remain rejected |
| Limitations — historical/public W8 identity distinction | CL-22 | Artifact identity registry | Exact replay limitation retained |
| Conclusion — reproducible static route and measured ANE participation | CL-04, CL-05, CL-08, CL-09, CL-10 | Patch, runtime suites, trace, public validation | Admitted with device/version and participation wording |
| Conclusion — corrected authoring-model W8 fidelity and workload-dependent profile trade-off | CL-07, CL-15, CL-16, CL-17, CL-18, CL-19, CL-20 | Fidelity-v2, size, RSS, and speed evidence | Admitted; no compiled-device-logit, universal-winner, or energy claim |

## Rejected or rewritten claim classes

The final draft contains none of the following as findings:

- priority claims such as “first ever”;
- Apple acceptance, adoption, endorsement, or a promise to merge;
- a root-cause explanation for pull request 196;
- exclusive ANE or GPU execution;
- causal ANE-versus-GPU or W8-versus-INT4 superiority;
- quality parity, equivalence, or non-inferiority;
- energy, battery, or joules-per-token superiority;
- universal iPhone compatibility;
- background reliability, thermal endurance, or Jetsam conclusions;
- substitution of either later W8 build for the historical A/B binary;
- an iOS-upgrade, compiler-fix, or device-memory root-cause claim;
- generation, ANE-trace, cold-start, or comparative-performance claims derived
  from the Protocol-v2 load-only diagnostic; the separate Protocol-v3 speed-v2
  generation measurements do not alter that diagnostic boundary;
- path-independent byte reproducibility or semantic difference inferred from
  two authoring `main.mlirb` digests generated under different output directories.

## Final disposition

The sentence-level review is complete. The current performance claims use only
the finalized speed-v2 Run J bundle under Protocol v3; the historical,
July-public, and current W8 identities and the separate Protocol-v2 load-only
diagnostic remain distinct. Every empirical manuscript statement is within the
admitted evidence and protocol boundaries listed above. Claim IDs remain in the
LaTeX source but are hidden in the submission PDF. PDF compilation and
page-level visual review are separate publication checks.
