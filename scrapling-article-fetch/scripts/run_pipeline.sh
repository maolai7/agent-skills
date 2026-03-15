#!/usr/bin/env bash
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo 'Python not found' >&2
  exit 1
fi

"$PYTHON_BIN" ~/.openclaw/skills/scrapling-article-fetch/scripts/check_python_env.py
