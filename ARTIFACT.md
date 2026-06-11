# SparseTreePIR Artifact Guide

This guide gives a reviewer-oriented path for reproducing the main
SparseTreePIR results. The repository is organized so that the quick
Python-only checks can be run first, and the backend experiments can be run on a
Linux machine when more time is available.

## What the artifact supports

The artifact supports five paper claims.

1. **Minimal retrieval database.** SparseTreePIR stores the non-default sibling
   digests that can appear in occupied-leaf SMT membership proofs. Public
   default proof entries are reconstructed locally.
2. **Interval coloring.** Each stored digest is associated with the interval of
   occupied target leaves whose proofs require it. Coloring this interval family
   gives one real proof record per color subdatabase.
3. **Pruning alone is not enough.** Height-preserving pruned TreePIR removes
   default payloads but keeps a height-`h` query schedule.
4. **ActiveBalance.** Subtree recoloring reduces the maximum color subdatabase
   size while preserving the same retrieval width.
5. **Backend evidence.** SimplePIR and PIANO see lower online communication
   under SparseTreePIR than under the PBC baseline.

## Level 0: inspect checked-in outputs

The final checked-in Linux run is in:

```text
examples/sp_full_linux_full_latest/
```

The latest checked-in PBC baseline summaries are in:

```text
examples/treepir_pbc_active_linux_latest/
```

The most useful files are:

```text
examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv
examples/sp_full_linux_full_latest/real_backend_showcase_raw_means.csv
examples/sp_full_linux_full_latest/real_backend_showcase_repeats_summary.csv
examples/sp_full_linux_full_latest/end_to_end_cost_breakdown.csv
examples/sp_full_linux_full_latest/end_to_end_paired_comparison.csv
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_manifest_summary.csv
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv
```

`docs/RESULTS.md` maps these files to the paper tables and headline claims.

## Level 1: structural layout results

Runtime: seconds to minutes on a laptop.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/run_real_smt_final_experiment_suite.py \
  --workloads all \
  --heights 128,256 \
  --instances-csv examples/reproduce_instances.csv \
  --layouts-csv examples/reproduce_layouts.csv \
  --proof-csv examples/reproduce_plain_proofs.csv \
  --simplepir-csv examples/reproduce_simplepir_accounting.csv
```

Expected outputs:

```text
examples/reproduce_instances.csv
examples/reproduce_layouts.csv
examples/reproduce_plain_proofs.csv
examples/reproduce_simplepir_accounting.csv
```

Compare them with:

```text
examples/sp_full_linux_full_latest/real_smt_final_suite_instances.csv
examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv
examples/sp_full_linux_full_latest/real_smt_final_suite_plain_proofs.csv
examples/sp_full_linux_full_latest/real_smt_final_suite_simplepir.csv
```

This level reproduces the layout profile: active proof records, retrieval width,
height-preserving pruned TreePIR, PBC, flat active-record retrieval, and
SparseTreePIR maximum subdatabase sizes.

## Level 2: ActiveBalance checks

Small exact instances:

```bash
python scripts/run_small_opt_balance_experiment.py \
  --settings 10:0.98,12:0.99,14:0.995 \
  --trials 3 \
  --output examples/reproduce_small_opt_balance_results.csv
```

Scale and distribution sensitivity:

```bash
python scripts/run_profile_balance_scale_experiment.py \
  --heights 64,128,256 \
  --occupied-counts 100,1000,10000 \
  --distributions uniform,clustered,adversarial \
  --trials 3
```

The checked-in reference outputs are:

```text
examples/sp_full_linux_full_latest/small_opt_balance_results.csv
examples/sp_full_linux_full_latest/deployment_scale_snapshot_summary.csv
```

## Level 3: SimplePIR and PIANO backend runs

Install backend dependencies:

```bash
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

Run the full Linux suite:

```bash
bash scripts/run_sp_full_linux_experiments.sh smoke
bash scripts/run_sp_full_linux_experiments.sh full
```

Run only the repeated backend measurements:

```bash
python scripts/run_real_backend_showcase_repeats.py \
  --seeds 73000,83000,93000 \
  --workloads all \
  --height 128 \
  --backends simplepir,piano \
  --query-samples 50 \
  --output-dir examples/reproduce_backend_repeats \
  --combined-output examples/reproduce_backend_seed_rows.csv \
  --aggregate-output examples/reproduce_backend_summary.csv \
  --raw-means-output examples/reproduce_backend_raw_means.csv
```

Timing values can vary across machines. Communication and structural layout
metrics should be stable for fixed inputs and backend parameter tiers.

## Level 4: PBC baseline with SimplePIR

The PBC baseline uses the same active proof records as SparseTreePIR.

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --run-simplepir \
  --output-dir examples/reproduce_treepir_pbc_active
```

Reference summaries:

```text
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_manifest_summary.csv
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv
```

## Expected headline values

The checked-in paper run gives:

- Retrieval width: 9--17 for height-128 and height-256 workloads.
- Compared with height-preserving pruned TreePIR:
  - 7.53x--14.22x fewer queries at height 128.
  - 15.06x--28.44x fewer queries at height 256.
  - 1.74x--3.33x smaller largest searched subdatabase at height 128.
- Compared with flat active-record retrieval:
  - 2.76x--4.08x lower online communication.
- Compared with the PBC baseline:
  - 2.21x lower SimplePIR online communication.
  - 2.35x lower PIANO online communication.

## Regenerating figures

Final generated figures are in `figures/`. They can be regenerated with:

```bash
python scripts/plot_sparsetreepir_concept_figures.py
python scripts/plot_sparsetreepir_additional_figures.py
python scripts/plot_treepir_style_backend_advantage_overview.py
```

## Clean-room notes

The artifact is self-contained except for backend dependencies fetched by
`scripts/setup_linux_experiment_deps.sh`. Generated toolchains and large layout
dumps are intentionally excluded from version control.
