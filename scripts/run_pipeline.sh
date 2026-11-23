#!/usr/bin/env bash
# Runs the Bruin pipeline and records execution status for the benchmark export.
#   scripts/run_pipeline.sh            -> logs/bruin_run_latest.log + logs/bruin_run_latest.json
#   CFBD_API_KEY=... scripts/run_pipeline.sh   (optional; enables the CFBD provider)
set -uo pipefail
cd "$(dirname "$0")/.."
# Local secrets (PFF_API_KEY, CFBD_API_KEY) live in ./.env, which is git-ignored and never printed.
if [ -f .env ]; then set -a; . ./.env; set +a; fi
BRUIN="${BRUIN_BIN:-$(command -v bruin || echo ~/.local/bin/bruin)}"
if [ -z "${UV:-}" ]; then
  if uv --version >/dev/null 2>&1; then UV=$(command -v uv); else UV=~/.pyenv/versions/3.10.15/bin/uv; fi
fi
export PATH="$(dirname "$UV"):$PATH"
mkdir -p logs
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$BRUIN" run pipeline > logs/bruin_run_latest.log 2>&1
EXIT=$?
FINISHED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$UV" run --python 3.12 --with duckdb python -m bruin_export.run_status \
  --log logs/bruin_run_latest.log --exit "$EXIT" --started "$STARTED" --finished "$FINISHED" \
  --bruin-version "$("$BRUIN" --version 2>/dev/null | head -1)" --out logs/bruin_run_latest.json
tail -12 logs/bruin_run_latest.log
exit $EXIT
