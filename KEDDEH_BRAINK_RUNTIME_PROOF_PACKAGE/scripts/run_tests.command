#!/bin/bash
# Run the BrAInK runtime proof test suite.
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PACKAGE_ROOT"

PYTHON="${PYTHON:-python3}"

echo "== BrAInK runtime :: test suite =="
echo "package root : $PACKAGE_ROOT"
echo "interpreter  : $($PYTHON --version 2>&1)"
echo

if ! "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
    echo "pytest is not installed. Install it with:  $PYTHON -m pip install pytest" >&2
    exit 2
fi

PYTHONPATH="$PACKAGE_ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
    "$PYTHON" -m pytest tests/ -v
