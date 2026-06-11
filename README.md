# SparseTreePIR

**SparseTreePIR: Batch Private Retrieval of Sparse Merkle Proofs via Interval
Coloring**

This repository contains the anonymized artifact for SparseTreePIR. It includes
the layout construction code, workload data, backend adapters, plotting scripts,
and checked-in result summaries used by the paper.

## Abstract

Sparse Merkle Trees (SMTs) provide compact membership proofs for sparse state,
but a standard proof request reveals both the queried coordinate and the
authentication path to the server. SparseTreePIR studies target-private
retrieval of occupied-leaf membership proofs for a fixed public snapshot: the
server may know the snapshot layout, but it should not learn which occupied leaf
the client checks.

SparseTreePIR is a PIR-based database layout for this task. Instead of storing a
full logical tree, or keeping one searchable slot per proof level after pruning
default hashes, SparseTreePIR stores only non-default sibling digests that can
appear in membership proofs for occupied leaves. Each stored digest is mapped to
the interval of occupied leaves whose proofs require it. Coloring this interval
family gives a fixed one-query-per-color schedule: the client sends one PIR
query to every color subdatabase, uses dummy queries for colors that are not
needed, and locally reconstructs a standard height-`h` SMT proof with public
default hashes.

On six SMT workloads, SparseTreePIR reduces the retrieval width to 9--17 for
height-128 and height-256 proofs. Compared with height-preserving pruned
TreePIR, it uses fewer queries and searches smaller maximum subdatabases. With
SimplePIR and PIANO, the same layout improves online communication over the PBC
baseline without changing the underlying PIR primitives.

## Repository layout

```text
backend/     SimplePIR and PIANO adapter code used by the Linux runners
datasets/    fixed workload CSVs used in the paper experiments
docs/        result map, backend notes, and anonymization notes
examples/    checked-in result summaries and paper-facing CSV outputs
figures/     generated paper figures
scripts/     layout construction, balancing, backend, and plotting scripts
```

The artifact intentionally omits manuscript drafts, local toolchain checkouts,
large generated layout dumps, cache directories, and machine-local notes.

## Experimental setup

The structural experiments require only Python. The full backend experiments are
intended for Linux and use SimplePIR and PIANO through the adapter code in
`backend/`.

The paper run used Ubuntu 22.04.5 with Python 3.10.12, Go 1.18.1, GCC/G++ 11.4,
and CMake 3.22. Other recent Linux environments should reproduce the structural
results exactly and the timing results up to normal machine-level variation.

## Workloads

The input workload CSVs are in `datasets/`:

- `fuel_smt_test_workload.csv`
- `polygon_zkevm_account_leaf_workload.csv`
- `polygon_zkevm_account_leaf_workload_multiwindow.csv`
- `polygon_zkevm_account_leaf_workload_broad_multiwindow.csv`
- `zksync_era_account_leaf_workload_sample.csv`
- `zksync_era_account_leaf_workload_broad_sample.csv`

These are reproducible account-key snapshots and SMT test-vector workloads. They
are used to evaluate the retrieval layouts induced by realistic SMT key
distributions; they are not full archival state-tree dumps.

## Installing dependencies

For the Python-only structural experiments:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For the Linux backend experiments:

```bash
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

The setup script prepares the Python environment and fetches/builds the backend
dependencies needed by the SimplePIR and PIANO runners.

## Running the structural experiments

The following command rebuilds the main layout tables: active proof records,
retrieval widths, pruned TreePIR baselines, PBC baselines, unpartitioned
active-record baselines, SparseTreePIR subdatabase sizes, and construction
times.

```bash
python scripts/run_real_smt_final_experiment_suite.py \
  --workloads all \
  --heights 128,256 \
  --instances-csv examples/reproduce_instances.csv \
  --layouts-csv examples/reproduce_layouts.csv \
  --proof-csv examples/reproduce_plain_proofs.csv \
  --simplepir-csv examples/reproduce_simplepir_accounting.csv
```

The checked-in reference outputs are under:

```text
examples/sp_full_linux_full_latest/
```

## Running the backend experiments

To run the complete Linux artifact pipeline:

```bash
bash scripts/run_sp_full_linux_experiments.sh smoke
bash scripts/run_sp_full_linux_experiments.sh full
```

`smoke` checks the pipeline on small settings. `full` rebuilds the paper-facing
structural suite, ActiveBalance checks, scale/deployment experiments, and
repeated SimplePIR/PIANO backend measurements.

To run only the repeated SimplePIR/PIANO measurements:

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

## Running the PBC baseline

The PBC baseline uses the same active proof records as SparseTreePIR. It stores
three copies over `ceil(1.5m)` buckets and uses Cuckoo assignment for requested
proof batches.

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --output-dir examples/treepir_pbc_active_linux
```

After `scripts/setup_linux_experiment_deps.sh`, add `--run-simplepir` to execute
the generated PBC manifests through the SimplePIR bridge.

Checked-in Linux summaries are under:

```text
examples/treepir_pbc_active_linux_latest/
```

## Performance summary

The checked-in paper run gives the following headline values:

- SparseTreePIR retrieval width is 9--17 for height-128 and height-256
  workloads.
- Compared with height-preserving pruned TreePIR, SparseTreePIR uses
  7.53x--14.22x fewer queries at height 128 and 15.06x--28.44x fewer queries at
  height 256.
- At height 128, SparseTreePIR has a 1.74x--3.33x smaller largest searched
  subdatabase than height-preserving pruned TreePIR.
- Compared with flat active-record retrieval, SparseTreePIR reduces online
  communication by 2.76x--4.08x.
- Compared with the PBC baseline, SparseTreePIR reduces online communication by
  2.21x with SimplePIR and 2.35x with PIANO in the checked-in Linux run.

The main result files are:

```text
examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv
examples/sp_full_linux_full_latest/real_backend_showcase_raw_means.csv
examples/sp_full_linux_full_latest/real_backend_showcase_repeats_summary.csv
examples/sp_full_linux_full_latest/end_to_end_cost_breakdown.csv
examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv
```

See `ARTIFACT.md` for step-by-step reproduction recipes and `docs/RESULTS.md`
for the mapping from paper claims to files and commands.

## Anonymity

This artifact is prepared for anonymous review. It contains no author names,
institution names, private repository URLs, local user paths, or manuscript
drafts. See `docs/ANONYMIZATION.md`.
