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

For details, see `notes/linux_experiment_migration_plan.md`.

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
