#!/usr/bin/env bash
# Usage: ./run.sh [cpu ...]   (default: 0)
set -e
cd "$(dirname "$0")"
python3 gen.py .
gcc -O2 -o bench bench.c kernels.S
for c in "${@:-0}"; do
    echo "== cpu $c"
    ./bench "$c"
done
