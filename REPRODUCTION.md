# Reproduction

## Requirements

- macOS with Xcode 27 and the iOS 27 SDK;
- Apple's `coreai-build` from that Xcode installation;
- Git and `uv`;
- sufficient disk space for the source weights, export intermediates, and AOT
  artifact;
- a compatible physical iPhone for runtime validation.

## Public-distribution build hygiene

Core AI export and AOT artifacts can retain absolute source and Python module
paths inside generated binary containers. This does not affect inference, but
an artifact built under a personal home directory can disclose the local
account name when redistributed.

The device evidence in this repository was produced from a private validation
build. For a public binary release, rebuild the checkout, Python environment,
source snapshot, export, and AOT output under a neutral path such as
`/private/tmp/coreai-public-build`. Do not hex-edit or otherwise patch a
generated `.aimodel` or `.aimodelc`; rebuilding is required to preserve the
container's integrity.

Before uploading any model bundle, scan the complete distribution directory,
including binary files:

```bash
./scripts/audit-public-artifact.sh /private/tmp/coreai-public-build/release
```

Projects with additional private identifiers can add one regular expression:

```bash
COREAI_PUBLIC_FORBIDDEN_PATTERN='private-bundle-id|internal-project-name' \
  ./scripts/audit-public-artifact.sh /private/tmp/coreai-public-build/release
```

A passing scan is a publication gate, not a substitute for rerunning model
integrity checks and at least one physical-device inference on the rebuilt
artifact.

## 1. Lock Apple source

```bash
git clone https://github.com/apple/coreai-models.git
cd coreai-models
git checkout 04a3fd6cfe9bfae9cf05b1f246cf915d930d1c0a
git apply ../qwen3-1.7b-coreai-ios/patches/qwen3-1.7b-coreai-main.patch
uv sync --frozen
```

The patch must apply with no fuzz or rejected hunks.

## 2. Run the focused validation

```bash
uv run ruff check \
  python/src/coreai_models/export/metadata.py \
  python/src/coreai_models/llm/export.py \
  python/src/coreai_models/model_registry.py \
  python/tests/test_model_conversion/test_ios_models.py \
  python/tests/test_model_units/test_model_registry.py \
  python/tests/test_model_units/test_export/test_llm_export.py

uv run pytest -q \
  python/tests/test_model_units/test_model_registry.py \
  python/tests/test_model_units/test_export/test_llm_export.py

uv run coreai.llm.export qwen3-1.7b \
  --platform iOS \
  --experimental \
  --dry-run
```

The dry-run must resolve:

```text
model: Qwen/Qwen3-1.7B
platform: iOS
compression: qwen3_1_7b_w8_per_tensor
compute_precision: float16
max_context_length: 4096
disable_embedding_quantization: False
```

## 3. Download the locked source revision

```bash
uv run hf download Qwen/Qwen3-1.7B \
  --revision 70d244cc86ccca08cf5af4e1e306ecf908b1ad5e \
  --local-dir ../source/Qwen3-1.7B
```

Do not use GPTQ, AWQ, GGUF, MLX, or a pre-quantized checkpoint.

## 4. Export the frozen recipe

When exporting from the locked local source directory, pass the recipe
explicitly:

```bash
uv run coreai.llm.export ../source/Qwen3-1.7B \
  --platform iOS \
  --experimental \
  --compute-precision float16 \
  --max-context-length 4096 \
  --compression-config \
    ../qwen3-1.7b-coreai-ios/recipes/qwen3_1_7b_w8_per_tensor.yaml \
  --output-dir ../artifacts \
  --output-name qwen3_1_7b_w8_4k_ios
```

Do not pass `--disable-embedding-quantization-ios`. The frozen mechanism uses
INT8 embedding quantization before the W8 K-means pass.

## 5. Compile the iPhone specialization

```bash
xcrun coreai-build compile \
  ../artifacts/qwen3_1_7b_w8_4k_ios/qwen3_1_7b_w8_4k_ios.aimodel \
  --output ../artifacts/qwen3_1_7b_w8_4k_ios.h16p.aimodelc \
  --platform iOS \
  --min-deployment-version 27.0 \
  --preferred-compute neural-engine \
  --architecture h16p
```

`--preferred-compute neural-engine` is a compile preference, not proof that
every operation runs exclusively on the Neural Engine.

## 6. Run the companion

The public companion intentionally contains no model or tokenizer payload.
Create this local-only resource folder:

```text
companion/ModelBundle/qwen3_1_7b_w8_4k_ios/
  metadata and tokenizer resources
  qwen3_1_7b_w8_4k_ios.h16p.aimodelc/
```

Add the `qwen3_1_7b_w8_4k_ios` directory to the companion target as a folder
reference, choose your own signing team and bundle identifier, then run on a
compatible physical iPhone.

The first check should be the deterministic `COREAI-OK` smoke, followed by a
normal prompt and unload/reload.
