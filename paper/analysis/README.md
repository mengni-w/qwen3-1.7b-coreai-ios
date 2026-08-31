# Deterministic analysis pipeline

This pipeline reconstructs manuscript data from the already published evidence.
It does not call either model, invoke Core AI, connect to a device, or create a
new measurement.

## What it does

1. Fetches the two public evidence repositories at their exact commits.
2. Verifies every admitted input against `source-lock.json`, including the
   corrected formal `results/fidelity-v2-summary.json` and the post-review
   compatibility summary, sanitized event records, and event manifest in this
   repository.
3. Downloads the official CMRC2018 development file at its exact commit and
   refuses any source whose SHA-256 differs.
4. Runs the frozen sample builder and requires the historical 300-sample hash.
5. Recomputes the published paired quality result under Python 3.11.15 and
   NLTK 3.10.0, then requires byte-for-byte identity with the published JSON.
6. Reanalyzes the unchanged paired predictions with a post-review,
   context-length-stratified bootstrap and exact paired sign tests.
7. Admits only a finalized, conformant eight-block
   `public-artifact-speed-confirmation-v2` publication bundle under
   `REPORT_PROTOCOL_V3.md`. Before a bundle is accepted, a candidate path is
   required explicitly. After acceptance, the source-locked bundle is selected
   automatically and cannot be overridden from the command line.
8. Generates T3 from the corrected formal fidelity-v2 result. The older
   `quality-summary.json` remains available only as historical model-selection
   evidence; its W8 fidelity values are superseded.
9. Cross-checks the compatibility summary against the sanitized load and
   device-transition records, including the reboot-request/reconnect boundary.
10. Generates machine-readable inputs for Tables T2–T8 and Figures F3–F5. T8
    preserves the compatibility record's load-only and non-causal boundaries.

The copyrighted dataset text and cloned repositories remain under the ignored
`.analysis-work/` directory. Generated outputs contain aggregates and already
public timing rows, not passages, questions, or reference answers.

## Prospective speed-v2 evidence

Before the new result is integrated, copy only the immutable root
`FINALIZED.json` and its byte-identical `public/` directory into a fresh
publication bundle. Do not copy `host/`, `.xcresult` bundles, device-control
output, or other private acquisition files. Then run:

```sh
./analysis/run.sh \
  --speed-evidence-dir evidence/speed-v2/attempts/<run-id>
```

Relative evidence paths are resolved from `paper/`. The pipeline rehashes every
file named by the public evidence index and requires that the index cover every
public file. It cross-checks the finalization certificate, public host record,
analyzer summary, frozen identities, eight-block schedule, 120 completed
profile observations, and 60 complete pairs. An aborted, nonconformant,
partially completed, privately sourced, or unfinalized bundle is rejected
before it can supply a paper statistic.

Until a successful run has been copied and frozen in `source-lock.json`, a
normal analysis run requires `--speed-evidence-dir`. The historical
three-sample output can only be checked by the explicit `--test-only` path; it
cannot be regenerated as current paper evidence. The later evidence-integration
commit fills `speedV2Admission.acceptedBundle` with the repository-relative
bundle path, run ID, finalization hash, public-index hash, public-host-record
hash, and analyzer-summary hash. From that commit onward, `./analysis/run.sh`
uses the accepted bundle by default and rejects any `--speed-evidence-dir`
override.

## Run

Requirements: `git`, `curl`, `uv`, and network access for the first run.

```sh
./analysis/run.sh
```

This default form is the submission path after `acceptedBundle` has been
filled. During prospective candidate review, use the command in the preceding
section instead.

After one successful online run, the exact cached inputs can be reused without
network access:

```sh
./analysis/run.sh --offline
```

The launcher applies this offline contract to both `uv` and the analysis
program. If the locked Python runtime or a locked wheel is absent, the command
fails instead of downloading it.

Run the committed-output checks with:

```sh
./analysis/run.sh --test-only
```

While `acceptedBundle` is `null`, this is the only path allowed to validate the
committed historical schema-1 speed output. It does not create or admit a new
paper result.

Generated files are written to `analysis/generated/`. A successful run ends
with `PIPELINE_OK` and prints the source and generated-output hashes.

For an isolated review output, `--generated-dir` may name a direct child of
`analysis/` whose name starts with `generated` (for example,
`analysis/generated-review`). Relative paths are resolved from the repository
root, even when the launcher is called elsewhere. The same resolved directory
is passed to the tests, and its manifest must list exactly every generated file.
