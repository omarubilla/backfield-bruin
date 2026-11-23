#!/usr/bin/env bash
# Starts the read-only Bruin benchmark API on http://127.0.0.1:${PORT:-8787}
set -euo pipefail
cd "$(dirname "$0")/.."
# Local secrets (PFF_API_KEY, CFBD_API_KEY) live in ./.env, which is git-ignored and never printed.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${UV:-}" ]; then
  if uv --version >/dev/null 2>&1; then UV=$(command -v uv); else UV=~/.pyenv/versions/3.10.15/bin/uv; fi
fi
exec "$UV" run --python 3.12 --with fastapi --with "uvicorn[standard]" --with duckdb \
  uvicorn api.bruin_api:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8787}"
