# S&P Linux Experiment Runbook

This runbook is the paper-facing experiment checklist for a Security & Privacy submission. It groups the experiments needed to defend the current SparseTreePIR claims against the main reviewer risks: TreePIR/PBC baselines, ActiveBalance optimality, scale sensitivity, executable PIR backend evidence, and end-to-end accounting.

## 1. Fresh Linux Setup

```bash
git clone https://github.com/athatgirls/sparsetreepir.git
cd sparsetreepir
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

The setup script installs Python dependencies and pinned SimplePIR/PIANO checkouts under `.tools/`.

For the optional official TreePIR artifact baseline:

```bash
bash scripts/setup_linux_extra_backend_sources.sh
```

## 2. Smoke Test

Run this first on a new machine:

```bash
bash scripts/run_sp_full_linux_experiments.sh smoke
```

The smoke run uses the FuelLabs workload, one seed, and a few queries. It checks dependency wiring before the full run.

## 3. Full S&P Experiment Run

```bash
bash scripts/run_sp_full_linux_experiments.sh full
```

Recommended for a full paper table refresh:

```bash
SPARSETREEPIR_WITH_EXTRA_SETUP=1 \
SPARSETREEPIR_RUN_TREEPIR=1 \
bash scripts/run_sp_full_linux_experiments.sh full
```

The script creates timestamped output folders:

- `examples/sp_full_linux_full_<timestamp>/`
- `notes/sp_full_linux_full_<timestamp>/`

The most useful file to open first is `notes/.../run_manifest.md`.

## 4. What the Full Run Covers

1. Real SMT layout suite at heights 128 and 256:
   `real_smt_final_suite_instances.csv`, `real_smt_final_suite_layouts.csv`, and `real_smt_final_suite_plain_proofs.csv`.

2. Exact small-instance ActiveBalance check:
   `small_opt_balance_results.csv`.

3. Scale and distribution sensitivity:
   `profile_balance_scale_experiment_note.md`.

4. Optional official TreePIR perfectized baseline:
   `official_treepir_perfectized_baseline.csv`.

5. Paired executable backend runs:
   SimplePIR and PIANO over PBC-style SMT versus SparseTreePIR, with three seeds and 50 targets per seed by default.

6. End-to-end accounting:
   `end_to_end_cost_breakdown.csv`, `end_to_end_paired_comparison.csv`, and `end_to_end_cost_breakdown_note.md`.

## 5. Useful Overrides

```bash
SPARSETREEPIR_OUT_TAG=linux_server_a_full \
SPARSETREEPIR_BACKEND_SEEDS=73000,83000,93000,103000,113000 \
SPARSETREEPIR_QUERY_SAMPLES=100 \
SPARSETREEPIR_BACKENDS=simplepir,piano \
bash scripts/run_sp_full_linux_experiments.sh full
```

To rerun only a smaller workload mix:

```bash
SPARSETREEPIR_WORKLOADS="FuelLabs SMT test vectors,ZKsync Era broad" \
SPARSETREEPIR_BACKEND_WORKLOADS="FuelLabs SMT test vectors,ZKsync Era broad" \
bash scripts/run_sp_full_linux_experiments.sh full
```

## 6. How to Use Results in the Paper

- Use `real_smt_final_suite_layouts.csv` for Table 3-style layout results.
- Use `real_backend_showcase_repeats_summary.csv` and `real_backend_showcase_raw_means.csv` for Table 4-style backend ratios.
- Use `end_to_end_paired_comparison.csv` for appendix-level end-to-end accounting.
- Use `small_opt_balance_results.csv` and the scale note to defend ActiveBalance against the "just a heuristic" critique.
- Use the optional TreePIR baseline note to defend against the "just TreePIR on a sparse tree" critique.

Keep the generated `examples/<run>/linux_experiment_environment.*` files with the artifact so the paper can report the exact OS, compiler, Go, Java, SimplePIR, and PIANO versions.
