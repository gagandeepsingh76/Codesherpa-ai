#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/dev_start.py "$@"
fi

if command -v python >/dev/null 2>&1; then
  exec python scripts/dev_start.py "$@"
fi

echo "Python 3.11+ was not found on PATH. Install Python, then rerun ./start-dev.sh." >&2
exit 1
