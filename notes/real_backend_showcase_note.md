# Real Backend Showcase on Real SMT Workloads

This run is the main executable-backend experiment for the paper: real SMT key sets are converted into SparseTreePIR/PBC-SMT PIR-facing layouts and then measured through concrete backend runners.

## Backend Evidence

| Backend | Evidence level |
|---|---|
| SimplePIR-full-api | Full 32-byte digest retrieval through the SimplePIR Go API; recovered chunks are verified. |
| PIANO-local-runner | Executable PIANO runner over the exact bucket-size vectors induced by the real layouts. |

## Average Effect Against PBC-SMT

| Backend | Datasets | Width reduction | Max-bucket reduction | Online KB reduction | Query-time reduction | Setup reduction |
|---|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | 6 | 34.8% | 48.6% | 54.0% | 55.1% | 69.9% |
| SimplePIR-full-api | 6 | 34.8% | n/a | 52.4% | 39.5% | 59.2% |

## Per-Workload Summary

| Backend | Dataset | h | PBC width | Sparse width | PBC KB | Sparse KB | Online reduction |
|---|---|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | FuelLabs SMT test vectors | 128 | 14 | 9 | 18.44 | 6.89 | 62.6% |
| PIANO-local-runner | Polygon zkEVM broad | 128 | 26 | 17 | 170.62 | 82.34 | 51.7% |
| PIANO-local-runner | Polygon zkEVM multi-window | 128 | 21 | 14 | 72.19 | 35.00 | 51.5% |
| PIANO-local-runner | Polygon zkEVM recent | 128 | 17 | 11 | 37.19 | 17.19 | 53.8% |
| PIANO-local-runner | ZKsync Era broad | 128 | 26 | 17 | 178.75 | 85.00 | 52.4% |
| PIANO-local-runner | ZKsync Era sample | 128 | 20 | 13 | 59.38 | 28.44 | 52.1% |
| SimplePIR-full-api | FuelLabs SMT test vectors | 128 | 14 | 9 | 12.00 | 5.91 | 50.8% |
| SimplePIR-full-api | Polygon zkEVM broad | 128 | 26 | 17 | 133.25 | 62.16 | 53.4% |
| SimplePIR-full-api | Polygon zkEVM multi-window | 128 | 21 | 14 | 51.84 | 25.38 | 51.1% |
| SimplePIR-full-api | Polygon zkEVM recent | 128 | 17 | 11 | 25.50 | 11.69 | 54.2% |
| SimplePIR-full-api | ZKsync Era broad | 128 | 26 | 17 | 138.94 | 65.34 | 53.0% |
| SimplePIR-full-api | ZKsync Era sample | 128 | 20 | 13 | 43.12 | 20.72 | 52.0% |

## Scope

These rows should be presented as real-workload, executable-backend evidence. They do not claim that Spiral, YPIR, or SealPIRplus have already been fully integrated with SparseTreePIR; those remain separate artifact-engineering extensions.

Raw rows: 24
