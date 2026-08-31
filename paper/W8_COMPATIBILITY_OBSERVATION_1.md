# W8 Compatibility Observation 1

Date: 2026-08-29
Status: descriptive post-review load-only observation
Governing admission protocol: `REPORT_PROTOCOL_V2.md`
Claim identifiers: `CL-28` and `CL-29`

## 1. Question and scope

This record documents the observed failures of a previously validated public
W8 AOT in the current device environment and whether a freshly exported and
compiled candidate could cross the same load boundary. It does not identify
why the old artifact failed. It is not a speed, quality,
generation, energy, thermal, or ANE-trace experiment.

The candidate load was deliberately limited to one attempt. This does not make
the investigation preregistered or give the single duration the status of a
performance estimate.

## 2. Shared device environment

- device class: iPhone 15 Pro (`iPhone16,1`, A17 Pro, `h16p`)
- operating system: iOS 27
- OS build: `24A5424a`

No other device was used. Device names and persistent identifiers are excluded.

## 3. Previously published artifact

- role: the exact public W8 rebuild that previously passed its recorded
  six-case suite
- authoring `main.mlirb` SHA-256 recorded by the AOT metadata:
  `5e885ec407f1b2690df5098d38b1bed4a3e66f4352c859fb2bb79666bc0aef73`
- compiled `main-h16p.mlirb` SHA-256:
  `a7eefeef16708a324f9919890355eb92180ec85eef419ebd5822e8c8afd42f5f`
- compiler producer: `coreai-build-3600.75.3`

Observed current-environment attempts:

1. Load attempt 1 terminated during `ANECCompileOffline`.
2. A full reboot was requested. The host command timed out while waiting for
   the device, after which the same physical device was observed booted and
   connected again before the application was installed and launched.
3. Load attempt 2 then also terminated during `ANECCompileOffline`.

These attempts establish two failures at the recorded phase on the stated
artifact/device/OS combination. They do not identify the cause of the failure.
This sequence is not an independently instrumented boot transition and does
not establish that every persistent cache or item of system state was cleared.

## 4. New candidate construction

- base model: `Qwen/Qwen3-1.7B`
- base revision:
  `70d244cc86ccca08cf5af4e1e306ecf908b1ad5e`
- Apple `coreai-models` commit:
  `04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`
- patch SHA-256:
  `bc8f135d5637d629beac727e4d10b0b6e909ebcc77206c39c971d8967d4360d4`
- recipe SHA-256:
  `dab03ae1dd6c6290a7964e05ebcda7fe027c2bb240174fcf034e64a376be9d72`
- Xcode: 27 Beta 6
- compiler producer: `coreai-build-3600.83.1`
- authoring `main.mlirb` SHA-256 recorded by the AOT metadata:
  `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c`
- compiled `main-h16p.mlirb` SHA-256:
  `09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca`
- complete `.aimodelc` file-list fingerprint:
  `182336f4654bb735bcad35e45f7832756c34469931ad96d872532dca727ebd8d`

The candidate shares the pinned checkpoint and recipe with the public route,
but it is a separate exported and compiled artifact. It must not be described
as byte-identical to either the historical A/B binary or the previously
published W8 rebuild.

## 5. Candidate load observation

Exactly one load-only attempt was made on the device and OS build stated above.

- load completed: yes
- observed load duration: `41.931619875 seconds`
- observed peak process RSS: `2737.046875 MiB`
- unload completed: yes
- process exit status: `0`
- generation performed: no
- Instruments trace performed: no
- cache-cold state established: no

The duration and RSS describe this one process observation. RSS is not total
system memory, and the observation is not a minimum-memory requirement.

## 6. Minimal repeat-export check

A second export used the same checkout, virtual environment, source model,
recipe, and export parameters. Only the output directory changed. No second AOT
or device load was performed.

| Export | Source SHA-256 | Size |
| --- | --- | ---: |
| First | `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c` | 1,739,655,751 bytes |
| Second | `12349a9ad32bf2a1d2f9a6f201ffec3125c28c027786fa9925dc34669d8bc946` | 1,739,655,747 bytes |

The two raw outputs were not byte-identical. Because the output directory also
changed, this check does not determine whether the difference arose from path
metadata or another source. A raw source hash mismatch alone therefore cannot
establish a recipe, weight, structure, or numerical mismatch, and this two-run
check does not establish path-independent export nondeterminism.

## 7. Interpretation boundary

The observations are consistent with compatibility depending on the particular
exported artifact, compiler product, and current runtime combination. They do
not isolate which component caused the old artifact to fail. In particular,
this record does not claim an iOS regression, compiler bug, memory-shortage
cause, cold-cache measurement, generation success, or ANE participation for the
new candidate.

The earlier public-artifact six-case pass and historical ANE trace remain tied
to their own recorded artifacts and environments. The new candidate load cannot
replace either result.
