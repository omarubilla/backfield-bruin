#!/usr/bin/env bash
# Pulls assessments accepted by the deployed ingest API (Modal volume) into data/landing/assessments/
# so the next `bruin run` ingests them into bronze.live_assessments.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -z "${MODAL:-}" ]; then
  if modal --version >/dev/null 2>&1; then MODAL=$(command -v modal); else MODAL=~/.pyenv/versions/3.10.15/bin/modal; fi
fi
mkdir -p data/landing
"$MODAL" volume get backfield-bruin-assessments /assessments data/landing --force
ls data/landing/assessments | wc -l | xargs echo "assessment records:"
