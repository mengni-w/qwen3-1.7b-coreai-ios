#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
MANUSCRIPT="$ROOT/manuscript"
OUTPUT="$MANUSCRIPT/output/pdf"
TECTONIC_BIN=${TECTONIC:-$(command -v tectonic || true)}
EXPECTED_TECTONIC_VERSION="Tectonic 0.17.0"

if [ -z "$TECTONIC_BIN" ]; then
    echo "ERROR: tectonic is required. Set TECTONIC=/absolute/path/to/tectonic." >&2
    exit 1
fi

OBSERVED_TECTONIC_VERSION=$("$TECTONIC_BIN" --version)
if [ "$OBSERVED_TECTONIC_VERSION" != "$EXPECTED_TECTONIC_VERSION" ]; then
    echo "ERROR: expected $EXPECTED_TECTONIC_VERSION, observed $OBSERVED_TECTONIC_VERSION." >&2
    exit 1
fi

cd "$ROOT"
./analysis/run.sh --test-only
python3 manuscript/generate_assets.py "$@"
python3 manuscript/claim_audit.py

mkdir -p "$OUTPUT"
"$TECTONIC_BIN" \
    --keep-logs \
    --keep-intermediates \
    --outdir "$OUTPUT" \
    manuscript/qwen3-coreai-report.tex

test -s "$OUTPUT/qwen3-coreai-report.pdf"
if grep -Eq \
    'Overfull \\hbox|Undefined control sequence|Citation .* undefined|Reference .* undefined|There were undefined references' \
    "$OUTPUT/qwen3-coreai-report.log"; then
    echo "ERROR: the manuscript log contains an overflow or unresolved reference." >&2
    exit 1
fi
echo "PAPER_BUILD_OK"
echo "pdf=$OUTPUT/qwen3-coreai-report.pdf"
