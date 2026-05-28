# SparseTreePIR experiments

This repository contains the SparseTreePIR paper sources, experiment scripts, small workload CSVs, generated result summaries, and Linux setup helpers.

## What is included

- `scripts/`: experiment, plotting, and summarization scripts.
- `datasets/`: small fixed SMT workload CSVs used by the current paper experiments.
- `examples/*.csv`: generated result summaries used by the paper.
- `backend/`: local SimplePIR and PIANO runner adapters copied into external backend checkouts by the Linux setup script.
- `figures/`, `manuscripts/`, `notes/`: paper figures, LaTeX sources, and experiment notes.

Large local toolchains, caches, downloaded zips, and generated layout dumps are intentionally ignored. They should be rebuilt on Linux.

## Linux setup

```bash
git clone <repo-url> sparsetreepir
cd sparsetreepir
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

The setup script installs apt packages when available, creates a Python virtual environment, installs Python dependencies, clones pinned SimplePIR and PIANO checkouts under `.tools/`, and installs the local runner adapters.

## Main experiment commands

Structural and layout suite:

```bash
python scripts/run_real_smt_final_experiment_suite.py
```

SimplePIR backend evidence:

```bash
python scripts/run_real_smt_final_experiment_suite.py --run-simplepir
python scripts/run_real_smt_multi_pir_pbc_battle.py
```

PIANO backend evidence:

```bash
python scripts/run_piano_wsl_backend_from_layouts.py --queries 5 --timeout 300
```

Paper-facing real backend showcase:

```bash
python scripts/run_real_backend_showcase.py --workloads all --height 128 --backends simplepir,piano --query-samples 20
```

This command rebuilds the real SMT workload layouts and compares PBC-SMT
against SparseTreePIR through executable SimplePIR and PIANO runners. It writes
`examples/real_backend_showcase_raw.csv`,
`examples/real_backend_showcase_summary.csv`, and
`notes/real_backend_showcase_note.md`.

Final repeated backend run for paper tables:

```bash
bash scripts/collect_linux_experiment_env.sh
python scripts/run_real_backend_showcase_repeats.py --seeds 73000,83000,93000 --workloads all --height 128 --backends simplepir,piano --query-samples 50
```

Or run the same final checklist through one shell entrypoint:

```bash
bash scripts/run_final_linux_backend_experiments.sh
```

This produces per-seed backend results plus
`examples/real_backend_showcase_repeats_summary.csv` and
`notes/real_backend_showcase_repeats_note.md`. See
`notes/linux_final_backend_runbook.md` for the final Linux checklist.

For details, see `notes/linux_experiment_migration_plan.md`.

## S&P full Linux experiment suite

For a full paper-facing rerun aimed at the IEEE S&P submission, use:

```bash
bash scripts/run_sp_full_linux_experiments.sh smoke
bash scripts/run_sp_full_linux_experiments.sh full
```

The full suite runs the real SMT layout study, exact small-instance
ActiveBalance checks, scale/distribution sensitivity, paired SimplePIR/PIANO
backend repeats, and end-to-end accounting. To include the optional official
TreePIR artifact baseline, run:

```bash
SPARSETREEPIR_WITH_EXTRA_SETUP=1 SPARSETREEPIR_RUN_TREEPIR=1 \
  bash scripts/run_sp_full_linux_experiments.sh full
```

See `notes/sp_full_linux_experiment_runbook.md` for outputs and overrides.

## Backend scope

The Linux setup intentionally installs only the current executable SparseTreePIR
backend integrations: SimplePIR and PIANO. Other backend attempts and artifact
checks are documented separately in `notes/backend_integration_status.md`.

To fetch and inspect additional real backend artifacts on Linux, run:

```bash
bash scripts/setup_linux_extra_backend_sources.sh
python scripts/check_linux_backend_readiness.py
```

See `notes/linux_extra_backend_runbook.md` for the suggested order and scope.
