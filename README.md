# SparseTreePIR

This repository contains the anonymized research artifact for
**SparseTreePIR: Batch Private Retrieval of Sparse Merkle Proofs via
Interval Coloring**.

SparseTreePIR is a PIR-aware database layout for target-private retrieval of
Sparse Merkle Tree (SMT) membership proofs.  The verifier still receives a
standard height-`h` SMT proof, but the PIR backend stores and retrieves only the
non-default sibling digests that cannot be reconstructed from the public
default-hash chain.  Each such digest is associated with an interval of
occupied target leaves.  Coloring these intervals gives a fixed
one-query-per-color retrieval schedule with dummy queries for unused colors.

## Repository contents

- `scripts/`: experiment drivers, layout construction, balancing, plotting, and
  backend runners.
- `backend/`: adapter code copied into SimplePIR and PIANO checkouts by the
  Linux setup script.
- `datasets/`: fixed workload CSVs used in the paper experiments.
- `examples/`: checked-in result summaries used by the paper tables and plots.
- `figures/`: generated paper-facing figures.
- `docs/`: artifact guide, result map, and anonymization notes.

The repository intentionally omits local toolchain checkouts, generated layout
dumps, cache directories, and manuscript drafts.

## Quick start

The structural experiments require only Python.

```bash
git clone <anonymous-repository-url> sparsetreepir
cd sparsetreepir
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

This recomputes the layout-level results: active proof records, retrieval
widths, pruned TreePIR baselines, PBC baselines, unpartitioned active-record
baselines, SparseTreePIR subdatabase sizes, and layout construction times.

## Full Linux artifact run

The full backend experiments use existing PIR systems and are intended for a
Linux machine.  The paper run used Ubuntu 22.04.5, Python 3.10.12, Go 1.18.1,
GCC/G++ 11.4, and CMake 3.22.

```bash
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
bash scripts/run_sp_full_linux_experiments.sh smoke
bash scripts/run_sp_full_linux_experiments.sh full
```

The `smoke` mode checks the pipeline on small settings.  The `full` mode
rebuilds the paper-facing structural suite, ActiveBalance checks,
scale/deployment stress tests, and repeated SimplePIR/PIANO backend runs.

The final checked-in run is under:

```text
examples/sp_full_linux_full_latest/
```

## PBC backend run

The PBC baseline uses the same active proof records as SparseTreePIR, stores
three copies over `ceil(1.5m)` buckets, and uses Cuckoo assignment for requested
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
the generated PBC manifests through the same SimplePIR bridge.

The checked-in Linux PBC result summaries are under:

```text
examples/treepir_pbc_active_linux_latest/
```

## Main paper outputs

The most important checked-in result files are:

- `examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv`
- `examples/sp_full_linux_full_latest/real_backend_showcase_raw_means.csv`
- `examples/sp_full_linux_full_latest/real_backend_showcase_repeats_summary.csv`
- `examples/sp_full_linux_full_latest/end_to_end_cost_breakdown.csv`
- `examples/sp_full_linux_full_latest/deployment_scale_snapshot_summary.csv`
- `examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv`

See `ARTIFACT.md` and `docs/RESULTS.md` for the mapping from commands and CSV
files to paper claims.

## Backend scope

The primary executable backend evidence uses SimplePIR and PIANO.  Additional
PIR backends can be installed for exploratory checks, but they are not required
to reproduce the main paper tables.

## Anonymity

This artifact is prepared for anonymous review.  It contains no author names,
institution names, private repository URLs, local user paths, or manuscript
drafts.  See `docs/ANONYMIZATION.md`.
