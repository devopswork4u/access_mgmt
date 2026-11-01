#!/usr/bin/env bash
# Usage: ./startup.sh [--setup]   (--setup also creates the sample USTA databases)
set -e
cd "$(dirname "$0")"

PY=./.venv/Scripts/python.exe
[ -x "$PY" ] || PY=./.venv/bin/python3
if [ ! -x "$PY" ]; then
  python3 -m venv .venv
  PY=./.venv/Scripts/python.exe
  [ -x "$PY" ] || PY=./.venv/bin/python
  "$PY" -m pip install -q -r requirements.txt
fi

export AURORA_ADMIN_USER="${AURORA_ADMIN_USER:-admin}"
if [ -z "$AURORA_ADMIN_PASSWORD" ]; then
  read -r -s -p "Aurora password for $AURORA_ADMIN_USER: " AURORA_ADMIN_PASSWORD
  echo
  export AURORA_ADMIN_PASSWORD
fi

"$PY" test_connection.py
[ "$1" = "--setup" ] && "$PY" setup_sample_data.py

"$PY" -m streamlit run app.py
