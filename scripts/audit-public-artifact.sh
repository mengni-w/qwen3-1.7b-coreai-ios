#!/bin/sh

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <artifact-directory>" >&2
  exit 2
fi

artifact_directory=$1

if [ ! -d "$artifact_directory" ]; then
  echo "artifact directory does not exist: $artifact_directory" >&2
  exit 2
fi

if ! command -v rg >/dev/null 2>&1; then
  echo "ripgrep (rg) is required" >&2
  exit 2
fi

forbidden_pattern='/Users/|/home/|[A-Za-z]:\\Users\\'
if [ -n "${COREAI_PUBLIC_FORBIDDEN_PATTERN:-}" ]; then
  forbidden_pattern="$forbidden_pattern|$COREAI_PUBLIC_FORBIDDEN_PATTERN"
fi

matches=$(mktemp)
trap 'rm -f "$matches"' EXIT HUP INT TERM

if (
  cd "$artifact_directory"
  LC_ALL=C rg -a -l -- "$forbidden_pattern" .
) >"$matches"; then
  echo "public artifact audit failed: embedded local identifiers were found" >&2
  sed 's/^/  /' "$matches" >&2
  echo "rebuild from a neutral path; do not patch the generated binary" >&2
  exit 1
fi

echo "public artifact audit passed: $artifact_directory"
