# Result Map

This file maps paper-facing claims to artifact files and commands.

## Workloads

Input workload CSVs are in `datasets/`:

- `fuel_smt_test_workload.csv`
- `polygon_zkevm_account_leaf_workload.csv`
- `polygon_zkevm_account_leaf_workload_multiwindow.csv`
- `polygon_zkevm_account_leaf_workload_broad_multiwindow.csv`
- `zksync_era_account_leaf_workload_sample.csv`
- `zksync_era_account_leaf_workload_broad_sample.csv`

These are account-key snapshots and SMT test-vector workloads, not full
archival state-tree dumps.

## Layout table

Paper claim:

- Active proof records are much smaller than complete logical trees.
- SparseTreePIR retrieval width is 9--17.
- Height-preserving pruned TreePIR keeps width `h`.
- PBC and unpartitioned active-record baselines leave structure on the table.

Checked-in file:

```text
examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv
```

Regeneration command:

```bash
python scripts/run_real_smt_final_experiment_suite.py --workloads all --heights 128,256
```

## ActiveBalance

Paper claim:

- ActiveBalance reduces the maximum color subdatabase size without changing the
  retrieval width.

Checked-in files:

```text
examples/sp_full_linux_full_latest/small_opt_balance_results.csv
examples/sp_full_linux_full_latest/deployment_scale_snapshot_summary.csv
```

Regeneration commands:

```bash
python scripts/run_small_opt_balance_experiment.py
python scripts/run_deployment_scale_snapshot_experiment.py
```

## SimplePIR and PIANO backend evidence

Paper claim:

- SparseTreePIR reduces online communication under existing PIR backends.

Checked-in files:

```text
examples/sp_full_linux_full_latest/real_backend_showcase_raw_means.csv
examples/sp_full_linux_full_latest/real_backend_showcase_repeats_summary.csv
examples/sp_full_linux_full_latest/end_to_end_cost_breakdown.csv
examples/sp_full_linux_full_latest/end_to_end_paired_comparison.csv
```

Regeneration command:

```bash
python scripts/run_real_backend_showcase_repeats.py \
  --seeds 73000,83000,93000 \
  --workloads all \
  --height 128 \
  --backends simplepir,piano \
  --query-samples 50
```

## PBC baseline

Paper claim:

- Under SimplePIR, SparseTreePIR has lower online communication than the PBC
  baseline over the same active proof records.

Checked-in files:

```text
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_manifest_summary.csv
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv
```

Regeneration command:

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --run-simplepir
```

## Figures

The final generated figures are in `figures/`.  They can be regenerated with:

```bash
python scripts/plot_sparsetreepir_concept_figures.py
python scripts/plot_sparsetreepir_additional_figures.py
```
