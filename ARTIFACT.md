# Artifact Guide

This guide explains how to reproduce the SparseTreePIR paper claims from the
checked-in scripts and result summaries.

## Claims covered by the artifact

1. **SMT-specific retrieval layout.**  SparseTreePIR stores only non-default
   sibling digests that can appear in occupied-leaf membership proofs.
2. **Interval coloring.**  Target-rank intervals allow one real proof record per
   color subdatabase, so retrieval sends one PIR query per color.
3. **Pruning is not enough.**  Height-preserving pruned TreePIR removes default
   payloads but keeps the height-`h` query pattern.
4. **ActiveBalance.**  Subtree recoloring reduces the maximum color
   subdatabase size while preserving retrieval width.
5. **Backend evidence.**  Existing SimplePIR and PIANO runners see lower
   communication under the SparseTreePIR layout than under the PBC baseline.

## Reproduction levels

### Level 1: structural layout results

Runtime: seconds to minutes on a laptop.

```bash
python scripts/run_real_smt_final_experiment_suite.py \
  --workloads all \
  --heights 128,256 \
  --instances-csv examples/reproduce_instances.csv \
  --layouts-csv examples/reproduce_layouts.csv \
  --proof-csv examples/reproduce_plain_proofs.csv \
  --simplepir-csv examples/reproduce_simplepir_accounting.csv
```

Expected outputs:

- `examples/reproduce_instances.csv`
- `examples/reproduce_layouts.csv`
- `examples/reproduce_plain_proofs.csv`
- `examples/reproduce_simplepir_accounting.csv`

Compare these files with:

- `examples/sp_full_linux_full_latest/real_smt_final_suite_instances.csv`
- `examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv`
- `examples/sp_full_linux_full_latest/real_smt_final_suite_plain_proofs.csv`
- `examples/sp_full_linux_full_latest/real_smt_final_suite_simplepir.csv`

### Level 2: ActiveBalance exact and scale checks

```bash
python scripts/run_small_opt_balance_experiment.py \
  --settings 10:0.98,12:0.99,14:0.995 \
  --trials 3 \
  --output examples/reproduce_small_opt_balance_results.csv

python scripts/run_profile_balance_scale_experiment.py \
  --heights 64,128,256 \
  --occupied-counts 100,1000,10000 \
  --distributions uniform,clustered,adversarial \
  --trials 3
```

The first command reproduces the exact small-instance ActiveBalance check.  The
second reports scale and distribution sensitivity to standard output.

### Level 3: executable backend runs

Install dependencies and run the full Linux suite:

```bash
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
bash scripts/run_sp_full_linux_experiments.sh full
```

This produces a timestamped directory under `examples/` and a matching
timestamped directory under `notes/`.  The final checked-in run has been copied
to `examples/sp_full_linux_full_latest/`.

To run only repeated SimplePIR/PIANO backend measurements:

```bash
python scripts/run_real_backend_showcase_repeats.py \
  --seeds 73000,83000,93000 \
  --workloads all \
  --height 128 \
  --backends simplepir,piano \
  --query-samples 50 \
  --output-dir examples/reproduce_backend_repeats \
  --note-dir docs/reproduce_backend_notes \
  --combined-output examples/reproduce_backend_seed_rows.csv \
  --aggregate-output examples/reproduce_backend_summary.csv \
  --raw-means-output examples/reproduce_backend_raw_means.csv
```

### Level 4: PBC baseline with SimplePIR

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --run-simplepir \
  --output-dir examples/reproduce_treepir_pbc_active
```

The corresponding checked-in result summaries are:

- `examples/treepir_pbc_active_linux_latest/treepir_pbc_active_manifest_summary.csv`
- `examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv`

## Expected headline values

The checked-in paper run gives:

- SparseTreePIR retrieval width: 9--17 for height-128 and height-256 workloads.
- Compared with height-preserving pruned TreePIR:
  - 7.53x--14.22x fewer queries at height 128.
  - 15.06x--28.44x fewer queries at height 256.
  - 1.74x--3.33x smaller largest searched subdatabase at height 128.
- Compared with flat active-record retrieval:
  - 2.76x--4.08x lower SimplePIR online communication.
- Compared with the PBC baseline:
  - 2.21x lower SimplePIR online communication.
  - 2.35x lower PIANO online communication.

Small timing differences are expected across machines.  Communication and
structural layout metrics should be stable for fixed inputs and backend
parameter tiers.

## Clean-room notes

The artifact is self-contained except for external backend dependencies fetched
by `scripts/setup_linux_experiment_deps.sh`.  Generated toolchains and layout
dumps are intentionally excluded from version control.
