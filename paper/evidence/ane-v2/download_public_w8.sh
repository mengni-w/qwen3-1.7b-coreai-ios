#!/bin/bash
set -euo pipefail

readonly repository="massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p"
readonly revision="466ebe2e5cec125fa113ea71503add41bba581a8"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 OUTPUT_DIRECTORY" >&2
  exit 64
fi

output=$1
if [[ -e "$output" ]]; then
  echo "refusing an existing output path: $output" >&2
  exit 65
fi

hf download "$repository" \
  --revision "$revision" \
  --local-dir "$output"

printf '%s\n' \
  "repository=$repository" \
  "revision=$revision" \
  "output=$output"
