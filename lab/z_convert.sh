#!/bin/bash
set -e

for f in *.py; do
  jupytext --to ipynb "$f"
done
