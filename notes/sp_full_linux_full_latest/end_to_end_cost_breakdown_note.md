# End-to-End Cost Breakdown

This note joins the current WSL repeated backend run with the current WSL structural/layout suite. It is an accounting table, not a new PIR primitive result.

Scheme-level CSV: `/home/thighlight/Desktop/paper/sparsetreepir/examples/sp_full_linux_full_latest/end_to_end_cost_breakdown.csv`
Paired comparison CSV: `/home/thighlight/Desktop/paper/sparsetreepir/examples/sp_full_linux_full_latest/end_to_end_paired_comparison.csv`

## Backend Averages

| Backend | Workloads | Setup reduction | Online latency reduction | Online KB reduction | Width gain | Stored-record gain | Max-bucket gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | 6 | 67.2% | 58.0% | 57.4% | 1.53x | 3.00x | 1.95x |
| SimplePIR-full-api | 6 | 56.0% | 40.8% | 52.4% | 1.53x | 3.00x | 1.95x |

## Per-Workload Paired Rows

| Backend | Dataset | m PBC->Sparse | Metadata KB | ActiveBalance ms | Setup ms PBC->Sparse | Online ms PBC->Sparse | Online KB PBC->Sparse |
|---|---|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | FuelLabs SMT test vectors | 14->9 | 4.64 | 28.09 | 3.21->1.13 | 0.71->0.20 | 22.12->6.89 |
| PIANO-local-runner | Polygon zkEVM broad | 26->17 | 329.95 | 11875.08 | 409.89->136.30 | 17.20->8.43 | 426.56->205.86 |
| PIANO-local-runner | Polygon zkEVM multi-window | 21->14 | 63.14 | 1056.63 | 84.19->28.67 | 9.11->4.17 | 180.47->87.50 |
| PIANO-local-runner | Polygon zkEVM recent | 17->11 | 17.95 | 145.41 | 18.17->5.15 | 3.57->0.96 | 92.97->30.08 |
| PIANO-local-runner | ZKsync Era broad | 26->17 | 362.77 | 11837.72 | 537.76->169.85 | 21.56->10.60 | 446.88->212.50 |
| PIANO-local-runner | ZKsync Era sample | 20->13 | 44.77 | 681.71 | 50.33->17.24 | 6.26->3.31 | 148.44->71.09 |
| SimplePIR-full-api | FuelLabs SMT test vectors | 14->9 | 4.64 | 28.09 | 3.83->1.92 | 9.24->6.31 | 12.00->5.91 |
| SimplePIR-full-api | Polygon zkEVM broad | 26->17 | 329.95 | 11875.08 | 109.26->42.62 | 34.09->18.54 | 133.25->62.16 |
| SimplePIR-full-api | Polygon zkEVM multi-window | 21->14 | 63.14 | 1056.63 | 24.45->9.78 | 18.88->11.11 | 51.84->25.38 |
| SimplePIR-full-api | Polygon zkEVM recent | 17->11 | 17.95 | 145.41 | 8.58->4.22 | 12.65->7.65 | 25.50->11.69 |
| SimplePIR-full-api | ZKsync Era broad | 26->17 | 362.77 | 11837.72 | 116.75->42.57 | 35.19->19.04 | 138.94->65.34 |
| SimplePIR-full-api | ZKsync Era sample | 20->13 | 44.77 | 681.71 | 17.81->8.71 | 16.79->9.89 | 43.12->20.72 |

## Scope Notes

- Backend setup/query/answer/recovery and communication are measured by the executable backend runners.
- `activebalance_profile_ms` is the SparseTreePIR layout-refinement cost from the structural suite; `suite_instance_runtime_ms` is intentionally not folded into the gain ratio because the suite builds multiple comparison layouts for reporting.
- PIANO answer-time counters are often zero or quantized on these small bucket vectors, so online latency for PIANO should be read mainly as query-side executable-runner evidence plus communication/setup accounting.
