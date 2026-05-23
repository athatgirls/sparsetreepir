# Multi-PIR Backend PBC-SMT Battle

This experiment compares the same two privacy-preserving organizations on real SMT workloads:

- `PBC-SMT`: generic probabilistic-batch-code style organization over active SMT proof records.
- `SparseTreePIR`: active-interval color stores after ActiveBalance.

The point is not that PBC is a PIR backend. PBC is a batch organization. We therefore compare PBC-SMT and SparseTreePIR under the same backend family whenever possible.

## Backend summary

| Backend | Avg. online reduction | Avg. query-time reduction | Avg. parallel-server reduction |
|---|---:|---:|---:|
| 2server-XOR-PIR-model | 52.7% | 100.0% | 48.6% |
| LWE-PIR-prototype-d64 | 62.3% | 53.5% | 48.1% |
| SimplePIR-full-api | 52.4% | 39.8% | 10.3% |

## Per-workload summary

| Backend | Dataset | h | PBC width | Sparse width | PBC KB | Sparse KB | Online red. |
|---|---|---:|---:|---:|---:|---:|---:|
| 2server-XOR-PIR-model | FuelLabs SMT test vectors | 128 | 14 | 9 | 1.04 | 0.62 | 40.8% |
| 2server-XOR-PIR-model | Polygon zkEVM broad | 128 | 26 | 17 | 11.95 | 4.52 | 62.2% |
| 2server-XOR-PIR-model | Polygon zkEVM multi-window | 128 | 21 | 14 | 3.32 | 1.54 | 53.5% |
| 2server-XOR-PIR-model | Polygon zkEVM recent | 128 | 17 | 11 | 1.63 | 0.88 | 45.9% |
| 2server-XOR-PIR-model | ZKsync Era broad | 128 | 26 | 17 | 13.00 | 4.85 | 62.7% |
| 2server-XOR-PIR-model | ZKsync Era sample | 128 | 20 | 13 | 2.66 | 1.29 | 51.2% |
| LWE-PIR-prototype-d64 | FuelLabs SMT test vectors | 128 | 14 | 9 | 4.07 | 1.90 | 53.4% |
| LWE-PIR-prototype-d64 | Polygon zkEVM broad | 128 | 26 | 17 | 168.23 | 57.12 | 66.0% |
| LWE-PIR-prototype-d64 | Polygon zkEVM multi-window | 128 | 21 | 14 | 34.20 | 12.27 | 64.1% |
| LWE-PIR-prototype-d64 | Polygon zkEVM recent | 128 | 17 | 11 | 11.10 | 4.37 | 60.7% |
| LWE-PIR-prototype-d64 | ZKsync Era broad | 128 | 26 | 17 | 184.63 | 62.59 | 66.1% |
| LWE-PIR-prototype-d64 | ZKsync Era sample | 128 | 20 | 13 | 24.88 | 9.09 | 63.5% |
| SimplePIR-full-api | FuelLabs SMT test vectors | 128 | 14 | 9 | 12.00 | 5.91 | 50.8% |
| SimplePIR-full-api | Polygon zkEVM broad | 128 | 26 | 17 | 133.25 | 62.16 | 53.4% |
| SimplePIR-full-api | Polygon zkEVM multi-window | 128 | 21 | 14 | 51.84 | 25.38 | 51.1% |
| SimplePIR-full-api | Polygon zkEVM recent | 128 | 17 | 11 | 25.50 | 11.69 | 54.2% |
| SimplePIR-full-api | ZKsync Era broad | 128 | 26 | 17 | 138.94 | 65.34 | 53.0% |
| SimplePIR-full-api | ZKsync Era sample | 128 | 20 | 13 | 43.12 | 20.72 | 52.0% |
