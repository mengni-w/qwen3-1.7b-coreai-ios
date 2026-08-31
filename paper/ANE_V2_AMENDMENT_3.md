# ANE Trace Protocol Amendment 3: Xcode 27 Beta 6 Runtime Compatibility

Date: 2026-09-01
Status: prospective; no trace governed by this amendment has been collected

The companion app did not compile against the Core AI source revision fixed by
`Package.resolved` when built with Xcode 27 Beta 6 (build `27A5252f`). The
failure was confined to Foundation Models API changes: two
`LanguageModelCapabilities` initializers no longer accept an argument label,
and two usage-update events now require an explicit metadata value. This
amendment freezes the smallest source patch that resolves those four compiler
errors. A Release diagnostic build with exactly those changes completed before
this amendment was written; no Instruments trace or accelerator result was
collected or inspected.

No trace is admissible under this amendment unless this file, the exact patch,
the updated identity code, and the updated analyzer have first been reviewed
and committed. Identity preparation must then verify the post-build Core AI
checkout against the committed patch before the app is installed or a trace is
captured.

## Frozen runtime source

| Field | Required value |
| --- | --- |
| Repository | `https://github.com/apple/coreai-models.git` |
| Base revision | `04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a` |
| Patch | `paper/evidence/ane-v2/coreai-models-xcode27-beta6-compat.patch` |
| Patch SHA-256 | `100d8e3e0c865aa3a94e0bc96f5f202fc6581e1df029053a0f72e69198919044` |

The patch may change exactly these files:

| Relative path | Base SHA-256 | Patched SHA-256 |
| --- | --- | --- |
| `swift/Sources/CoreAILanguageModels/LanguageModel/CoreAILanguageModel.swift` | `9a672d0b3c8faa200a7326a5c38df74740bd31c8f96bce12232fdc41f967ca23` | `fd6f9b7c7344faf9bb6e3333dc06fb9a8466f886f1d994458afb939d0762ead6` |
| `swift/Sources/CoreAILanguageModels/VLM/CoreAIVisionLanguageModel.swift` | `78a426a821bd1dd4eff4a5eda1c77a72444270ec5ed2a49538113887b8c48a99` | `0938e55c0a5b8dc1430bb2ea87ed78795df6255a6c1c331cd55853dd09c07a1d` |

Identity preparation must require all of the following: the checkout `HEAD`
equals the base revision; the sole `coreai-models` pin in `Package.resolved`
equals the same revision; the patch applies in reverse to the checkout; the
tracked diff contains exactly the two paths above; no untracked file exists;
and each base and patched file has the stated digest. This binds the built app
to a reproducible base-to-patch transition rather than merely recording a
dirty dependency checkout.

The patch does not alter tokenization, chat-template arguments, sampling,
session construction, model assets, or generation control. The VLM file is
compiled as part of the package but is not called by this text-only companion.
The two empty metadata dictionaries satisfy the Beta 6 event initializer and
carry no experiment result.

## Identity and interpretation

The public identity schema advances from `public-w8-trace-identity-v3` to
`public-w8-trace-identity-v4`. It adds the runtime repository, base revision,
patch identity, and per-file base and patched digests. Amendment 1 remains the
signing and publication boundary. Amendment 2 remains the public W8 artifact
identity. This amendment becomes the latest protocol amendment and is the hash
bound by run metadata.

The companion uses a committed source `Info.plist` whose
`ANETraceBuildConfiguration` value is `$(CONFIGURATION)`. Xcode must expand it
to `Release` in the processed app bundle before identity preparation succeeds.
The source plist is included in the identity's source-file manifest; the
processed plist and complete signed app bundle are hashed separately.

All other experimental requirements remain unchanged: the public W8 artifact,
fixed prompt, sessions, signpost, target PID, trace template, device class,
Xcode and Instruments build, exact join, and permitted conclusion. A matching
trace can establish only that the Apple Neural Engine participated in the
recorded inference program built from the patched runtime above. It cannot be
described as evidence from the unmodified upstream revision, as exclusive ANE
execution, or as a performance or energy comparison.

Historical traces remain attached to their original source identities. No
result collected before the prospective source commit for this amendment may
be relabeled as an Amendment 3 result.
