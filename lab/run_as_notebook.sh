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

TMP_IPYNB="./${NAME}_tmp.ipynb"
OUTPUT_IPYNB="$OUTPUT_DIR/${NAME}_executed.ipynb"

KERNEL_NAME="python3"

echo "Converting: $INPUT -> $TMP_IPYNB"
jupytext --to notebook "$INPUT" -o "$TMP_IPYNB"

echo "Injecting kernel: $KERNEL_NAME"
python - <<EOF
import json

path = "$TMP_IPYNB"

with open(path, "r") as f:
    nb = json.load(f)

nb.setdefault("metadata", {})
nb["metadata"]["kernelspec"] = {
    "name": "$KERNEL_NAME",
    "display_name": "Python 3"
}

with open(path, "w") as f:
    json.dump(nb, f)
EOF

echo "Running notebook..."
papermill "$TMP_IPYNB" "$OUTPUT_IPYNB" -k "$KERNEL_NAME"

echo "Cleaning up..."
rm -f "$TMP_IPYNB"

echo "Done: $OUTPUT_IPYNB"