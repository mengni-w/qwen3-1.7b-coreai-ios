# Manuscript Claim Audit

- Manuscript: `qwen3-coreai-report.tex`
- Governing protocol: `../REPORT_PROTOCOL_V1.md`
- Evidence ledger: `../EVIDENCE_INDEX.md`
- Audit date: 2026-08-28
- Audit result: **PASS**

## Audit method

This is a sentence-level audit of factual and empirical manuscript language,
not a summary of the paper. Each row identifies the sentence or tightly coupled
sentence family, the admitted claim IDs, the primary evidence class, and the
qualification that keeps the wording inside Protocol v1. Conceptual statements
that make no empirical assertion are not listed.

The companion `claim_audit.py` performs the mechanical half of the audit: it
rejects unknown claim IDs, missing citations, missing tables or figures,
generated-asset hash or inventory drift, unresolved placeholders, absent provenance
disclosures, and selected forbidden positive-claim patterns. This file records
the human semantic review that a pattern matcher cannot replace.

## Sentence-level ledger

| Manuscript locus and sentence locator | Claim IDs | Primary evidence | Audit decision and mandatory boundary |
| --- | --- | --- | --- |
| Abstract — Apple repository lacked a 1.7B preset at the audited commit | CL-01 | Apple README and registry at `7062017c…` | Admitted only as dated repository state; no impossibility inference |
| Abstract — static W8 authoring-path definition | CL-03, CL-04, CL-05 | Locked recipe, manifests, patch, upstream validation | Admitted as a coupled static profile; “preferred” is retained |
| Abstract — W8 holdout cosine, top-1, and NLL values | CL-06, CL-07 | `quality-summary.json` | Admitted as conversion fidelity under frozen inputs only |
| Abstract — four historical suites and 547/547 trace intervals | CL-08, CL-09 | Historical device summary and sanitized trace summary | Admitted with historical artifact identity and non-exclusive ANE wording |
| Abstract — separate public W8 suite | CL-10, CL-22 | Public-release device-validation JSON | Admitted as separate validation, not substituted into the A/B run |
| Abstract — paired same-device setup | CL-11, CL-12 | INT4 artifact summary and quality protocol | Admitted as a profile comparison, not isolated hardware causality |
| Abstract — EM/F1 and zero-crossing interpretation | CL-13, CL-14 | Raw JSONL plus recomputed quality JSON | Admitted; reports both intervals crossing zero without an equivalence claim |
| Abstract — storage, RSS, TTFT, prefill, and decode trade-off | CL-15, CL-16, CL-17, CL-18, CL-19, CL-20 | Locked speed report and deterministic extraction | Admitted as workload-dependent and profile-level; no energy claim |
| Introduction — shared base revision and tokenizer identity | CL-03 | W8 and comparison artifact summaries | Admitted; exact revision and hash are printed |
| Introduction — Apple sizes present, issue open, PR closed unmerged | CL-01, CL-02 | Apple commit plus dated API objects | Admitted; PR regression root cause remains undisclosed |
| Introduction — community dynamic GPU and stateful INT8 routes exist | CL-24, CL-25 | Frozen community model cards and manifests | Context only; no same-device comparison is inferred |
| Introduction contribution 1 — patch, recipe, tests, dry run, AOT procedure | CL-04, CL-05 | W8 repository objects | Admitted as reference implementation, not accepted upstream work |
| Introduction contribution 2 — quality selection, device suites, trace | CL-06, CL-07, CL-08, CL-09, CL-10 | W8 quality and device records | Admitted with artifact and trace boundaries |
| Introduction contribution 3 — paired data and measurements | CL-11, CL-12, CL-13, CL-14, CL-15, CL-16, CL-17, CL-18, CL-19 | Comparison repository | Admitted; no new run or measurement is implied |
| Introduction contribution 4 — public materials and identity boundary | CL-22, CL-23 | Public Git and Hub revisions | Admitted; exact historical W8 binary is not distributed |
| Background — Apple authoring/runtime surface and launch contribution policy | CL-26 | Apple root README at audited commit | Context only and time-bounded; no Apple endorsement |
| Background — ANE and palettization documentation interpretation | CL-09 | Apple documentation plus trace summary | Documentation motivates the route; trace, not documentation, supports participation |
| Related work — `mlboydaisuke` dynamic INT4/GPU h18p artifact | CL-24 | Frozen model-card snapshot | Community, iPhone 17 Pro, and not re-measured are all explicit |
| Related work — `kevinqz` stateful INT8 artifact and `not_run` gate | CL-25 | Model card, parity report, reproduction manifest | Context only; no comparable iPhone result is asserted |
| Shared source identity — revisions, tokenizer hash, 4,096 cap, h16p | CL-03, CL-04, CL-11 | Profile manifests | Admitted; remaining dimensions are explicitly said to differ |
| Static W8 — unquantized source, 196 projections, embedding treatment | CL-04 | Recipe and artifact summary | Admitted; excludes generic INT8/GPTQ/W4A16 shorthand |
| Static W8 — patch contents and Apple-main validation counts | CL-05 | Patch and upstream-validation JSON | Admitted with exact later commit and no repeated full-export claim |
| Static W8 — 34 AOT functions and Swift runtime classes | CL-04, CL-08 | Artifact and device-runtime summaries | Admitted; architectural/runtime facts, not performance causality |
| Dynamic INT4 — block-32, dynamic KV, GPU-preferred, selected engine | CL-11 | Comparison artifact and feasibility summaries | Admitted with no exclusive-GPU inference |
| Dynamic INT4 — chat-template no-thinking control | CL-21 | Runtime patch, `NO_THINKING.md`, quality protocol | Admitted for the pinned benchmark only |
| Methods — retrospective evidence creates no new outputs or measurements | CL-23 | Protocol and deterministic pipeline provenance | Admitted as study-process boundary |
| Methods — historical/public W8 payloads are not byte-identical | CL-22 | Artifact identity registry | Artifact identities remain separate |
| W8 selection — rejected W4/mixed candidates and mean-cosine range | CL-06 | Quality summary and results narrative | Admitted; no complete candidate raw-logit release is implied |
| Device method — six case types, four suites, zero final hard failures | CL-08 | Historical device summary | Admitted for A-W8-HISTORICAL only |
| Device method — trace summary supports participation, not exclusivity | CL-09 | Sanitized trace summary | Mandatory non-exclusivity qualifier present |
| Device method — separate public rebuild suite | CL-10, CL-22 | Public-release device-validation JSON | Admitted; not substituted for historical A/B |
| CMRC method — dataset task, 300 examples, strata, sample hash | CL-12, CL-27 | CMRC paper/source and frozen protocol | Admitted as subset-level Chinese span extraction only |
| CMRC method — shared controls and exact Python-3 reanalysis | CL-12, CL-13 | Protocol, raw JSONL, source lock, recomputed JSON | Admitted; explicitly not Python-2 byte parity |
| CMRC method — bootstrap/sign-test procedure and zero interpretation | CL-14 | Published scorer and recomputed JSON | Admitted; no equality or non-inferiority conclusion |
| CMRC method — initial -1.0 heuristic and -1.67 EM failure | CL-13, CL-14 | Frozen feasibility protocol and recomputed results | Admitted alongside the distinct non-significant paired test |
| Speed method — controls, warm-up, three tagged samples | CL-17, CL-18, CL-19 | Frozen speed protocol/report | Admitted; repeat-input cache contamination excluded before accepted run |
| Speed method — workloads and replaced 24-token W8 attempt | CL-17, CL-18, CL-19 | Fixed-hash speed report | Admitted with exclusion/replacement disclosure |
| Results — W8 holdout values | CL-07 | Generated T3 from quality JSON | Admitted as fidelity; no full perplexity matrix claim |
| Results — Apple-main validation boundary | CL-05 | Upstream-validation JSON | Admitted without binary identity or fresh full-export inference |
| Results — historical load/RSS/unload and long-context TTFT | CL-08 | Historical device summary | Admitted for specialization-cache-warm historical suite |
| Results — trace counts and public rebuild RSS/TTFT | CL-09, CL-10 | Separate historical trace and public validation records | Admitted with separate identities |
| Results — 300 completions, EM/F1, exact counts, identical responses | CL-13 | Raw predictions and generated T5 | Admitted for frozen subset only |
| Results — observed differences, intervals, and p-values | CL-14 | Recomputed paired analysis and generated F3 | Admitted; zero crossing and no-equivalence statement retained |
| Results — bundle size | CL-15 | Locked speed report and manifests | Admitted as logical compiled-resource-directory size |
| Results — peak process RSS | CL-16 | Locked speed report | Admitted as benchmark process RSS, not system RAM |
| Results — 161/60 medians | CL-17 | Extracted accepted samples | Admitted as three-sample medians; no P95 |
| Results — 3,790/10 medians and decode-rate omission | CL-18 | Extracted accepted samples | Admitted; nine-visible-token limitation retained |
| Results — 120/256 medians | CL-19 | Extracted accepted samples | Admitted as sustained-throughput workload, not answer quality |
| Results — no universal winner | CL-20 | CL-15 through CL-19 | Admitted as profile-level synthesis only |
| Discussion — workload-specific explanations | CL-17, CL-18, CL-19, CL-20 | Three workload result groups | Admitted as interpretation of observed workloads, not a causal hardware result |
| Discussion — profiles change together | CL-04, CL-11 | Profile manifests and T2 | Mandatory confounding boundary retained |
| Discussion — long-output INT4 and long-input W8 observations | CL-15, CL-16, CL-18, CL-19 | Frozen size/RSS/speed evidence | Limited to the measured workload shapes; no routing threshold |
| Discussion — CMRC does not settle bookmark-task quality | CL-12, CL-13, CL-14, CL-27 | CMRC task definition and paired result | Admitted scope statement; failed heuristic remains visible |
| Reference implementation — path and public materials | CL-04, CL-05, CL-06, CL-08, CL-09, CL-23 | W8 Git/Hub materials | Admitted; no Apple acceptance or regression-fix claim |
| Reference implementation — community GPU and INT8 context | CL-24, CL-25 | Frozen community objects | Context only; no deficiency or superiority inference |
| Reproducibility — Git and Hub revisions | CL-22, CL-23 | Frozen public repositories | Admitted exact identifiers |
| Reproducibility — recipe and compiled-file hashes | CL-22, CL-23 | Hub manifests and checksum locks | Admitted exact identifiers |
| Reproducibility — deterministic pipeline and byte-identical Python-3 quality JSON | CL-12, CL-13, CL-23 | Source lock, generated provenance, tests | Admitted; no new model/device output |
| Reproducibility — dataset is reconstructed, not redistributed | CL-12, CL-27 | Official CMRC commit/hashes | Admitted dataset-boundary statement |
| Reproducibility — historical/public W8 identity distinction | CL-22 | Artifact identity registry | Exact historical replay requires the historical binary |
| Limitations — one device/toolchain scope | CL-08, CL-10, CL-11 | Device records | Admitted; universal compatibility rejected |
| Limitations — coupled profiles | CL-04, CL-11 | Profile manifests | Admitted; causal attribution rejected |
| Limitations — trace non-exclusivity | CL-09 | Trace summary | Mandatory qualification retained |
| Limitations — 300 examples, zero-crossing intervals, failed heuristic | CL-12, CL-13, CL-14 | Frozen quality evidence | Admitted; equivalence and full-task generalization rejected |
| Limitations — three measured timing samples | CL-17, CL-18, CL-19 | Frozen speed report | Admitted; P95 and universal cold-load ratio rejected |
| Limitations — historical/public W8 identity distinction | CL-22 | Artifact identity registry | Exact replay limitation retained |
| Conclusion — reproducible static route and measured ANE participation | CL-04, CL-05, CL-08, CL-09, CL-10 | Patch, runtime suites, trace, public validation | Admitted with device/version and participation wording |
| Conclusion — W8 fidelity and workload-dependent profile trade-off | CL-07, CL-15, CL-16, CL-17, CL-18, CL-19, CL-20 | Frozen quality, size, RSS, and speed evidence | Admitted; no universal winner or energy claim |

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
- substitution of the current public W8 rebuild for the historical A/B binary.

## Final disposition

Every factual or empirical sentence is either linked to an admitted claim ID,
presented as dated related-work context with a bibliographic source, or framed
as an explicit limitation. The manuscript is semantically inside Protocol v1.
It passed the locked build, claim checks, and page-level visual review on
2026-08-28. The claim IDs remain in the LaTeX source but are hidden in the
submission PDF.
