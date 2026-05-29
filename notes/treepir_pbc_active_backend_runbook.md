# TreePIR-compatible PBC active-record backend runbook

This runbook adds the missing "real PBC mechanics" check for SparseTreePIR.
The previous `pbc_smt_active` rows were deterministic balanced accounting
baselines.  They used the same three-copy, `ceil(1.5m)` bucket resource profile
as TreePIR's PBC foil, but they did not perform per-request Cuckoo assignment
or expose Cuckoo failures.

`scripts/run_treepir_pbc_active_backend.py` keeps the SparseTreePIR active
proof-record universe but applies the PBC mechanics used by the TreePIR
artifact:

- three candidate buckets per active proof record;
- `ceil(1.5m)` PBC buckets for active width `m`;
- three replicated server-side copies;
- per-target Cuckoo assignment for the fixed-size active batch;
- dummy padding when a target proof needs fewer than `m` active records;
- failure accounting under a 500-attempt Cuckoo insertion limit;
- optional execution through the existing SimplePIR manifest runner.

This is not the unmodified TreePIR `PBC/` entry point, because that executable
is hard-wired to complete-tree Merkle paths.  Instead, the script adapts the
same PBC bucket and Cuckoo mechanics to SparseTreePIR's active proof-record
batches.

## Manifest-only smoke test

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads "FuelLabs SMT test vectors" \
  --heights 128 \
  --seeds 73000 \
  --queries 50 \
  --output-dir examples/treepir_pbc_active_smoke
```

This writes:

- `manifest.json` files that can be consumed by `backend/simplepir/smt_full_backend.go`;
- `treepir_pbc_active_manifest_summary.csv` with bucket sizes, replicated
  record counts, Cuckoo failures, and Cuckoo assignment time.

## Full Linux PBC mechanics run

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --output-dir examples/treepir_pbc_active_linux
```

## Full Linux run with SimplePIR backend

Run the normal Linux dependency setup first:

```bash
bash scripts/setup_linux_experiment_deps.sh
```

Then run the PBC active-record baseline through the same SimplePIR bridge used
for SparseTreePIR:

```bash
python scripts/run_treepir_pbc_active_backend.py \
  --workloads all \
  --heights 128 \
  --seeds 73000,83000,93000 \
  --queries 50 \
  --output-dir examples/treepir_pbc_active_linux \
  --run-simplepir \
  --simplepir-root external/simplepir \
  --go-exe external/go/bin/go \
  --timeout 1200
```

The backend run additionally writes
`treepir_pbc_active_simplepir_summary.csv`, with setup, online communication,
server answer, and decode timings reported by the SimplePIR runner.

## Interpretation

Use this run when the paper needs to compare against a PBC baseline without the
weaker "balanced accounting" caveat.  The manifest rows report actual Cuckoo
assignment failures and actual hash-induced bucket sizes.  After the Linux run
completes, compare `treepir_pbc_active_simplepir_summary.csv` against the
existing SparseTreePIR SimplePIR rows from the repeated backend run.
