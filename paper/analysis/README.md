# Deterministic analysis pipeline

This pipeline reconstructs manuscript data from the already published evidence.
It does not call either model, invoke Core AI, connect to a device, or create a
new measurement.

## What it does

1. Fetches the two public evidence repositories at their exact commits.
2. Verifies every admitted input against `source-lock.json`.
3. Downloads the official CMRC2018 development file at its exact commit and
   refuses any source whose SHA-256 differs.
4. Runs the frozen sample builder and requires the historical 300-sample hash.
5. Recomputes the published paired quality result under Python 3.11.15 and
   NLTK 3.10.0, then requires byte-for-byte identity with the published JSON.
6. Reanalyzes the unchanged paired predictions with a post-review,
   context-length-stratified bootstrap and exact paired sign tests.
7. Parses every accepted speed sample from the fixed-hash report, recomputes
   medians, and checks them against the report's headline table.
8. Generates machine-readable inputs for Tables T2–T7 and Figures F3–F5.

The copyrighted dataset text and cloned repositories remain under the ignored
`.analysis-work/` directory. Generated outputs contain aggregates and already
public timing rows, not passages, questions, or reference answers.

## Run

Requirements: `git`, `curl`, `uv`, and network access for the first run.

```sh
./analysis/run.sh
```

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

Generated files are written to `analysis/generated/`. A successful run ends
with `PIPELINE_OK` and prints the source and generated-output hashes.

For an isolated review output, `--generated-dir` may name a direct child of
`analysis/` whose name starts with `generated` (for example,
`analysis/generated-review`). Relative paths are resolved from the repository
root, even when the launcher is called elsewhere. The same resolved directory
is passed to the tests, and its manifest must list exactly every generated file.
