#!/usr/bin/env bash

set -e  # stop on error

if [ -z "$1" ]; then
  echo "Usage: $0 notebook.ipynb"
  exit 1
fi

INPUT="$1"

# Extract filename without path
BASENAME=$(basename "$INPUT")
NAME="${BASENAME%.ipynb}"

# Create results directory if needed
OUTPUT_DIR=".ipynb_results"
mkdir -p "$OUTPUT_DIR"

# Output file path
OUTPUT="$OUTPUT_DIR/${NAME}_executed.ipynb"

echo "Running notebook: $INPUT"
echo "Saving result to: $OUTPUT"

papermill "$INPUT" "$OUTPUT"

echo "Done."
