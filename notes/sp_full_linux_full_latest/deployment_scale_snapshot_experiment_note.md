# Deployment-Scale Snapshot Experiment

This experiment addresses the S&P reviewer risk that the paper only measures small fixed snapshots. It constructs dynamic, real-trace-seeded SMT snapshots, runs SparseTreePIR layout construction at deployment-scale occupied-leaf counts, and records the full snapshot-side cost needed before pairing with the executable backend experiments.

## Configuration

- Workloads: `Polygon zkEVM broad,ZKsync Era broad`
- Heights: `128`
- Target occupied leaves: `1000,10000,100000`
- Epochs per setting: `3`
- Churn per epoch after epoch 0: `0.05`
- Prefix bits preserved for trace bootstrapping: `24`
- Coloring strategy: `hybrid`
- Coloring/refinement rounds: `60`

## Paper-Facing Summary

| Dataset | h | occupied | mode | strategy | epochs | width gain | stored-record gain | max-bucket gain | build ms | coloring ms | peak MB |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| Polygon zkEVM broad | 128 | 1000 | real-trace-exact | hybrid | 3/3 | 1.54x | 3.00x | 1.58x | 451.57 | 438.70 | 0.91 |
| Polygon zkEVM broad | 128 | 10000 | real-trace-bootstrapped-prefix24 | hybrid | 3/3 | 1.53x | 3.00x | 1.70x | 38,998.1 | 38,802.4 | 8.87 |
| Polygon zkEVM broad | 128 | 100000 | real-trace-bootstrapped-prefix24 | hybrid | 3/3 | 1.51x | 3.00x | 1.78x | 398,051.4 | 395,707.9 | 89.06 |
| ZKsync Era broad | 128 | 1000 | real-trace-exact | hybrid | 3/3 | 1.50x | 3.00x | 1.66x | 1,729.5 | 1,716.5 | 0.91 |
| ZKsync Era broad | 128 | 10000 | real-trace-bootstrapped-prefix24 | hybrid | 3/3 | 1.50x | 3.00x | 1.63x | 28,821.6 | 28,630.7 | 8.87 |
| ZKsync Era broad | 128 | 100000 | real-trace-bootstrapped-prefix24 | hybrid | 3/3 | 1.52x | 3.00x | 1.74x | 242,605.6 | 240,269.8 | 89.04 |

## How This Should Be Used

- Use this table to support the main-text claim that SparseTreePIR remains structurally useful at deployment-scale snapshot sizes.
- Pair it with `real_backend_showcase_repeats_summary.csv` and `end_to_end_paired_comparison.csv`; this script measures snapshot layout construction, not a replacement for the SimplePIR/PIANO backend runs.
- If a setting is skipped, raise `--max-active-nodes` on a larger Linux machine or lower `--target-counts` for a pilot run.
