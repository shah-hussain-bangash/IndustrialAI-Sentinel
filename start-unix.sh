#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock.txt
pnpm install --frozen-lockfile
pnpm build
printf '\nOpen http://127.0.0.1:8127 . Press Ctrl+C to stop.\n'
.venv/bin/python scripts/run.py
