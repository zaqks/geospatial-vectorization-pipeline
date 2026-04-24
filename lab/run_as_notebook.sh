#!/usr/bin/env bash

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 script.py"
  exit 1
fi

INPUT="$1"

BASENAME=$(basename "$INPUT")
NAME="${BASENAME%.py}"

OUTPUT_DIR=".ipynb_runs"
mkdir -p "$OUTPUT_DIR"

TMP_IPYNB="$OUTPUT_DIR/${NAME}_tmp.ipynb"
OUTPUT_IPYNB="$OUTPUT_DIR/${NAME}_executed.ipynb"

echo "Converting: $INPUT -> $TMP_IPYNB"
jupytext --to notebook "$INPUT" -o "$TMP_IPYNB"

echo "Running notebook..."
papermill "$TMP_IPYNB" "$OUTPUT_IPYNB"

echo "Cleaning up..."
rm -f "$TMP_IPYNB"

echo "Done: $OUTPUT_IPYNB"