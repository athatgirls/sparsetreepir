# Linux runbook for additional backend artifacts

This runbook prepares the Linux machine for backend artifacts beyond the two
current SparseTreePIR integrations, SimplePIR and PIANO.

## 1. Fetch extra backend sources

```bash
git pull
bash scripts/setup_linux_extra_backend_sources.sh
python scripts/check_linux_backend_readiness.py
```

The setup script fetches pinned checkouts for:

- TreePIR artifact: `https://github.com/PIR-PIXR/TreePIR.git`
- Spiral: `https://github.com/menonsamir/spiral.git`
- YPIR: `https://github.com/menonsamir/ypir.git`
- VBPIR: `https://github.com/mhmughees/vectorized_batchpir.git`
- SealPIR: `https://github.com/microsoft/SealPIR.git`

The downloaded repositories stay under `external/` or `.tools/` and are not
committed to Git.

## 2. Light artifact check: TreePIR indexing

```bash
python scripts/run_official_treepir_perfectized_baseline.py
```

This reruns the official TreePIR Java indexing path on perfect-tree baselines.
It is useful for reproducing the paper's claim that the bottleneck is the SMT
PIR-facing object, not TreePIR's indexing speed.

## 3. TreePIR artifact routes

The TreePIR artifact includes PBC, Spiral, VBPIR, and SealPIRplus routes. These
are useful prior-art artifact checks, but they are not yet full SparseTreePIR
backend integrations.

Recommended order on Linux:

1. Run TreePIR indexing first.
2. Try VBPIR/PBC builds from `external/TreePIR-main/VBPIR_PBC`,
   `external/TreePIR-main/VBPIR_TreePIR`, and `external/TreePIR-main/PBC`.
3. Try TreePIR's Spiral Docker route under `external/TreePIR-main/Spiral`.
4. Treat SealPIRplus as a heavier service setup requiring SEAL, gRPC, Protobuf,
   server/client binaries, and the orchestrator.

## 4. YPIR

Before trying YPIR, check CPU support:

```bash
lscpu | grep -i avx512
```

If there is no AVX-512 flag, do not spend time on YPIR on that machine.

## 5. What these results can support

Use these runs as artifact and backend-compatibility evidence. Do not claim that
SparseTreePIR has a finished production integration with Spiral, YPIR, VBPIR, or
SealPIRplus until we add backend-specific exporters from active color stores to
each backend's database/query format.
