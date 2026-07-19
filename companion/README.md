# Core AI Qwen3-1.7B companion

This is a minimal iOS 27 app that loads a locally supplied Qwen3-1.7B
`h16p` artifact and exercises a real `LanguageModelSession`.

It is intentionally:

- unsigned;
- free of model and tokenizer resources;
- independent of any product code or database;
- configured with an example bundle identifier and no Development Team.

## Prepare resources

Follow the repository-level `REPRODUCTION.md`, then create a folder named:

`qwen3_1_7b_w8_4k_ios`

It must contain the generated model metadata, tokenizer resources, and:

`qwen3_1_7b_w8_4k_ios.h16p.aimodelc`

Drag the folder into the Xcode app target as a blue folder reference. The
folder and every model payload remain ignored by Git.

## Build

The project pins Apple's Swift package to:

`04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a`

For an unsigned compile check:

```bash
xcodebuild \
  -project CoreAIQwen17Companion.xcodeproj \
  -scheme CoreAIQwen17Companion \
  -configuration Debug \
  -destination 'generic/platform=iOS' \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  build
```

For physical-device execution, choose your own Development Team and replace the
example bundle identifier locally. Do not commit those signing changes.

## Run

1. Tap **Load model**.
2. Run the deterministic `COREAI-OK` smoke.
3. Send a normal prompt.
4. Tap **Unload** and confirm a later load still succeeds.

The app checks that the compiled model contains `main-h16p.mlirb` and a
non-empty `sourceHash`. It displays only the first 12 hash characters and
generation metrics. It does not log the user's prompt or interactive response.
