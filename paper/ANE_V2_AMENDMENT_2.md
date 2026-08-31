# ANE Trace Protocol Amendment 2: Runtime-Compatible Public W8 Identity

Date: 2026-08-31
Status: prospective; no trace governed by this amendment has been collected

The public W8 artifact frozen by `EXPERIMENT_PROTOCOL_V1.md` no longer loads in
the current device and runtime environment. A separately compiled W8 artifact
has since crossed the load boundary with the frozen model, recipe, context
length, and Core AI source revision. This amendment changes the artifact used
by the ANE trace experiment so that a new trace can test the current,
runtime-compatible artifact. It does not reinterpret or replace evidence tied
to the earlier artifact.

No trace is admissible under this amendment unless this file, the updated
companion, and the updated ANE evidence tools have first been reviewed and
committed. The resulting source commit and this amendment's digest must be
sealed into the pre-capture identity. `ANE_V2_AMENDMENT_1.md` remains in force
for signing, privacy, publication, and attribution; it is unchanged and is
also included in the sealed source manifest.

## Frozen public artifact

| Field | Required value |
| --- | --- |
| Hugging Face repository | `massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p` |
| Immutable revision | `75bbe06906cb5d953e602e3e4fb6364187c81822` |
| Root `metadata_version` | `0.2` |
| Root `metadata.json` SHA-256 | `c12e3b1035dd8c009d5b8d8572d0ad829236871edd10c02ef35d89644c5289d1` |
| Published `SHA256SUMS` SHA-256 | `11b44a503983182f99f5de2a458947ac1bfb9b68bfaafd39a5b13feb4d430be9` |
| Generated benchmark artifact manifest SHA-256 | `91c68e82e280a36d39aaeef9b8726ab1d59e52760b6f970db67c334a674d47b2` |
| Source `.aimodel` SHA-256 | `13ba3f73fcb7e090cd6ba1ca14b6b8903516ab608d451e94b9cdd750cfceda2c` |
| Compiled `main-h16p.mlirb` SHA-256 | `09f609775baa56b11ff3c91bfcb07b145930297289634fdc5514b2a5ab4dc7ca` |
| Compiler producer | `coreai-build-3600.83.1` |
| Compiled-bundle file-list fingerprint | `182336f4654bb735bcad35e45f7832756c34469931ad96d872532dca727ebd8d` |

The benchmark artifact manifest is generated locally after downloading the
immutable Hub revision. It uses schema version 2, covers every downloaded
regular file except itself, and records the repository, revision, byte count,
and SHA-256 of each file. Its embedded `publishedSHA256SUMS` summary is derived
from the exact published `SHA256SUMS` file. Identity preparation must reject a
different file set, path, byte count, digest, root metadata version, compiled
producer, source hash, compiled-main hash, or compiled-bundle fingerprint.

The root metadata and generated manifest are separate identity objects. The
root metadata digest binds the runtime-facing package description, while the
generated manifest binds the complete downloaded revision. Neither digest may
be substituted for the other.

Because the public identity record gains required artifact fields, its schema
advances from `public-w8-trace-identity-v2` to
`public-w8-trace-identity-v3`. App records, run metadata, and the private
signing record retain their existing schemas because their field sets do not
change.

## Unchanged experiment boundary

This amendment changes only the public W8 artifact identity and the checks
needed to bind it. It does not change the fixed prompt, sessions, signpost,
trace template, target PID, device class, toolchain requirement, exact join,
or permitted conclusion. In particular, a matching trace can establish only
that the Apple Neural Engine participated in the recorded inference program;
it cannot establish exclusive ANE execution, work share, a performance or
energy advantage, or behavior outside the sealed run.

Historical files and conclusions remain attached to their original artifact
identities. No result collected before the prospective source commit for this
amendment may be relabeled as an Amendment 2 result.
