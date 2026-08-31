# ANE trace confirmation V1, identity schema V4

This directory implements Section 3 of `paper/EXPERIMENT_PROTOCOL_V1.md`. It
contains instrumentation and deterministic derivation code, not a trace or a
result. A real run is admissible only after these files and the companion
instrumentation have been reviewed and committed.
`paper/ANE_V2_AMENDMENT_1.md` defines the signing and publication boundary.
`paper/ANE_V2_AMENDMENT_2.md` prospectively freezes the current,
runtime-compatible public W8 artifact. `paper/ANE_V2_AMENDMENT_3.md` freezes
the minimal Xcode 27 Beta 6 compatibility patch applied to the pinned Core AI
source. All three amendments and the patch are hashed into every new admissible
source identity. Do not collect a trace until Amendment 3 and the corresponding
instrumentation and tools have been reviewed and committed.

Use the same Xcode 27 Beta toolchain for every build, identity, capture, and
export command in the run:

```bash
export DEVELOPER_DIR=/Applications/Xcode-27-Beta.app/Contents/Developer
```

The scripts record the toolchain that actually executed each step, and the
analyzer rejects a capture or export made by a different toolchain.

## What the companion owns

The button **Run public W8 trace confirmation** performs this sequence:

1. create a run UUID and record the already-loaded public artifact identity;
2. create a prerequisite `LanguageModelSession` and complete an exact-response
   smoke request;
3. complete a separate exact-response warm-up on that prerequisite session;
4. create a fresh measured session and record that it is ready;
5. begin the signpost interval and issue exactly one fixed measured generation;
6. end the same interval immediately on terminal completion or error.

The frozen signpost identity is:

```text
subsystem = io.massif.qwen3.coreai.trace-confirmation
category  = inference
name      = PUBLIC_W8_TRACE_CONFIRMATION_V1
```

Both endpoints carry the public run UUID and PID. The begin endpoint is marked
`started`; the end endpoint records `completed` or `error`. App-side
records use the prefix `ANE_TRACE_V2_JSON=` and always carry the same UUID. The
measured prompt itself is not logged; its SHA-256 is logged instead.

## 1. Download, patch the pinned dependency, and build

Run from the repository root:

```bash
paper/evidence/ane-v2/download_public_w8.sh /tmp/public-w8-trace-artifact
mkdir -p companion/ModelBundle
ditto /tmp/public-w8-trace-artifact \
  companion/ModelBundle/qwen3_1_7b_w8_4k_ios
```

The downloader pins Hub revision
`75bbe06906cb5d953e602e3e4fb6364187c81822`, verifies the runtime-facing root
metadata, published `SHA256SUMS`, source `.aimodel`, compiled main, producer,
and compiled-bundle fingerprint, then writes the frozen schema-v2 benchmark
artifact manifest. Its required SHA-256 is
`91c68e82e280a36d39aaeef9b8726ab1d59e52760b6f970db67c334a674d47b2`.
The generated manifest is a local evidence object, not a file claimed to exist
at the immutable Hub revision.

The destination is ignored and already referenced by the Xcode project. Do
not drag resources into Xcode. Resolve the checked-in package graph into a new
package directory, apply the committed compatibility patch to the pinned Core
AI checkout, and then build from that same directory with automatic package
resolution disabled:

```bash
export TRACE_SOURCE_PACKAGES=/tmp/PublicW8TraceSourcePackages
test ! -e "$TRACE_SOURCE_PACKAGES"

DEVELOPER_DIR=/Applications/Xcode-27-Beta.app/Contents/Developer \
xcodebuild \
  -resolvePackageDependencies \
  -project companion/CoreAIQwen17Companion.xcodeproj \
  -scheme CoreAIQwen17Companion \
  -clonedSourcePackagesDirPath "$TRACE_SOURCE_PACKAGES" \
  -onlyUsePackageVersionsFromResolvedFile

git -C "$TRACE_SOURCE_PACKAGES/checkouts/coreai-models" apply \
  --check "$PWD/paper/evidence/ane-v2/coreai-models-xcode27-beta6-compat.patch"
git -C "$TRACE_SOURCE_PACKAGES/checkouts/coreai-models" apply \
  "$PWD/paper/evidence/ane-v2/coreai-models-xcode27-beta6-compat.patch"

DEVELOPER_DIR=/Applications/Xcode-27-Beta.app/Contents/Developer \
xcodebuild \
  -project companion/CoreAIQwen17Companion.xcodeproj \
  -scheme CoreAIQwen17Companion \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -derivedDataPath /tmp/PublicW8TraceDerivedData \
  -clonedSourcePackagesDirPath "$TRACE_SOURCE_PACKAGES" \
  -disableAutomaticPackageResolution \
  -onlyUsePackageVersionsFromResolvedFile \
  DEVELOPMENT_TEAM="$TRACE_DEVELOPMENT_TEAM" \
  PRODUCT_BUNDLE_IDENTIFIER=io.massif.PublicW8TraceConfirmation \
  build
```

The patch changes only the two files and four Foundation Models API call sites
listed in Amendment 3. It does not change tokenization, generation controls,
or model assets. Identity preparation rejects an unpatched checkout, an extra
tracked or untracked change, a different base revision, or any patched-file
digest mismatch.

Before installation, and only after the instrumentation commit exists, seal
the static identities:

```bash
mkdir -p /tmp/public-w8-trace-public
mkdir -m 700 /tmp/public-w8-trace-private
DEVELOPER_DIR=/Applications/Xcode-27-Beta.app/Contents/Developer \
python3 paper/evidence/ane-v2/prepare_identity.py \
  --repo "$PWD" \
  --artifact-dir /tmp/public-w8-trace-artifact \
  --app /tmp/PublicW8TraceDerivedData/Build/Products/Release-iphoneos/CoreAIQwen17Companion.app \
  --coreai-checkout "$TRACE_SOURCE_PACKAGES/checkouts/coreai-models" \
  --publication-dir /tmp/public-w8-trace-public \
  --public-output /tmp/public-w8-trace-public/identity.json \
  --private-output /tmp/public-w8-trace-private/identity-private.json
```

The command fails if any frozen artifact or runtime field differs, if the generated
artifact manifest does not cover exactly the downloaded regular files, if any
companion/ANE-analysis source is dirty, if `codesign --verify --deep --strict`
fails, the fixed public bundle identifier does not match, or a required
identity is absent. Hugging Face's transport-only `.cache` directory and all
symbolic links are rejected. Each schema-v2 manifest entry contains:

```text
path, bytes, sha256
```

The public record includes the manifest and its digest; the exact root-metadata
version and digest; the exact `SHA256SUMS` digest; the source, compiled-main,
producer, and compiled-bundle identities; the source commit, project,
`Package.resolved`, all amendment hashes, runtime patch identity, per-file
base and patched hashes, and source-file hashes; Release app
and executable hashes; verified signing status, CDHash, signature format, and
signing-output hashes; the fixed bundle identifier; Xcode/Instruments build;
and the verified Core AI source revision. It contains no signing Identifier,
team identifier, or authority string. Those fields and the strict-verification
result exist only in the bound private record. The script refuses a private
path inside either the repository or publication directory and creates the
private file with mode `0600`.

The source Info.plist carries `ANETraceBuildConfiguration` from Xcode's
`$(CONFIGURATION)` build setting. Xcode expands the value in the processed app
bundle. Identity preparation reads that processed value and accepts only
`Release`; it does not assign the label from the command that invoked the
script.

At run time, the companion hashes its installed executable. Metadata sealing
and analysis require that hash to equal the executable in the sealed Release
app, closing the gap between the host build and the process that was captured.

## 2. Capture one exact-PID run

Create or review an Instruments template that contains both **Core AI** and
**Points of Interest**. Save the template as a file; a named built-in template
is not sufficient evidence that both instruments were enabled. Load the model
before capture and obtain the app's current PID from the device process list.

Use the device UDID only through a private environment variable so a personal
device name or identifier is not published:

```bash
export TRACE_DEVICE_UDID='private-device-identifier'
python3 paper/evidence/ane-v2/capture_trace.py \
  --pid "$TRACE_APP_PID" \
  --template /absolute/path/PublicW8CoreAIAndPOI.tracetemplate \
  --time-limit 90s \
  --output /tmp/public-w8-trace-private/public-w8.trace \
  --command-record /tmp/public-w8-trace-public/capture-command.json \
  >/tmp/public-w8-trace-private/capture.stdout \
  2>/tmp/public-w8-trace-private/capture.stderr
```

After recording starts, tap **Run public W8 trace confirmation** exactly once.
Do not run another generation during the capture. Save the app console or
unified-log output without editing it.

`capture_trace.py` attaches to the supplied numeric PID. Its public command
record uses fixed placeholders for the device, template, and trace bundle. It
contains no device identifier or hash, host path, or stdout/stderr hash. The
template hash, attached PID, timestamps, return code, and actual
Xcode/Instruments versions remain public. Raw command output stays in the
private directory.

## 3. Export all required tables

First inspect the trace table of contents:

```bash
xcrun xctrace export \
  --input /tmp/public-w8-trace-private/public-w8.trace \
  --toc \
  --output /tmp/public-w8-trace-private/toc-preview.xml
```

Record the actual schema strings for the complete signpost intervals,
MPSGraph Program, Apple Neural Engine Prediction, process information, and
ODIEProfile tables. Then export those exact schemas:

```bash
python3 paper/evidence/ane-v2/export_trace.py \
  --trace /tmp/public-w8-trace-private/public-w8.trace \
  --output-dir /tmp/public-w8-trace-private/exports \
  --signposts-schema 'SCHEMA_FROM_TOC' \
  --mpsgraph-schema 'SCHEMA_FROM_TOC' \
  --ane-schema 'SCHEMA_FROM_TOC' \
  --process-info-schema 'SCHEMA_FROM_TOC' \
  --odie-profile-schema 'SCHEMA_FROM_TOC'
```

The exporter never guesses a schema and never drops source columns. It first
requires each supplied schema to occur exactly once in the selected TOC run and
requires five distinct schemas. The private directory retains the TOC and all
five XML exports. The reviewed public command record retains their hashes, the
trace-bundle hash, placeholder-only command arguments, and the Xcode/Instruments
versions that performed the export. Copy only `export-command.json` into the
public directory after review.

```bash
cp /tmp/public-w8-trace-private/exports/export-command.json \
  /tmp/public-w8-trace-public/export-command.json
```

Because a `.trace` is a bundle, its recorded hash is the SHA-256 of a sorted
`sha256<TAB>size<TAB>kind<TAB>path<NEWLINE>` manifest; symlink hashes cover
`SYMLINK<NUL>` plus the UTF-8 target. The Release app bundle uses the same
tabular manifest definition. The downloaded model instead uses the schema-v2
benchmark JSON manifest described in Section 1. Each definition is used
identically wherever that object is sealed and later verified.

## 4. Canonicalize without changing the matching rule

`xctrace` XML positions and units can vary with toolchain schema. Create three
small mapping JSON files after inspecting the exported schema. Each mapping
uses schema `ane-v2-xctrace-column-map-v1`, declares a `table_role`, the XML
`row_xpath`, and exactly the canonical fields required by
`canonicalize_xctrace.py`. Both the mapping's top-level keys and every column
specification use exact allowlists; unknown keys, multiple source modes, an
untyped null substitution, or a unit on a non-time field is rejected.

For interval tables, retain the original program label, channel, state,
process, PID, timestamp, duration, and native identifier. Set
`native_identifier_name` to the exact shared exported column name only when
both tables expose the same stable native identifier; otherwise set it to
`null`. Do not insert invented identifiers or substitute constants for missing
source fields. The converter accepts explicit child indexes or tags, resolves
the `id`/`ref` representation used by xctrace XML, supports optional attribute
and regex extraction, and performs exact `ns`, `us`, `ms`, or `s` conversion.
It rejects sub-nanosecond values rather than rounding them.

For the signpost mapping, extract the UUID and PID from the frozen public
message fields, use the complete begin-to-end interval, and derive
`terminal_state` from the end endpoint. Do not canonicalize a begin-only or
end-only row as a complete measured interval.

```bash
python3 paper/evidence/ane-v2/canonicalize_xctrace.py \
  --xml /tmp/public-w8-trace-private/exports/signposts.xml \
  --mapping /tmp/public-w8-trace-public/signpost-map.json \
  --target-pid "$TRACE_APP_PID" \
  --private-output /tmp/public-w8-trace-private/signposts-full.json \
  --public-output /tmp/public-w8-trace-public/signposts.json

python3 paper/evidence/ane-v2/canonicalize_xctrace.py \
  --xml /tmp/public-w8-trace-private/exports/mpsgraph.xml \
  --mapping /tmp/public-w8-trace-public/mpsgraph-map.json \
  --target-pid "$TRACE_APP_PID" \
  --private-output /tmp/public-w8-trace-private/mpsgraph-full.json \
  --public-output /tmp/public-w8-trace-public/mpsgraph.json

python3 paper/evidence/ane-v2/canonicalize_xctrace.py \
  --xml /tmp/public-w8-trace-private/exports/ane.xml \
  --mapping /tmp/public-w8-trace-public/ane-map.json \
  --target-pid "$TRACE_APP_PID" \
  --private-output /tmp/public-w8-trace-private/ane-full.json \
  --public-output /tmp/public-w8-trace-public/ane.json
```

Mapping files are evidence inputs and must be published with the run. They may
describe the exported schema but may not alter the frozen exact-key rule.
Each full canonical table remains private with mode `0600`. Its public partner
contains only rows whose PID equals the captured process, a SHA-256 commitment
to the full canonical table, and the number of omitted other-process rows.

## 5. Seal dynamic metadata

Extract the UUID-owned app records:

```bash
python3 paper/evidence/ane-v2/extract_app_records.py \
  --log /tmp/public-w8-trace-private/device-console.log \
  --output /tmp/public-w8-trace-public/app-records.json
```

Read the Core AI build from the retained ODIEProfile/Core AI export. Seal the
run metadata, cross-checking the exact PID, public artifact, sourceHash, bundle
identifier, prompt hash, trace hash, and toolchain identity:

```bash
python3 paper/evidence/ane-v2/seal_run_metadata.py \
  --identity /tmp/public-w8-trace-public/identity.json \
  --private-identity /tmp/public-w8-trace-private/identity-private.json \
  --trace /tmp/public-w8-trace-private/public-w8.trace \
  --capture-command /tmp/public-w8-trace-public/capture-command.json \
  --export-command /tmp/public-w8-trace-public/export-command.json \
  --odie-profile-export /tmp/public-w8-trace-private/exports/odie_profile.xml \
  --app-records /tmp/public-w8-trace-public/app-records.json \
  --coreai-build 'VALUE_FROM_RETAINED_EXPORT' \
  --output /tmp/public-w8-trace-public/run-metadata.json
```

The sealer requires the Core AI build to be an exact dotted numeric version. It
parses the retained ODIEProfile XML and accepts the version only when the same
complete token occurs in a Core AI build/version field or row. Arbitrary
substrings such as `build`, `coreai`, or a partial version do not satisfy this
check. The exact export hash must also match the one recorded by
`export_trace.py`.

A terminal error remains in the raw records, but it is not silently promoted
to an admissible confirmation run.

## 6. Analyze the owned interval

```bash
python3 paper/evidence/ane-v2/analyze_trace.py \
  --signposts /tmp/public-w8-trace-public/signposts.json \
  --mpsgraph /tmp/public-w8-trace-public/mpsgraph.json \
  --ane /tmp/public-w8-trace-public/ane.json \
  --identity /tmp/public-w8-trace-public/identity.json \
  --run-metadata /tmp/public-w8-trace-public/run-metadata.json \
  --capture-command /tmp/public-w8-trace-public/capture-command.json \
  --export-command /tmp/public-w8-trace-public/export-command.json \
  --app-records /tmp/public-w8-trace-public/app-records.json \
  --output /tmp/public-w8-trace-public/ane-analysis.json
```

The analyzer first re-hashes the current protocol, both amendments, analyzer,
canonicalizer, sealer, public validator, app source, Xcode project, and the
complete sealed source-file set, and requires the current Git commit to match
the identity. It then requires exactly one complete frozen signpost interval
for the recorded UUID and PID. Public tables may contain only that PID. Target
rows whose start precedes `RUN_BEGIN` or whose end exceeds `RUN_END` are
excluded, while the private other-process row count is carried into the public
exported and exclusion totals. If both canonical tables declare the same
non-null native identifier and every eligible row has one, the key is exactly:

```text
(typed_native_identifier, relative_start_ns, duration_ns)
```

Otherwise it uses exactly:

```text
(relative_start_ns, duration_ns)
```

Rows are joined as multisets. The result contains each target-process pair,
both target-process unmatched sides, aggregate exclusion counts by reason,
every target-process key multiplicity, and duplicate multiplicities. It never
copies a row from another process. There is no tolerance, nearest timestamp,
row-order pairing, or hard-coded expected count.

Only a nonzero exact match permits the sentence:

> The Apple Neural Engine participated in the traced inference program.

The output expressly excludes claims of exclusive ANE execution, work share,
absence of CPU/GPU work, performance or energy benefit, or generalization
beyond the recorded artifact, build, device, OS, and run.

## Publication boundary

Never publish the signed app, provisioning profile, build logs, device console,
capture stdout/stderr, raw `.trace` bundle, TOC, XML exports, full canonical
tables, private identity, or any executed command containing a device
identifier or host path. Keep those items in the private directory and
content-address them there. The public
directory contains only the twelve reviewed JSON records named by
`validate_public_bundle.py`; it must contain no symlink or additional file.

The public bundle lets a reviewer verify every target-process row, the exact
analysis, the full-table commitment, and the stated number of omitted rows. By
design, it does not reveal the other-process rows, so a reviewer cannot
independently recompute the commitment or omitted-row count without access to
the retained private canonical table. This is the explicit privacy boundary,
not an independent public proof of those hidden values.

Before copying a run into the repository, run the recursive checker:

```bash
python3 paper/evidence/ane-v2/validate_public_bundle.py \
  --bundle /tmp/public-w8-trace-public
```

The checker scans original bytes before parsing, rejects private tokens and
host/container paths, duplicate JSON keys, private signing or device fields,
an extra or missing file, and a non-regular entry. Every public JSON document
has an exact schema; mapping top levels and column specifications are validated
before their hashes are accepted. The checker also re-hashes the current sealed
source bytes and commit, rejects any non-target process row, and requires the
analysis file to be the byte-for-byte deterministic result of the public
inputs.

## Tests

The fixtures are synthetic and contain no real device result:

```bash
python3 -m unittest discover \
  -s paper/evidence/ane-v2/tests \
  -p 'test_*.py' -v
```
