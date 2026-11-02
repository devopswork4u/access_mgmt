#!/usr/bin/env bash
# Usage: ./startup.sh [--setup]
# Dry-run is the default. Set AURORA_HOST to explicitly enable live provisioning.
set -e
cd "$(dirname "$0")"

if [ -x ./.venv/Scripts/python.exe ]; then
  PY=./.venv/Scripts/python.exe
elif [ -x ./.venv/bin/python ]; then
  PY=./.venv/bin/python
elif [ -x ./.venv/bin/python3 ]; then
  PY=./.venv/bin/python3
else
  python3 -m venv .venv
  PY=./.venv/bin/python
fi

if [ "$#" -gt 1 ] || { [ "$#" -eq 1 ] && [ "$1" != "--setup" ]; }; then
  printf 'Usage: ./startup.sh [--setup]\n' >&2
  exit 2
fi

"$PY" -m pip install -q -r requirements.txt

export AURORA_HOST="${AURORA_HOST:-}"
export AURORA_ADMIN_USER="${AURORA_ADMIN_USER:-admin}"
if [ -n "$AURORA_HOST" ] && [ -z "${AURORA_ADMIN_PASSWORD:-}" ]; then
  printf 'AURORA_HOST is set for live provisioning, but AURORA_ADMIN_PASSWORD is missing.\n' >&2
  exit 1
fi

if [ "$#" -eq 1 ]; then
  if [ -z "$AURORA_HOST" ]; then
    printf 'The --setup option requires AURORA_HOST to be set for a live database.\n' >&2
    exit 1
  fi
  "$PY" setup_sample_data.py
fi

exec "$PY" -m streamlit run app.py
