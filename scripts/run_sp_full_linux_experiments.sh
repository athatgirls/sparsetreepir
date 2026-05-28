#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-${SPARSETREEPIR_EXPERIMENT_MODE:-full}}"
if [[ "$MODE" != "full" && "$MODE" != "smoke" ]]; then
  echo "usage: bash scripts/run_sp_full_linux_experiments.sh [full|smoke]" >&2
  exit 2
fi

if [[ "${SPARSETREEPIR_WITH_SETUP:-0}" == "1" ]]; then
  bash scripts/setup_linux_experiment_deps.sh
fi
if [[ "${SPARSETREEPIR_WITH_EXTRA_SETUP:-0}" == "1" ]]; then
  bash scripts/setup_linux_extra_backend_sources.sh
fi

if [[ -d "$ROOT/.venv" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
fi

if ! command -v python >/dev/null 2>&1; then
  echo "python not found. Run: bash scripts/setup_linux_experiment_deps.sh" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_TAG="${SPARSETREEPIR_OUT_TAG:-sp_full_linux_${MODE}_${STAMP}}"
EXAMPLE_DIR="$ROOT/examples/$OUT_TAG"
NOTE_DIR="$ROOT/notes/$OUT_TAG"
LOG_DIR="$EXAMPLE_DIR/logs"
LAYOUT_DIR="$EXAMPLE_DIR/layouts"
mkdir -p "$EXAMPLE_DIR" "$NOTE_DIR" "$LOG_DIR" "$LAYOUT_DIR"

exec > >(tee "$LOG_DIR/run.log") 2>&1

echo "=== SparseTreePIR S&P Linux experiment suite ==="
echo "mode=$MODE"
echo "root=$ROOT"
echo "examples=$EXAMPLE_DIR"
echo "notes=$NOTE_DIR"
echo "started_at=$(date -Is)"
echo

if [[ "$MODE" == "smoke" ]]; then
  STRUCT_WORKLOADS="${SPARSETREEPIR_WORKLOADS:-FuelLabs SMT test vectors}"
  STRUCT_HEIGHTS="${SPARSETREEPIR_STRUCTURAL_HEIGHTS:-128}"
  BATCH_SIZES="${SPARSETREEPIR_BATCH_SIZES:-1,8}"
  BACKEND_WORKLOADS="${SPARSETREEPIR_BACKEND_WORKLOADS:-FuelLabs SMT test vectors}"
  BACKEND_SEEDS="${SPARSETREEPIR_BACKEND_SEEDS:-73000}"
  BACKEND_QUERY_SAMPLES="${SPARSETREEPIR_QUERY_SAMPLES:-3}"
  SCALE_HEIGHTS="${SPARSETREEPIR_SCALE_HEIGHTS:-16}"
  SCALE_OCCUPIED="${SPARSETREEPIR_SCALE_OCCUPIED:-64}"
  SCALE_TRIALS="${SPARSETREEPIR_SCALE_TRIALS:-1}"
  EXACT_SETTINGS="${SPARSETREEPIR_EXACT_SETTINGS:-8:0.95}"
  EXACT_TRIALS="${SPARSETREEPIR_EXACT_TRIALS:-1}"
else
  STRUCT_WORKLOADS="${SPARSETREEPIR_WORKLOADS:-all}"
  STRUCT_HEIGHTS="${SPARSETREEPIR_STRUCTURAL_HEIGHTS:-128,256}"
  BATCH_SIZES="${SPARSETREEPIR_BATCH_SIZES:-1,32,128}"
  BACKEND_WORKLOADS="${SPARSETREEPIR_BACKEND_WORKLOADS:-all}"
  BACKEND_SEEDS="${SPARSETREEPIR_BACKEND_SEEDS:-73000,83000,93000}"
  BACKEND_QUERY_SAMPLES="${SPARSETREEPIR_QUERY_SAMPLES:-50}"
  SCALE_HEIGHTS="${SPARSETREEPIR_SCALE_HEIGHTS:-64,128,256}"
  SCALE_OCCUPIED="${SPARSETREEPIR_SCALE_OCCUPIED:-100,1000,10000}"
  SCALE_TRIALS="${SPARSETREEPIR_SCALE_TRIALS:-3}"
  EXACT_SETTINGS="${SPARSETREEPIR_EXACT_SETTINGS:-10:0.98,12:0.99,14:0.995}"
  EXACT_TRIALS="${SPARSETREEPIR_EXACT_TRIALS:-3}"
fi

BACKEND_HEIGHT="${SPARSETREEPIR_BACKEND_HEIGHT:-128}"
BACKENDS="${SPARSETREEPIR_BACKENDS:-simplepir,piano}"
HYBRID_ROUNDS="${SPARSETREEPIR_HYBRID_ROUNDS:-60}"
BALANCE_ROUNDS="${SPARSETREEPIR_BALANCE_ROUNDS:-20}"
SIMPLEPIR_TIMEOUT="${SPARSETREEPIR_SIMPLEPIR_TIMEOUT:-1200}"
PIANO_TIMEOUT="${SPARSETREEPIR_PIANO_TIMEOUT:-300}"
RUN_TREEPIR="${SPARSETREEPIR_RUN_TREEPIR:-auto}"

run_step() {
  local name="$1"
  shift
  echo
  echo "=== step: $name ==="
  "$@" 2>&1 | tee "$LOG_DIR/${name}.log"
}

run_step env bash scripts/collect_linux_experiment_env.sh \
  "$EXAMPLE_DIR/linux_experiment_environment.txt" \
  "$EXAMPLE_DIR/linux_experiment_environment.csv"

run_step structural python scripts/run_real_smt_final_experiment_suite.py \
  --workloads "$STRUCT_WORKLOADS" \
  --heights "$STRUCT_HEIGHTS" \
  --batch-sizes "$BATCH_SIZES" \
  --hybrid-rounds "$HYBRID_ROUNDS" \
  --balance-rounds "$BALANCE_ROUNDS" \
  --layout-dir "$LAYOUT_DIR/structural" \
  --instances-csv "$EXAMPLE_DIR/real_smt_final_suite_instances.csv" \
  --layouts-csv "$EXAMPLE_DIR/real_smt_final_suite_layouts.csv" \
  --proof-csv "$EXAMPLE_DIR/real_smt_final_suite_plain_proofs.csv" \
  --simplepir-csv "$EXAMPLE_DIR/real_smt_final_suite_simplepir.csv" \
  --note "$NOTE_DIR/real_smt_final_suite_note.md"

run_step exact_balance python scripts/run_small_opt_balance_experiment.py \
  --settings "$EXACT_SETTINGS" \
  --trials "$EXACT_TRIALS" \
  --seed-base "${SPARSETREEPIR_EXACT_SEED_BASE:-220000}" \
  --timeout-s "${SPARSETREEPIR_EXACT_TIMEOUT_S:-20}" \
  --output "$EXAMPLE_DIR/small_opt_balance_results.csv"

{
  echo "# Profile Balance Scale Experiment"
  echo
  echo '```text'
  python scripts/run_profile_balance_scale_experiment.py \
    --heights "$SCALE_HEIGHTS" \
    --occupied-counts "$SCALE_OCCUPIED" \
    --distributions "${SPARSETREEPIR_SCALE_DISTRIBUTIONS:-uniform,clustered,adversarial}" \
    --trials "$SCALE_TRIALS" \
    --seed-base "${SPARSETREEPIR_SCALE_SEED_BASE:-26000}" \
    --initial-rounds "${SPARSETREEPIR_SCALE_INITIAL_ROUNDS:-120}" \
    --refine-rounds "${SPARSETREEPIR_SCALE_REFINE_ROUNDS:-20}"
  echo '```'
} 2>&1 | tee "$LOG_DIR/profile_scale.log" > "$NOTE_DIR/profile_balance_scale_experiment_note.md"

if [[ "$RUN_TREEPIR" == "1" || ( "$RUN_TREEPIR" == "auto" && -d "$ROOT/external/TreePIR-main/TreePIR-Indexing" ) ]]; then
  run_step treepir_perfectized python scripts/run_official_treepir_perfectized_baseline.py \
    --output "$EXAMPLE_DIR/official_treepir_perfectized_baseline.csv" \
    --note "$NOTE_DIR/official_treepir_perfectized_baseline_note.md"
else
  {
    echo "# Official TreePIR Perfectized Baseline"
    echo
    echo "Skipped because external/TreePIR-main/TreePIR-Indexing is not present."
    echo "Run \`bash scripts/setup_linux_extra_backend_sources.sh\` and then rerun with \`SPARSETREEPIR_RUN_TREEPIR=1\`."
  } > "$NOTE_DIR/official_treepir_perfectized_baseline_note.md"
fi

run_step backend_repeats python scripts/run_real_backend_showcase_repeats.py \
  --seeds "$BACKEND_SEEDS" \
  --workloads "$BACKEND_WORKLOADS" \
  --height "$BACKEND_HEIGHT" \
  --backends "$BACKENDS" \
  --query-samples "$BACKEND_QUERY_SAMPLES" \
  --hybrid-rounds "$HYBRID_ROUNDS" \
  --balance-rounds "$BALANCE_ROUNDS" \
  --simplepir-timeout "$SIMPLEPIR_TIMEOUT" \
  --piano-timeout "$PIANO_TIMEOUT" \
  --layout-dir "$LAYOUT_DIR/backend_repeats" \
  --output-dir "$EXAMPLE_DIR" \
  --note-dir "$NOTE_DIR" \
  --combined-output "$EXAMPLE_DIR/real_backend_showcase_repeats_seed_rows.csv" \
  --aggregate-output "$EXAMPLE_DIR/real_backend_showcase_repeats_summary.csv" \
  --raw-means-output "$EXAMPLE_DIR/real_backend_showcase_raw_means.csv" \
  --note "$NOTE_DIR/real_backend_showcase_repeats_note.md"

run_step e2e_breakdown python scripts/build_end_to_end_cost_breakdown.py \
  --raw-dir "$EXAMPLE_DIR" \
  --layouts-csv "$EXAMPLE_DIR/real_smt_final_suite_layouts.csv" \
  --breakdown-csv "$EXAMPLE_DIR/end_to_end_cost_breakdown.csv" \
  --paired-csv "$EXAMPLE_DIR/end_to_end_paired_comparison.csv" \
  --note "$NOTE_DIR/end_to_end_cost_breakdown_note.md"

cat > "$NOTE_DIR/run_manifest.md" <<EOF
# S&P Linux Experiment Run Manifest

- Mode: \`$MODE\`
- Started: \`$STAMP\`
- Examples: \`examples/$OUT_TAG\`
- Notes: \`notes/$OUT_TAG\`
- Workloads: \`$STRUCT_WORKLOADS\`
- Structural heights: \`$STRUCT_HEIGHTS\`
- Backend height: \`$BACKEND_HEIGHT\`
- Backend seeds: \`$BACKEND_SEEDS\`
- Backend query samples per seed: \`$BACKEND_QUERY_SAMPLES\`
- Backends: \`$BACKENDS\`
- Scale heights: \`$SCALE_HEIGHTS\`
- Scale occupied counts: \`$SCALE_OCCUPIED\`
- Scale trials per setting: \`$SCALE_TRIALS\`
- Exact-balance settings: \`$EXACT_SETTINGS\`

## Paper-Facing Outputs

- \`examples/$OUT_TAG/real_smt_final_suite_layouts.csv\`
- \`examples/$OUT_TAG/small_opt_balance_results.csv\`
- \`notes/$OUT_TAG/profile_balance_scale_experiment_note.md\`
- \`examples/$OUT_TAG/real_backend_showcase_repeats_summary.csv\`
- \`examples/$OUT_TAG/real_backend_showcase_raw_means.csv\`
- \`examples/$OUT_TAG/end_to_end_paired_comparison.csv\`
- \`notes/$OUT_TAG/end_to_end_cost_breakdown_note.md\`

## Review-Risk Coverage

- TreePIR/pruned/full-layout comparison: \`real_smt_final_suite_layouts.csv\`; optional official TreePIR run in \`official_treepir_perfectized_baseline.csv\`.
- ActiveBalance optimality check: \`small_opt_balance_results.csv\`.
- Scale and distribution sensitivity: \`profile_balance_scale_experiment_note.md\`.
- Paired executable SimplePIR/PIANO backend evidence: \`real_backend_showcase_repeats_*.csv\`.
- End-to-end accounting: \`end_to_end_paired_comparison.csv\`.
EOF

echo
echo "completed_at=$(date -Is)"
echo "manifest=$NOTE_DIR/run_manifest.md"
echo "examples=$EXAMPLE_DIR"
echo "notes=$NOTE_DIR"
