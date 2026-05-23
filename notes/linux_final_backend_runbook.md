# Linux Final Backend Runbook

This is the final checklist for the paper-facing real-data backend experiment.
It assumes the repository has already been cloned on the Linux machine.

## 1. Sync and setup

```bash
git pull
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

## 2. Record the machine and backend versions

```bash
bash scripts/collect_linux_experiment_env.sh
```

This writes:

- `examples/linux_experiment_environment.txt`
- `examples/linux_experiment_environment.csv`

Commit these files with the experiment results so the paper can report the
hardware, OS, toolchain versions, and backend commits.

## 3. Run the repeated real-backend experiment

The one-command route is:

```bash
bash scripts/run_final_linux_backend_experiments.sh
```

The explicit route is:

```bash
python scripts/run_real_backend_showcase_repeats.py \
  --seeds 73000,83000,93000 \
  --workloads all \
  --height 128 \
  --backends simplepir,piano \
  --query-samples 50
```

This runs the same real SMT workloads through the executable SimplePIR and
PIANO runners, comparing `PBC-SMT` against `SparseTreePIR`.

Main outputs:

- `examples/real_backend_showcase_seed1_raw.csv`
- `examples/real_backend_showcase_seed1_summary.csv`
- `examples/real_backend_showcase_seed2_raw.csv`
- `examples/real_backend_showcase_seed2_summary.csv`
- `examples/real_backend_showcase_seed3_raw.csv`
- `examples/real_backend_showcase_seed3_summary.csv`
- `examples/real_backend_showcase_repeats_seed_rows.csv`
- `examples/real_backend_showcase_repeats_summary.csv`
- `notes/real_backend_showcase_repeats_note.md`

The repeated summary is the table to use for the main paper. The per-seed
tables are artifact support.

## 4. Optional: aggregate existing seed files only

If the backend runs already completed and only aggregation needs to be redone:

```bash
python scripts/run_real_backend_showcase_repeats.py \
  --seeds 73000,83000,93000 \
  --skip-runs
```

## 5. Optional: larger workload stress test

The current main workload set is enough for the paper. If time remains, run a
larger fetched workload as an appendix stress test, preferably with PIANO first
because it is faster than SimplePIR for large bucket vectors.

The stress-test result should be described as supplementary, not as a
replacement for the six-workload main table.

## 6. Push results back

```bash
git status
git add examples/real_backend_showcase_seed*_raw.csv \
  examples/real_backend_showcase_seed*_summary.csv \
  examples/real_backend_showcase_repeats_seed_rows.csv \
  examples/real_backend_showcase_repeats_summary.csv \
  examples/linux_experiment_environment.txt \
  examples/linux_experiment_environment.csv \
  notes/real_backend_showcase_seed*_note.md \
  notes/real_backend_showcase_repeats_note.md
git commit -m "Add repeated real backend showcase results"
git push origin main
```

After pushing, ask Codex to inspect the new commit and decide which rows should
be promoted into the paper tables.
