#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -d "$ROOT/.venv" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

bash scripts/collect_linux_experiment_env.sh

python scripts/run_real_backend_showcase_repeats.py \
  --seeds "${SPARSETREEPIR_SEEDS:-73000,83000,93000}" \
  --workloads "${SPARSETREEPIR_WORKLOADS:-all}" \
  --height "${SPARSETREEPIR_HEIGHT:-128}" \
  --backends "${SPARSETREEPIR_BACKENDS:-simplepir,piano}" \
  --query-samples "${SPARSETREEPIR_QUERY_SAMPLES:-50}" \
  --simplepir-timeout "${SPARSETREEPIR_SIMPLEPIR_TIMEOUT:-1200}" \
  --piano-timeout "${SPARSETREEPIR_PIANO_TIMEOUT:-300}"
