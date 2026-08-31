# Core AI Qwen3-1.7B companion

This is a minimal iOS 27 app that loads a locally supplied Qwen3-1.7B
`h16p` artifact and exercises a real `LanguageModelSession`.

It is intentionally:

- free of committed signing credentials or a Development Team;
- free of model and tokenizer resources;
- independent of any product code or database;
- configured with an example bundle identifier and no Development Team.

## Prepare resources

For the preregistered ANE confirmation, download the exact public revision with
`paper/evidence/ane-v2/download_public_w8.sh`. Copy that downloaded directory to:

`companion/ModelBundle/qwen3_1_7b_w8_4k_ios`

It must contain the published metadata, tokenizer resources, and:

`qwen3_1_7b_coreai_ane_w8_4k.h16p.aimodelc`

The Xcode project already has a blue folder reference to this ignored path.
Do not drag the folder into Xcode or otherwise edit the project file locally.
The app rejects a metadata `sourceHash` other than the one pinned by
`EXPERIMENT_PROTOCOL_V1.md`.

## Build

The project pins Apple's Swift package to:

`04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`

For an unsigned compile check:

```bash
xcodebuild \
  -project CoreAIQwen17Companion.xcodeproj \
  -scheme CoreAIQwen17Companion \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  build
```

For physical-device execution, supply your Development Team and the fixed trace
bundle identifier on the `xcodebuild` command line. Do not commit signing
credentials or project changes. The ANE protocol requires the resulting Release
app to pass `codesign --verify --deep --strict`; an unsigned build is never an
admissible trace app.

The source Info.plist embeds
`ANETraceBuildConfiguration=$(CONFIGURATION)`. Xcode expands that value while
processing the selected build configuration. The identity script reads it from
the built app and rejects Debug or any other value; the evidence cannot label
itself as Release.

## Run

1. Tap **Load model**.
2. Run the deterministic `COREAI-OK` smoke.
3. Send a normal prompt.
4. Tap **Unload** and confirm a later load still succeeds.

The **Run public W8 trace confirmation** button is reserved for the procedure
in `paper/evidence/ane-v2/README.md`. It creates a dedicated session, performs
the smoke test and warm-up outside the owned signpost interval, then places
exactly one measured generation inside that interval.

Public app records use the fixed `ANE_TRACE_V2_JSON=` marker and exact
event-specific field allowlists. Framework error descriptions and unknown
fields remain in the private console only and are never emitted through the
public marker.

The app checks that the compiled model contains `main-h16p.mlirb` and the
protocol-pinned `sourceHash`. It displays only the first 12 hash characters and
generation metrics. It does not log the user's prompt or interactive response.
