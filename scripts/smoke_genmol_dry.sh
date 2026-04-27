#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv/bin/python. Create the repo virtualenv first:" >&2
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'" >&2
  exit 1
fi

RUN_DIR="${1:-artifacts/smoke_dry}"

echo "Running dry GenMol smoke test into: $RUN_DIR"
.venv/bin/python -m pz_agent.cli run configs/phenothiazine_genmol_auto_loop_dry.yaml --run-dir "$RUN_DIR"

echo
echo "Key artifacts:"
echo "  $RUN_DIR/generation_iteration_loop_summary.json"
echo "  $RUN_DIR/report.json"
echo "  $RUN_DIR/state_snapshot.json"
