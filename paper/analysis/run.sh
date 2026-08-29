#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
WORK=${ANALYSIS_WORKSPACE:-"$ROOT/.analysis-work"}

mkdir -p "$WORK/uv-cache" "$WORK/uv-python"

export UV_CACHE_DIR="$WORK/uv-cache"
export UV_PYTHON_INSTALL_DIR="$WORK/uv-python"

for argument in "$@"; do
  if [ "$argument" = "--offline" ]; then
    export UV_OFFLINE=1
    break
  fi
done

exec uv run \
  --python 3.11.15 \
  --with-requirements "$ROOT/analysis/requirements.lock" \
  python "$ROOT/analysis/pipeline.py" \
  --work-dir "$WORK" \
  "$@"
