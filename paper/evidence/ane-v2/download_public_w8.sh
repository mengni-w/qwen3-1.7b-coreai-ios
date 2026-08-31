#!/bin/bash
set -euo pipefail

readonly repository="massif/Qwen3-1.7B-CoreAI-ANE-W8-4K-h16p"
readonly revision="75bbe06906cb5d953e602e3e4fb6364187c81822"
readonly script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

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

# `hf download --local-dir` creates transport metadata at this exact child
# path. It is not part of the immutable model revision or the app resource.
transport_cache="$output/.cache"
if [[ -L "$transport_cache" ]]; then
  echo "refusing a symbolic-link transport cache: $transport_cache" >&2
  exit 66
fi
if [[ -d "$transport_cache" ]]; then
  rm -rf -- "$transport_cache"
fi

python3 "$script_directory/prepare_identity.py" \
  --prepare-artifact-dir "$output"

printf '%s\n' \
  "repository=$repository" \
  "revision=$revision" \
  "output=$output"
