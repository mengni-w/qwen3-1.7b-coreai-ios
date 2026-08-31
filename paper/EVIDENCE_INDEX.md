# Evidence Index

## Qwen3-1.7B on iPhone with Apple Core AI

- **Index version:** 1.1
- **Audit date:** 2026-08-29
- **Governing protocols:** [`REPORT_PROTOCOL_V1.md`](REPORT_PROTOCOL_V1.md) and
  the post-review compatibility amendment in
  [`REPORT_PROTOCOL_V2.md`](REPORT_PROTOCOL_V2.md)
- **Purpose:** Claim-to-evidence control for the technical report

## 1. Operating rule

Every empirical sentence in the manuscript must cite an admitted claim ID from
this index. Every admitted claim must resolve to a versioned source and a
specific evidence object. Narrative summaries may explain a result, but they
cannot replace the primary evidence that establishes it.

This index does not authorize new experiments. Protocol v1 admits the
retrospective public evidence and deterministic reanalysis used for the main
study. Protocol v2 separately admits one completed post-review, load-only W8
compatibility diagnostic; it does not retroactively make that diagnostic part
of the original study design.

## 2. Evidence classes

| Class | Meaning | Permitted use |
| --- | --- | --- |
| `A` | Hash-identified compiled or source model artifact | Establish the exact payload to which a device or comparison result belongs |
| `O` | Official external state, frozen by commit or dated API object | Establish Apple repository, issue, and pull-request status |
| `R` | Raw measured output or per-example prediction | Primary empirical evidence |
| `D` | Machine-readable derived result with a disclosed procedure | Headline metrics, statistical estimates, and structured summaries |
| `M` | Frozen method, protocol, recipe, patch, or analysis code | Establish how evidence was produced |
| `N` | Human-readable narrative report with a verified hash | Interpretation and raw values when no separate structured file exists |
| `C` | Contextual or comparative source | Related work and non-headline context only |

Evidence strength is claim-specific. An official repository statement is
primary for official support status, while raw device output is primary for a
runtime measurement. A `N` source alone may support a published observation
only when its individual samples are present, the document is hash-locked, and
the limitation is disclosed.

## 3. Frozen source registry

### S-APPLE-MAIN — Apple `coreai-models`

- Class: `O`
- Repository: <https://github.com/apple/coreai-models>
- Audited commit:
  [`7062017c8e86c6cf4f49b721ddc3494efcdb7c7d`](https://github.com/apple/coreai-models/commit/7062017c8e86c6cf4f49b721ddc3494efcdb7c7d)
- Commit date: `2026-08-27T18:27:12Z`
- Qwen3 support table:
  <https://github.com/apple/coreai-models/blob/7062017c8e86c6cf4f49b721ddc3494efcdb7c7d/models/qwen3/README.md>
- Model registry:
  <https://github.com/apple/coreai-models/blob/7062017c8e86c6cf4f49b721ddc3494efcdb7c7d/python/src/coreai_models/model_registry.py>
- Relevant fact: the support table lists Qwen3-0.6B, Qwen3-4B, and Qwen3-8B;
  the registry contains no Qwen3-1.7B preset.
- Time boundary: this establishes repository state only at the audited commit.

### S-APPLE-ISSUE-116 — Official model request

- Class: `O`
- URL: <https://github.com/apple/coreai-models/issues/116>
- Title: `Add Qwen3-1.7B support for iOS`
- State at audit: `open`
- Created: `2026-07-19T07:42:48Z`
- Updated: `2026-08-26T00:43:22Z`
- Assignee at audit: `stikves`
- Use: establishes the public request and preserves the published contribution
  summary.
- Limit: an open issue is not acceptance, endorsement, or a roadmap promise.

### S-APPLE-PR-196 — Closed official implementation attempt

- Class: `O`
- URL: <https://github.com/apple/coreai-models/pull/196>
- Title: `Add Qwen3-1.7B iOS and macOS export support`
- State at audit: `closed`, `merged=false`
- Head commit: `f39347bcd64946ba32f8f74f3c7dcfdbad3106c6`
- PR description: proposed macOS INT4 and iOS mixed 4/8-bit palettized
  registration; reported float16 perplexity `20.96` and mixed-precision
  perplexity `21.19` at `5.43 BPW`.
- Maintainer regression comment:
  <https://github.com/apple/coreai-models/pull/196#issuecomment-5432991306>
- Comment date: `2026-08-27T01:05:46Z`
- Exact relevant statement: the maintainer reported a local iOS regression,
  moved toward macOS-only work, and said iOS would be followed up later.
- Limit: the comment reports a regression; it does not identify its technical
  cause and does not prove that all iOS approaches fail.

### S-W8-GIT — Static-path contribution repository

- Classes: `M`, `D`, `N`, `C`
- Repository: <https://github.com/massif-01/qwen3-1.7b-coreai-ios>
- Frozen commit:
  [`46668db811559ce21b0006f07706a6d0bde08656`](https://github.com/massif-01/qwen3-1.7b-coreai-ios/commit/46668db811559ce21b0006f07706a6d0bde08656)
- Commit date: `2026-07-19T08:41:02Z`
- License: BSD 3-Clause for original repository material; Apple-derived context
  retains Apple's license; model weights retain their upstream license.

Admitted objects and audited SHA-256 values:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `REPRODUCTION.md` | `M` | `06c555b647faf0934dd62be435b632dc534e01a976653af9a4cb72d177f2c9e2` |
| `RESULTS.md` | `N` | `77c5266e43f05a1257227da4e6d8b40bcbf11b1412862d18b113ae26c8eff3cf` |
| `RELATED_WORK.md` | `C` | `af0c431e172658c3b15ecc0316e9e76e3f90aad90b011d63716e5c5c1d9f1f0f` |
| `patches/qwen3-1.7b-coreai-main.patch` | `M` | `bc8f135d5637d629beac727e4d10b0b6e909ebcc77206c39c971d8967d4360d4` |
| `recipes/qwen3_1_7b_w8_per_tensor.yaml` | `M` | `dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72` |
| `results/artifact-summary.json` | `D` | `3fee177b437e677a8611a0bed1b3b522b79abb15778cff635aea4532d74d95de` |
| `results/device-runtime-summary.json` | `D` | `b714b1bf67541c4e4c200eb98eff83e36446df9819477a1be19d5bba0f19726d` |
| `results/quality-summary.json` | `D` | `b2e6e067b6ee68fd935143e131805179806ec034a8d69fe0b706118884fa72d4` |
| `results/upstream-validation.json` | `D` | `325b4bcb4dac20c9b656d83489863a5cdcb22c24c641d3d5ec12f6f179bac6a0` |

`results/quality-summary.json` is retained as historical evidence of the W4
and mixed-W4/W8 selection process. Its W8 tuning and holdout values are
superseded by S-FIDELITY-V2 and are not used for manuscript headline metrics.

### S-FIDELITY-V2 — Corrected formal authoring-model fidelity evaluation

- Classes: `M`, `R`, `D`
- Repository: <https://github.com/massif-01/qwen3-1.7b-coreai-ios>
- Evidence publication commit:
  [`c54a355d5696e914efa64213f50e98264589ef2e`](https://github.com/massif-01/qwen3-1.7b-coreai-ios/commit/c54a355d5696e914efa64213f50e98264589ef2e)
- Corrected run ID: `c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24`
- Status: 10/10 reference cases, 10/10 candidate cases, and 10/10
  comparisons completed successfully
- Evaluated representation: Apple iOS Qwen3 PyTorch authoring model with the
  published W8-plus-INT8 mechanism enabled; CPU execution with FP16 model
  logits and binary64 metric computation
- Limit: this evidence does not contain logits from a compiled `.aimodelc`, a
  downstream capability benchmark, or a device-performance measurement

Admitted objects and audited SHA-256 values:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `paper/EXPERIMENT_PROTOCOL_V1.md` | `M` | `b7d98264068aad19b950e96af04c52fa027e57afcf67062e06125c9a875cc6b2` |
| `paper/FIDELITY_V2_AMENDMENT_1.md` | `M` | `07eab8874485e8954ee959d611de302de122ad04c1e5c0fcca6f1e957ab368d3` |
| `paper/evidence/fidelity-v2/prompt-manifest.json` | `M` | `59eedc731dab284755a59fc60b548a034a2a657ed8c9998413d58419b5ac1a95` |
| `paper/evidence/fidelity-v2/environment.lock.json` | `M` | `c0f169ab66d52385d7d31456bbbdeb5e93103c5355b7510a87da61453d30ad47` |
| `paper/evidence/fidelity-v2/run_fidelity_v2.py` | `M` | `3f8d729bd42b22fa590562f17f6703a66fc6611cc3cf922379108116a6ddd82b` |
| `paper/evidence/fidelity-v2/attempts/c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24/PUBLIC_MANIFEST.sha256` | `M` | `52b1400d86bd0bcdc96239262653a9af30b6ed69bdc53708df9d449de66f40cb` |
| `paper/evidence/fidelity-v2/attempts/c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24/raw/aggregates.json` | `D` | `172e2218ba6e44d55a7efab5280a8bd2fa1703231a62811761e41539a59e9e0d` |
| `paper/evidence/fidelity-v2/attempts/c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24/raw/case-comparisons.jsonl` | `R` | `be19235ff92a84b4c3b52d9dc278b577f41fcb40355ed7ff4e4d7bfa4f61262f` |
| `results/fidelity-v2-summary.json` | `D` | `fa2ef349a04d26cdb09686f9eb53c925b9c72c68ca7a04b1f89bbc96fcdd6cca` |

### S-W8-COMPAT-2026-08 — Post-review W8 load compatibility diagnostic

- Classes: `A`, `D`, `M`
- Governing documents: [`REPORT_PROTOCOL_V2.md`](REPORT_PROTOCOL_V2.md) and
  [`W8_COMPATIBILITY_OBSERVATION_1.md`](W8_COMPATIBILITY_OBSERVATION_1.md)
- Device class: physical iPhone 15 Pro (`iPhone16,1`)
- Runtime: iOS 27.0 build `24A5424a`
- Application toolchain: Xcode build `27A5252f`; iPhoneOS SDK build
  `24A5422a`
- Evidence object: `results/w8-aot-compatibility-evidence.json`
- Evidence SHA-256:
  `baf1e717e445a56108350066cac983ad1cd0f0941af0467da7260bbc341ca68d`
- Public event-level evidence:
  `paper/evidence/w8-compatibility/sanitized-load-events.jsonl`
- Evidence form: manually sanitized structured extracts classified as `D`, not
  unsanitized raw captures; source digests identify the retained private
  originals but do not independently prove the extraction mapping
- Event evidence SHA-256:
  `2b3ee7024446cdf7aae01adefb616f74f641876fbf31807b1a2f94e0d294de1d`
- Event manifest SHA-256:
  `3c9c72d44f6e0878ac425a9c5e302fa3cd4648c35ed28fed25bd249a1c0fcfe5`
- Scope: two failed load-only invocations of the earlier public AOT. The second
  followed a full-reboot request and the same device's subsequent observed
  reconnection; one no-retry load-and-unload invocation of a current-toolchain
  candidate; two authoring exports using different output directories.
- Limit: this source contains no generation result, Instruments trace,
  cold-start benchmark, or controlled single-factor comparison across iOS or
  compiler versions.

Admitted objects and audited SHA-256 values:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `paper/REPORT_PROTOCOL_V2.md` | `M` | `b54284270c9f9fff14beadb8f5dca01d012b0585f887c0f6f30a729bc076587f` |
| `paper/W8_COMPATIBILITY_OBSERVATION_1.md` | `M` | `f5405f6adf8a2556f2ad95ee0291426dadd885e0de9f540f31e2d9f34dd67a79` |
| `results/w8-aot-compatibility-evidence.json` | `D` | `baf1e717e445a56108350066cac983ad1cd0f0941af0467da7260bbc341ca68d` |
| `paper/evidence/w8-compatibility/sanitized-load-events.jsonl` | `D` | `2b3ee7024446cdf7aae01adefb616f74f641876fbf31807b1a2f94e0d294de1d` |
| `paper/evidence/w8-compatibility/README.md` | `M` | `81b6d1bdc1689eae24c0e6f9db4c5e5a624d246042cde0f752d77dc8fd1c84b7` |
| `paper/evidence/w8-compatibility/MANIFEST.sha256` | `M` | `3c9c72d44f6e0878ac425a9c5e302fa3cd4648c35ed28fed25bd249a1c0fcfe5` |

### S-W8-HF — Public W8/ANE resource directory

- Classes: `A`, `D`, `N`
- Repository:
  <https://huggingface.co/massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p>
- Frozen Hub revision: `466ebe2e5cec125fa113ea71503add41bba581a8`
- Created: `2026-07-19T08:38:53Z`
- Last modified: `2026-07-19T08:44:12Z`
- Access at audit: public, ungated, enabled
- Compiled `main-h16p.mlirb` SHA-256:
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`
- Public authoring `main.mlirb` identity recorded by the AOT metadata:
  `5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73`
- Use: downloadable public artifact and exact-public-artifact six-case device
  validation.
- Limit: this public rebuild is not byte-identical to the W8 artifact used in
  the historical paired A/B run.
- Current model-card revision:
  `be6b5aad19e18bb71be3199eadceb27db7e69724`; this privacy-only amendment
  removes a local device nickname and leaves the frozen payload and admitted
  validation object unchanged.

Admitted evidence objects at the frozen Hub revision:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `evidence/artifact-summary.json` | `D` | `3fee177b437e677a8611a0bed1b3b522b79abb15778cff635aea4532d74d95de` |
| `evidence/device-runtime-summary.json` | `D` | `b714b1bf67541c4e4c200eb98eff83e36446df9819477a1be19d5bba0f19726d` |
| `evidence/public-release-device-validation.json` | `R`, `D` | `1a8f49375c0d1334ad3c2af9718610746ad53bdc4687fcc720a1650755b5c0e0` |
| `evidence/quality-summary.json` | `D` | `b2e6e067b6ee68fd935143e131805179806ec034a8d69fe0b706118884fa72d4` |
| `evidence/upstream-validation.json` | `D` | `325b4bcb4dac20c9b656d83489863a5cdcb22c24c641d3d5ec12f6f179bac6a0` |

### S-COMP-GIT — Paired comparison and reproduction repository

- Classes: `R`, `D`, `M`, `N`
- Repository:
  <https://github.com/massif-01/qwen3-1.7b-coreai-reproduction>
- Frozen commit:
  [`34a4c08a9282bd076b8b5fe154c5507e6a8b3774`](https://github.com/massif-01/qwen3-1.7b-coreai-reproduction/commit/34a4c08a9282bd076b8b5fe154c5507e6a8b3774)
- Commit date: `2026-07-20T20:05:16Z`
- Repository audit on `2026-08-28`: integrity verified across 38 files; all
  three published-metric tests passed.

Admitted objects and audited SHA-256 values:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `docs/quality-protocol.md` | `M` | `75d0f6562f4df31ef67e14d59e1c7e92f14d6a04e01488a422772e9949611ef6` |
| `docs/quality-result.md` | `N` | `a292d52139b6ec8b26986195cf7eae3547e97cdff744aa3bd901e2df6c90b813` |
| `docs/speed-protocol.md` | `M` | `8c5fe9400efbc4c968a50eca92fb54d5752a8f26779fbeb00ddd7dab70773b12` |
| `docs/speed-result.md` | `R`, `N` | `a9eb6c8075537d5c5bd9ff1af9f59170da7727714c8da049402d3ae7d313c3ee` |
| `docs/feasibility-result-source.md` | `N` | `62249f2d8a45888919756eabaf0b1b3bc8ec1ea596d0325a136b429f4a3cab85` |
| `docs/artifact-provenance.md` | `M` | `7a49ec10b296157ce246815b584427d2d5c695bf74febab406ff069b9d303eb8` |
| `benchmarks/results/artifact-summary.json` | `D` | `2c50cec391f72d98a09c65c20fe8fab1c35a8843abf10c5a9b28886a97cf6239` |
| `benchmarks/results/quality-comparison.json` | `D` | `47bae909fdac3e80996b4042daff173931dec306c6f8a9977189792f4effa171` |
| `benchmarks/results/raw/w8-ane-no-thinking-results.jsonl` | `R` | `772fa31dbd4f6c1b5c668636fcea8d6bef1f04234b7ddde57cae477ebf86cfbe` |
| `benchmarks/results/raw/int4-gpu-no-thinking-results.jsonl` | `R` | `18bc453cadd0b9c20e18ae016752a74f52de20ddc32aeda2ff5f2fcc5d00983f` |
| `benchmarks/results/raw/SHA256SUMS` | `M` | `550860878a19bba43a9d2d60c341b5d6294902a1a42f07cd1c4ee0d6d43089c5` |
| `benchmarks/tools/score_frozen_cmrc_py3.py` | `M` | `e89ce35f5f16671831ffb412b9194a60ee83b1ac4ba62b9d49b7d81c090cf4c9` |
| `runtime/NO_THINKING.md` | `M` | `872bc5bdabb6b8003897097dda58572e9515c702b20758d6632b637674719856` |
| `runtime/coreai-models-enable-no-thinking.patch` | `M` | `a881e3f7239a178553eb635b7a9339f2ca751cb4b8d835c85ebe451c4c8192b9` |

`docs/speed-result.md` is admitted as both raw and narrative evidence because
it contains the individual accepted timing samples and exclusions, is locked
by SHA-256, and has no separate raw timing JSON. Manuscript tables must be
generated by a deterministic extractor from this exact document; manual
transcription is prohibited.

### S-INT4-HF — Public INT4/GPU resource directory

- Classes: `A`, `D`, `M`, `N`
- Repository:
  <https://huggingface.co/massif/Qwen3-1.7B-CoreAI-GPU-INT4-4K-h16p>
- Frozen Hub revision: `c32b6342c98e5e23363f692e614bccca37f24234`
- Created: `2026-07-20T18:54:05Z`
- Last modified: `2026-07-20T19:37:15Z`
- Access at audit: public, ungated, enabled
- Compiled `main-h16p.mlirb` SHA-256:
  `ad953b6bc902accc1f1200a8870012c5dec6b488f0f4ec0f10a9916b16cb56ef`
- `resources.bin` SHA-256:
  `37c7f2fcf85625abb32d83ca24e7a9facd33a37f79dbc3afec64d41eb900f8bc`
- Use: exact public INT4/GPU artifact used in the paired comparison.
- Provenance note: the original comparison document pinned revision
  `cb25b3226ee679ee92d0e5af7467d579a6bff66a`. The frozen revision above is a
  documentation-only successor with identical compiled payload hashes.

Admitted evidence objects at the frozen Hub revision:

| Object | Class | SHA-256 |
| --- | --- | --- |
| `evidence/FEASIBILITY_RESULT.md` | `N` | `e26c76f1f9d293194e763a15d18d83df690dc53144f96b9878ed4ce48361544d` |
| `evidence/QUALITY_BENCHMARK_PROTOCOL.md` | `M` | `0d1ca650a76384efd0282ff6f7691b90b965ddd78a2265c047423adacac8c07d` |
| `evidence/QUALITY_COMPARISON.md` | `N` | `747e36d381807fc3d7efeaa9d810de739e83ac876f6138a340c1fe3fd625469b` |
| `evidence/QUALITY_COMPARISON.zh-CN.md` | `N` | `16c5ecf12bdde4ed89ad31bf0bc194c36371044411db15da3d397b9d083e97ff` |
| `evidence/SPEED_BENCHMARK_PROTOCOL.md` | `M` | `564c00ab521497d3f29edc8fa731a029d65622123f8caaeb79c6d9d9eee4b4de` |
| `evidence/SPEED_BENCHMARK_RESULT.md` | `N` | `f89d82c680bda3534779d28d9ff322f84a16845658271fd2a5674de89791963d` |
| `evidence/artifact-summary.json` | `D` | `2c50cec391f72d98a09c65c20fe8fab1c35a8843abf10c5a9b28886a97cf6239` |
| `evidence/quality-comparison.json` | `D` | `47bae909fdac3e80996b4042daff173931dec306c6f8a9977189792f4effa171` |

### S-PUBLIC-STATUS-V1 — Dated public-source audit lock

- Classes: `O`, `C`, `M`
- Object: `analysis/public-status-v1.json`
- Audit timestamp: `2026-08-28T09:07:26Z`
- SHA-256:
  `12b0ed2caf30e1f75e109bac404b8106d5b26ff6242d51588e7dd7fb10595f69`
- Use: normalized source for Table T1 and the related-work statements below.
- Boundary: this is a dated public-source review, not a new model evaluation.

Admitted public objects:

| Object | Revision / date | SHA-256 |
| --- | --- | --- |
| Apple Qwen3 README | `7062017c`, 2026-08-27 | `04724d8086b3c64fc0e46fd59caac175c74c732fbae527b70e3eaabe9ab39a6e` |
| Apple model registry | `7062017c`, 2026-08-27 | `aa4aaa268d96d5b30fd00c4f35e65a7851ada92cad26275fb75b95fc0ff66761` |
| `mlboydaisuke` model card | `af6335a8a108e383be8aa44925a8fe03a1cd2cd9` | `9c497a9d9aee41f5dca34694a689a2395cee379cdce4ed00c5ccfea464c84321` |
| `kevinqz` model card | `340f4c4c8c422c56e0cc9b5ecb7eabdf37781f54` | `de79c3cb9daf4d3be71c353e95846749297ec802136933c159a8d78dda7ac5e8` |
| `kevinqz` parity report | `340f4c4c8c422c56e0cc9b5ecb7eabdf37781f54` | `561bea7469d09b3df76474d8aa021debe5e23912ec5ac90b07e994bccfd318f0` |
| `kevinqz` reproduction manifest | `340f4c4c8c422c56e0cc9b5ecb7eabdf37781f54` | `e58dd90d9ebbea4df534475359e5427c6bc3caa036849ea69cc6aaa572f5c8ab` |

### S-CONTEXT — Background literature and official documentation

- Classes: `C`, `O`
- Qwen3 technical report: arXiv `2505.09388v1`.
- Frozen base model: `Qwen/Qwen3-1.7B` revision
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`.
- CMRC2018 paper: ACL Anthology `D19-1600`, DOI
  `10.18653/v1/D19-1600`.
- CMRC source: `ymcui/cmrc2018` commit
  `c0eb1b6ba219847457e6af3180da722bbeb656af`, development-source SHA-256
  `5cfe4414c28a8ecbb51670f78c0dc7d1049f286c2d5769b52f1f94bcc0752cf1`.
- Apple Core AI Models root README and Apple public Neural Engine and
  palettization documentation, accessed 2026-08-28.
- Use: contextual background only; report findings still require a numbered
  claim below.

## 4. Artifact identity registry

### A-W8-HISTORICAL

- Role: W8 side of the paired quality, speed, size, and memory comparison
- Authoring `main.mlirb` identity recorded by the AOT metadata:
  `66325b4cc0657e1f89a7a0a92f37899d01ddc37d168295dbbad0d71bef7f75e3`
- Compiled main SHA-256:
  `0c2dfcfeaae195386f1e61c05e0cf2b4a1ce6ecda1c321803afc0019b1d886d7`
- Configuration: W8 per-tensor projections, separately quantized tied
  embedding, FP16 compute, fixed FP16 KV, 4,096-token context, `h16p`, Neural
  Engine preferred
- Evidence scope: historical A/B results, four six-case suites, trace summary
- Distribution: the exact compiled payload is not the current public payload

### A-W8-PUBLIC

- Role: W8/ANE artifact published in July 2026 and used for the separately
  recorded six-case public-artifact suite
- Authoring `main.mlirb` identity recorded by the AOT metadata:
  `5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73`
- Compiled main SHA-256:
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`
- Configuration: same frozen W8 mechanism as A-W8-HISTORICAL
- Evidence scope: exact-public-artifact six-case physical-device validation
- Boundary: not byte-identical to A-W8-HISTORICAL; its earlier six-case record
  does not establish compatibility with every later Core AI runtime

### A-W8-CURRENT-CANDIDATE

- Role: post-review current-toolchain compatibility candidate
- Authoring `main.mlirb` identity:
  `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c`
- Compiled main SHA-256:
  `09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`
- Complete AOT file-list fingerprint:
  `182336f4654bb735bcad35e45f7832756c34469931ad96d872532dca727ebd8d`
- Load-record artifact-manifest SHA-256:
  `cca1e77d41e6f157e10f89e1f05c51e96966be92e7590e550e844e4178c09581`
- Producer: `coreai-build-3600.83.1`
- Configuration: same frozen W8 recipe and pinned base-model revision, with a
  separately identified authoring export and AOT result
- Evidence scope: one load-and-immediate-unload observation only
- Distribution boundary: this index does not assign a public Hub revision
  until an exact uploaded commit has been verified
- Claim boundary: no generation, quality, speed-comparison, cold-start, or ANE
  trace result is attached to this candidate

### A-INT4-PUBLIC

- Role: INT4 side of the paired comparison and currently downloadable artifact
- Source hash:
  `C0E3A7463B722AE6740DE3CFDFA835B06451436567663BDD79F2C8E996794CD6`
- Compiled main SHA-256:
  `ad953b6bc902accc1f1200a8870012c5dec6b488f0f4ec0f10a9916b16cb56ef`
- Configuration: block-32 INT4, FP16 compute, growing FP16 KV, 4,096-token
  context, `h16p`, GPU preferred
- Evidence scope: feasibility, paired quality, speed, size, and memory

## 5. Claim-to-evidence ledger

### CL-01 — Apple support-matrix gap

- Status: `READY`
- Admitted wording: “At Apple `coreai-models` commit `7062017…`, the published
  Qwen3 support table and model registry did not include Qwen3-1.7B.”
- Evidence: S-APPLE-MAIN Qwen3 README and model registry
- Required qualifier: include the audit date or exact commit
- Forbidden inference: “Apple Core AI cannot run Qwen3-1.7B.”

### CL-02 — Apple iOS implementation attempt was not merged

- Status: `READY WITH QUALIFICATION`
- Admitted wording: “PR #196 proposed Qwen3-1.7B for macOS and iOS, but was
  closed without merge after the maintainer reported a local iOS regression.”
- Evidence: S-APPLE-PR-196 PR state, body, and regression comment
- Required qualifier: the regression's root cause was not disclosed
- Forbidden inference: our W8 approach directly fixes PR #196's unknown defect

### CL-03 — Shared upstream model identity

- Status: `READY`
- Admitted wording: “Both compared profiles derive from the same
  Qwen/Qwen3-1.7B revision and publish the same tokenizer hash.”
- Evidence: S-W8-GIT `results/artifact-summary.json`; S-COMP-GIT
  `benchmarks/results/artifact-summary.json`
- Frozen base revision:
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Frozen tokenizer SHA-256:
  `aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4`

### CL-04 — W8 static deployment definition

- Status: `READY`
- Admitted wording: “The W8 profile uses per-tensor K-means-palettized
  transformer projections, a separately quantized tied embedding, FP16
  compute, fixed FP16 KV, a 4,096-token context, and Neural Engine-preferred
  `h16p` AOT.”
- Evidence: S-W8-GIT recipe, `results/artifact-summary.json`, and
  `results/device-runtime-summary.json`
- Forbidden shorthand: describe this mechanism as generic INT8, GPTQ, W4A16,
  or exclusive-ANE execution

### CL-05 — Reproducible Apple-main onboarding

- Status: `READY WITH VERSION BOUNDARY`
- Admitted wording: “The reference patch applied cleanly to Apple main commit
  `04a3fd6…`; 28 focused tests passed, 42 related iOS conversion tests
  collected without errors, Ruff passed, and the dry-run resolved the frozen
  W8 configuration.”
- Evidence: S-W8-GIT `results/upstream-validation.json`, patch, recipe, and
  `REPRODUCTION.md`; S-W8-COMPAT-2026-08 for the later export and AOT record
- Additional admitted wording: “A post-review run subsequently repeated the
  full export and AOT compilation at the same pinned Apple commit using Xcode
  27 Beta 6.”
- Required qualifier: the later output is a separately identified artifact;
  it does not retroactively replace the historical A/B binary or the earlier
  public rebuild
- Forbidden inference: the 2026-07 patch necessarily applies to Apple current
  main without a fresh compatibility check

### CL-06 — W8 quality-first selection

- Status: `READY`
- Admitted wording: “Uniform W4 and mixed W4/W8 candidates were rejected under
  the frozen conversion-fidelity contract before the W8 holdout result was
  admitted.”
- Evidence: S-W8-GIT `results/quality-summary.json` and `RESULTS.md`
- Limit: representative rejected mean-cosine range is reported; complete
  candidate-level raw logits are not distributed in the paper repository
- Supersession boundary: the historical file supports the selection sequence
  and rejected-candidate range only; its W8 tuning and holdout values are not
  admitted as current fidelity results

### CL-07 — W8 frozen-holdout fidelity

- Status: `READY`
- Corrected formal run: `c5ac8729-efb6-4a7f-bf39-5ffa13cdfb24`
- Tuning values: mean cosine `0.9972995580522954`, minimum cosine
  `0.9634192756433698`, top-1 agreement `0.9895833333333334`, mean NLL delta
  `0.0041901005215974`
- Holdout values: mean cosine `0.9968972864500013`, minimum cosine
  `0.953391227144109`, top-1 agreement `0.9696691176470589`, mean NLL delta
  `0.008879966197800114`
- Evidence: S-FIDELITY-V2 `results/fidelity-v2-summary.json`, sealed aggregate,
  case comparisons, protocol, and prospective amendment
- Interpretation: authoring-model fidelity to the uncompressed reference under
  ten frozen inputs; case-level arithmetic macro, candidate-minus-reference NLL
- Forbidden inference: general language capability, benchmark superiority, or
  downstream equivalence
- Additional forbidden inference: compiled-device logit fidelity

### CL-08 — Historical W8 physical-device suite

- Status: `READY WITH ARTIFACT IDENTITY`
- Admitted wording: “A-W8-HISTORICAL completed four six-case suites on iPhone
  15 Pro / iOS 27 with zero recorded hard failures.”
- Evidence: S-W8-GIT `results/device-runtime-summary.json` and `RESULTS.md`
- Admitted final values: peak RSS `2,963.7 MiB`; RSS after unload
  `198.7 MiB`; long-context input `3,790` tokens; TTFT `5.627 s`
- Required qualifier: these measurements belong to A-W8-HISTORICAL

### CL-09 — Apple Neural Engine participation

- Status: `READY WITH NON-EXCLUSIVITY QUALIFIER`
- Admitted wording: “The recorded Core AI trace contained 547 MPSGraph program
  intervals matched by 547 Apple Neural Engine Prediction intervals, supporting
  ANE participation in the traced inference program.”
- Evidence: S-W8-GIT `results/device-runtime-summary.json` → `execution_trace`
- Required qualifier: no exclusive-ANE claim
- Limit: the public repository distributes the sanitized trace summary, not the
  original trace bundle

### CL-10 — Exact public W8 artifact validation

- Status: `READY`
- Admitted wording: “The exact public W8 rebuild A-W8-PUBLIC separately passed
  a six-case device suite in the earlier recorded iPhone 15 Pro / iOS 27
  environment.”
- Evidence: S-W8-HF `evidence/public-release-device-validation.json`
- Admitted values: six of six cases, fresh load `46.176 s`, structured-output
  TTFT `1.213 s`, long-context TTFT `5.709 s`, peak RSS `2,766.4 MiB`, RSS
  after unload `197.3 MiB`
- Required qualifier: this was a single public-artifact validation suite, not
  the historical A/B series, and it does not imply compatibility with every
  later Core AI runtime

### CL-11 — INT4 dynamic GPU route

- Status: `READY`
- Admitted wording: “A-INT4-PUBLIC uses block-32 INT4 weights, FP16 compute,
  growing FP16 KV, a dynamic graph, GPU-preferred AOT, and selected the
  `coreai-pipelined` route on iPhone 15 Pro.”
- Evidence: S-COMP-GIT `benchmarks/results/artifact-summary.json` and
  `docs/feasibility-result-source.md`; S-INT4-HF evidence
- Limit: GPU-preferred and observed GPU route do not imply exclusive GPU use
  for every operation

### CL-12 — Paired quality controls

- Status: `READY`
- Admitted wording: “The paired quality comparison used a frozen 300-example
  CMRC2018 validation subset with 100 unique-context examples in each of the
  short, medium, and long strata; both variants used the same tokenizer,
  template, prompts, order, 128-token budget, temperature zero, and fresh
  sessions.”
- Evidence: S-COMP-GIT `docs/quality-protocol.md`; frozen sample SHA recorded in
  `benchmarks/results/artifact-summary.json`
- Frozen sample SHA-256:
  `9fb9d896c96fc2ef0fa9961a5b65d2ac5b8bd09744f717a0a0ecb9f6c9fe05ff`
- Limit: the dataset text is not redistributed; scoring parity with the
  original Python 2 environment is not claimed byte-for-byte

### CL-13 — Paired CMRC2018 headline metrics

- Status: `READY`
- Admitted values: W8 EM `59.33`, W8 F1 `81.70`, INT4 EM `57.67`, INT4 F1
  `81.42`, identical predictions `187/300`
- Primary evidence: S-COMP-GIT two raw JSONL files (`R`)
- Derived evidence: `benchmarks/results/quality-comparison.json` (`D`)
- Verification: repository metric tests passed at audit
- Required qualifier: 300-example frozen subset, not the full validation split

### CL-14 — Paired uncertainty and test results

- Status: `READY`
- Admitted values:
  - W8-minus-INT4 F1 `+0.2804`, 95% bootstrap interval
    `[-2.4442, +2.9989]`, 10,000 resamples, sign-test `p=0.6137`;
  - W8-minus-INT4 EM `+1.6667`, 95% bootstrap interval
    `[-3.0000, +6.3333]`, 10,000 resamples, sign-test `p=0.5758`.
- Evidence: S-COMP-GIT `benchmarks/results/quality-comparison.json` and scorer
- Admitted interpretation: no statistically detectable difference in this run
- Mandatory companion statement: the run also does not establish equivalence

### CL-15 — Bundle-size comparison

- Status: `READY`
- Admitted values: W8 `1,714.4 MiB`; INT4 `924.6 MiB`; INT4 lower by
  `789.8 MiB` / `46.1%`
- Evidence: S-COMP-GIT `docs/speed-result.md`; artifact manifests
- Required qualifier: compiled resource-directory logical size for the two
  compared artifacts

### CL-16 — Peak process RSS comparison

- Status: `READY WITH MEASUREMENT-SEMANTICS QUALIFIER`
- Admitted values: W8 `2,865.0 MiB`; INT4 `1,995.3 MiB`; INT4 lower by
  `869.7 MiB` / `30.4%`
- Evidence: S-COMP-GIT `docs/speed-result.md`
- Required qualifier: peak process resident memory under the disclosed device
  benchmark, not total system RAM or a universal device requirement

### CL-17 — Short structured workload

- Status: `READY`
- Workload: 161 input / 60 output tokens
- Admitted medians:
  - W8 TTFT `0.431 s`, total `3.259 s`, visible decode `20.505 tok/s`;
  - INT4 TTFT `1.221 s`, total `2.592 s`, visible decode `43.162 tok/s`.
- Evidence: S-COMP-GIT `docs/speed-result.md`, individual three-sample table
- Interpretation: W8 first token was faster; INT4 completed the total workload
  sooner and decoded faster
- Limit: three accepted measured samples after one warm-up; no P95 claim

### CL-18 — Near-4K prefill workload

- Status: `READY`
- Workload: 3,790 input / 10 output tokens
- Admitted medians:
  - W8 TTFT `5.647 s`, total `6.116 s`;
  - INT4 TTFT `13.522 s`, total `13.717 s`.
- Evidence: S-COMP-GIT `docs/speed-result.md`, individual three-sample table
- Interpretation: W8 was faster for this long-prompt, short-output workload
- Required qualifier: near-4K decode rate is not decision-grade because only
  nine visible decode tokens remained after excluding one reasoning token

### CL-19 — Sustained decode workload

- Status: `READY`
- Workload: 120 input / 256 output tokens
- Admitted medians:
  - W8 total `13.292 s`, visible decode `19.615 tok/s`;
  - INT4 total `7.159 s`, visible decode `38.487 tok/s`.
- Evidence: S-COMP-GIT `docs/speed-result.md`, individual three-sample table
- Required disclosure: one short W8 attempt was retained as model behavior,
  excluded under the frozen protocol, and replaced
- Limit: the 256-token cap intentionally measures sustained throughput, not
  answer quality

### CL-20 — Workload-dependent performance conclusion

- Status: `READY`
- Admitted wording: “The comparison produced no universal performance winner:
  INT4/GPU used less storage and peak RSS and decoded faster, whereas W8/ANE
  produced a faster first token and substantially faster near-4K prefill.”
- Evidence: CL-15 through CL-19
- Forbidden inference: ANE is inherently faster or more energy efficient than
  GPU; INT4 is inherently faster than W8

### CL-21 — No-thinking runtime control

- Status: `READY`
- Admitted wording: “For the pinned runtime, no-thinking mode was applied at
  chat-template time with `enable_thinking=false`; a `/no_think` prompt suffix
  was not treated as equivalent.”
- Evidence: S-COMP-GIT runtime patch, `runtime/NO_THINKING.md`, and quality
  protocol
- Limit: the patch is benchmark-specific and not proposed as a global product
  policy

### CL-22 — Historical/public W8 provenance boundary

- Status: `MANDATORY DISCLOSURE`
- Required wording: “The historical A/B payload, the July 2026 public rebuild,
  and the current-toolchain candidate are separate artifact identities. The
  public rebuild and candidate use the frozen W8 mechanism but neither may be
  silently substituted for the historical binary.”
- Evidence: A-W8-HISTORICAL, A-W8-PUBLIC, A-W8-CURRENT-CANDIDATE, S-W8-GIT,
  S-W8-HF, S-W8-COMPAT-2026-08, S-COMP-GIT
- Placement: Methods, Reproducibility, and Limitations
- Forbidden action: silently substitute A-W8-PUBLIC for A-W8-HISTORICAL in A/B
  claims, or attach the candidate's load result to either earlier artifact

### CL-23 — Public reproducibility materials exist

- Status: `READY WITH BOUNDARIES`
- Admitted wording: “The public release includes model artifacts, locked
  recipes or conversion scripts, benchmark applications, scoring tools,
  per-example quality predictions, checksums, and integration guidance.”
- Evidence: S-W8-GIT, S-W8-HF, S-COMP-GIT, S-INT4-HF
- Required qualifier: exact third-party reproduction of the historical W8 A/B
  binary is not available from the current public W8 payload

### CL-24 — Community dynamic INT4/GPU artifact context

- Status: `READY AS CONTEXT`
- Admitted wording: “At frozen revision `af6335a8…`, the community
  `mlboydaisuke` model card reports a dynamic INT4 GPU `h18p` bundle and iPhone
  17 Pro measurements.”
- Evidence: S-PUBLIC-STATUS-V1 model card snapshot
- Required qualifier: community artifact, not Apple-published or endorsed;
  different device and protocol; model-card measurements were not re-run here
- Forbidden inference: direct performance or quality superiority relative to
  this report's same-device profiles

### CL-25 — Community stateful INT8 artifact context

- Status: `READY AS CONTEXT`
- Admitted wording: “At frozen revision `340f4c4c…`, the community `kevinqz`
  repository publishes a stateful INT8 `.aimodel`; its reproduction manifest
  records the macOS export path and its numeric accuracy gate is `not_run`.”
- Evidence: S-PUBLIC-STATUS-V1 model card, parity report, and reproduction
  manifest snapshots
- Required qualifier: no directly comparable iPhone AOT, timing, or quality
  result is admitted

### CL-26 — Apple public authoring and contribution-policy context

- Status: `READY AS CONTEXT`
- Admitted wording: “At the audited commit, Apple's `coreai-models` root README
  describes export recipes, authoring primitives, Swift runtime utilities,
  version-27 requirements, and a launch policy that does not accept code pull
  requests.”
- Evidence: S-APPLE-MAIN root README at commit `7062017c…`
- Required qualifier: repository state at the audit date; the reference patch
  in this report is not an accepted Apple contribution

### CL-27 — CMRC2018 source and task boundary

- Status: `READY AS CONTEXT`
- Admitted wording: “CMRC2018 is a Chinese span-extraction reading-comprehension
  dataset; this report reconstructs its frozen 300-example validation subset
  from the exact official source commit and hash.”
- Evidence: S-CONTEXT CMRC paper and repository; CL-12 frozen sample controls;
  `analysis/source-lock.json`
- Required qualifier: it does not directly measure summarization,
  classification, safety, or a product bookmark-analysis contract

### CL-28 — Current-runtime W8 load compatibility observation

- Status: `READY WITH CAUSAL BOUNDARY`
- Admitted wording: “On iOS 27 build `24A5424a`, A-W8-PUBLIC stopped during
  `ANECCompileOffline` in two load-only invocations. The second followed a full
  reboot request and the same device's subsequent observed reconnection;
  A-W8-CURRENT-CANDIDATE completed one load in `41.932 s`, reached `2,737.0 MiB`
  peak process RSS, unloaded, and exited normally.”
- Evidence: S-W8-COMPAT-2026-08 and A-W8-CURRENT-CANDIDATE
- Required qualifier: both the exported bytes and compiler producer changed,
  so the contrast does not isolate an iOS, compiler, artifact, or memory cause
- Additional boundary: no generation or Instruments trace was performed; the
  load duration is not a generation-speed result or cold-start benchmark
- Reboot boundary: the host command timed out while waiting for the device;
  neither a boot-session identifier nor device uptime was captured

### CL-29 — Authoring export byte identity

- Status: `READY WITH SEMANTIC BOUNDARY`
- Admitted wording: “Two exports made from the same locked inputs and recipe,
  differing only in output directory, produced different authoring `main.mlirb`
  SHA-256 digests: `13ba3f73…eda2c` and `12349a9a…c946`; their sizes differed by
  four bytes.”
- Evidence: S-W8-COMPAT-2026-08 repeated-authoring-export record
- Interpretation: every export is assigned its own artifact identity
- Forbidden inference: byte inequality establishes a recipe, weight,
  graph-structure, numerical-fidelity, or generation-quality difference

## 6. Non-admitted claims

The following claims are not supported by Protocol v1 or v2 and must not
appear as findings:

- first Qwen3-1.7B Core AI conversion of any kind;
- first Qwen3-1.7B model on Apple Silicon;
- exclusive ANE execution;
- causal proof that ANE beats GPU or W8 beats INT4;
- numerical energy, battery, or joules-per-token advantage;
- full WikiText-2 perplexity comparison;
- quality parity, equivalence, or non-inferiority between W8 and INT4;
- universal iPhone compatibility;
- production background-execution reliability as a paper result;
- Apple acceptance, adoption, endorsement, or commitment to merge;
- a technical explanation for Apple PR #196's regression;
- a causal claim that an iOS upgrade caused the current old-AOT failures;
- a causal claim that `coreai-build-3600.83.1` fixed a compiler defect;
- a claim that A-W8-CURRENT-CANDIDATE has passed generation or an ANE trace;
- a claim that its `41.932 s` load is a cold-start benchmark;
- path-independent byte reproducibility from the two-run export check.

A carefully dated novelty statement may describe this work as a reproducible,
high-fidelity static iOS onboarding with measured ANE participation, provided
the related-work audit is refreshed immediately before submission.

## 7. Table evidence map

| Table | Content | Source path | Claim IDs | Generation rule |
| --- | --- | --- | --- | --- |
| T1 | Apple and related public status | S-APPLE-MAIN, S-APPLE-ISSUE-116, S-APPLE-PR-196, refreshed related-work audit | CL-01, CL-02 | Date-stamped script/API snapshot plus manual source review |
| T2 | Profile definitions | W8 and INT4 artifact summaries | CL-03, CL-04, CL-11 | Generate from normalized manifest JSON |
| T3 | W8 fidelity | `results/fidelity-v2-summary.json`; historical selection fields from `results/quality-summary.json` | CL-06, CL-07 | Generate metrics from fidelity-v2 JSON; retain the older file only for selection history |
| T4 | W8 device and trace evidence | `results/device-runtime-summary.json`; public-release validation JSON | CL-08, CL-09, CL-10 | Generate directly from JSON; keep artifact identity column |
| T5 | Paired CMRC quality and uncertainty | raw JSONL, scorer, `quality-comparison.json` | CL-12–CL-14 | Recompute from raw files; compare byte-for-byte with published JSON |
| T6 | Bundle size and RSS | artifact manifests and fixed-hash speed report | CL-15, CL-16 | Parse source values into normalized JSON; never hand-copy into manuscript |
| T7 | Workload latency and throughput | fixed-hash `docs/speed-result.md` | CL-17–CL-20 | Deterministically extract all accepted sample rows, then derive medians |
| T8 | Post-review W8 load compatibility | `results/w8-aot-compatibility-evidence.json` | CL-28, CL-29 | Generate from the hash-locked load-only and repeated-export records; preserve the causal boundary |

## 8. Figure evidence map

| Figure | Content | Source | Claim IDs | Boundary |
| --- | --- | --- | --- | --- |
| F1 | Static authoring-to-device pipeline | patch, recipe, `REPRODUCTION.md`, artifact summary | CL-04, CL-05 | Architecture diagram, not a measured result |
| F2 | Static fixed-KV and dynamic growing-KV profiles | W8 and INT4 artifact manifests | CL-04, CL-11 | Show coupled profile differences; do not imply isolated causality |
| F3 | Paired quality differences and confidence intervals | `quality-comparison.json` | CL-13, CL-14 | Include zero line and “not equivalence” caption |
| F4 | Workload-specific latency | extracted speed samples | CL-17–CL-20 | Show individual samples and medians; no P95 |
| F5 | Bundle size and peak RSS | normalized T6 source data | CL-15, CL-16 | Use separate units and identify process RSS semantics |

## 9. Verification ledger

Completed during the evidence audit:

- [x] Apple current-main commit resolved and support table inspected.
- [x] Issue #116 state and metadata checked through GitHub API.
- [x] PR #196 merge state, body, and regression comment checked.
- [x] W8 and comparison GitHub repository commits frozen.
- [x] W8 and INT4 Hugging Face revisions and public access checked.
- [x] Both frozen GitHub repositories fetched into a disposable audit
  workspace at the recorded commits.
- [x] Hub evidence-only snapshots fetched at the recorded revisions; admitted
  evidence files matched the repositories' published SHA-256 manifests.
- [x] Comparison repository integrity verifier passed across 38 files.
- [x] Three published-metric repository tests passed.
- [x] W8 repository `CHECKSUMS.sha256` verified for all tracked evidence files.
- [x] Every evidence-object SHA-256 value recorded in this index reverified
  against the frozen source.

Required before manuscript numbers are frozen:

- [x] Rebuilt the exact CMRC reference sample and reran published quality
  scoring against the existing raw predictions; the output was byte-identical
  to the published quality JSON.
- [x] Wrote and tested a deterministic extractor for the fixed-hash speed
  report; all accepted sample rows and disclosed exclusions were retained.
- [x] Generated normalized, machine-readable inputs for Tables T2–T8.
- [x] Generated Figures F3–F5 from the normalized inputs and visually inspected
  the rendered SVGs.
- [x] Refreshed Apple and related-work status on 2026-08-28 and froze the
  reviewed public objects in `analysis/public-status-v1.json`.
- [x] Ran the final sentence-level claim audit recorded in
  `manuscript/CLAIM_AUDIT.md`; the mechanical audit also passed.

The Protocol v1 reconstruction pipeline performs no model inference or device
measurement. The separately labeled Protocol v2 compatibility diagnostic did
create one new authoring/AOT candidate and one new load-only device
observation; it remains outside the historical A/B and speed datasets.

## 10. Amendment rule

Corrections to URLs, hashes, or evidence descriptions may update this index in
Git with an explicit commit message. Admitting a new dataset, model output,
device measurement, artifact, or central claim requires an explicit protocol
amendment. Protocol v2 is a retrospective post-review amendment and must not
be described as preregistration.
