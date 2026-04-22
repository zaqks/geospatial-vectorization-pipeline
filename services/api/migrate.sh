#!/bin/bash
cd "$(dirname "$0")"
PYTHONPATH=. python3 -m src.utils._db
echo db migrations applied!