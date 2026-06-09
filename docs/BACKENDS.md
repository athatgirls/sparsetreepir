# Backend Notes

SparseTreePIR is a database layout.  It does not modify the cryptographic PIR
primitive.  The artifact evaluates the same layout idea using two executable
PIR backends.

## SimplePIR

The SimplePIR bridge materializes 32-byte digest records and invokes the
official Go API for setup, query generation, server answer, and recovery.  The
adapter code is in:

```text
backend/simplepir/smt_full_backend.go
```

The driver scripts generate backend inputs and call this adapter through Go.

## PIANO

The PIANO experiment uses the public PIANO artifact with the subdatabase-size
vector induced by each SparseTreePIR or baseline layout.  The adapter code is
in:

```text
backend/piano/smt_layout_benchmark.go
```

PIANO is used as a secondary backend check; SimplePIR is the main full
digest-retrieval bridge.

## PBC baseline

The PBC baseline uses the same active proof records as SparseTreePIR.  It stores
three replicated copies over `ceil(1.5m)` buckets and uses Cuckoo assignment for
each requested proof batch.

The main driver is:

```text
scripts/run_treepir_pbc_active_backend.py
```

The checked-in Linux summaries are in:

```text
examples/treepir_pbc_active_linux_latest/
```

## Optional backends

The paper does not rely on YPIR, Spiral, SealPIR, or VBPIR as primary evidence.
Those systems require additional platform-specific setup and are outside the
main artifact path.
