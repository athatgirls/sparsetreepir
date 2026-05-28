# Real Backend Showcase Repeated Runs

Seeds: 73000, 83000, 93000

This note aggregates repeated runs of the real-workload, executable-backend showcase. Means and sample standard deviations are computed over seed-level summary rows.

## Backend Averages

| Backend | Workloads | Online mean | Online std | Query mean | Query std | Answer mean | Answer std | Setup mean | Setup std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | 6 | 57.4% | 0.0% | 57.5% | 4.9% | n/a | n/a | 66.4% | 5.6% |
| SimplePIR-full-api | 6 | 52.4% | 0.0% | 39.9% | 1.2% | 44.0% | 3.0% | 56.0% | 3.1% |

## Per-Workload Means

| Backend | Dataset | h | Online mean | Online std | Query mean | Answer mean | Setup mean |
|---|---|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | FuelLabs SMT test vectors | 128 | 68.9% | 0.0% | 72.5% | n/a | 64.3% |
| PIANO-local-runner | Polygon zkEVM broad | 128 | 51.7% | 0.0% | 50.8% | n/a | 66.4% |
| PIANO-local-runner | Polygon zkEVM multi-window | 128 | 51.5% | 0.0% | 54.2% | n/a | 66.0% |
| PIANO-local-runner | Polygon zkEVM recent | 128 | 67.6% | 0.0% | 69.3% | n/a | 67.8% |
| PIANO-local-runner | ZKsync Era broad | 128 | 52.4% | 0.0% | 50.8% | n/a | 68.3% |
| PIANO-local-runner | ZKsync Era sample | 128 | 52.1% | 0.0% | 47.3% | n/a | 65.8% |
| SimplePIR-full-api | FuelLabs SMT test vectors | 128 | 50.8% | 0.0% | 31.1% | 25.0% | 49.8% |
| SimplePIR-full-api | Polygon zkEVM broad | 128 | 53.4% | 0.0% | 45.1% | 51.5% | 61.0% |
| SimplePIR-full-api | Polygon zkEVM multi-window | 128 | 51.1% | 0.0% | 40.0% | 44.3% | 60.0% |
| SimplePIR-full-api | Polygon zkEVM recent | 128 | 54.2% | 0.0% | 38.2% | 33.8% | 50.8% |
| SimplePIR-full-api | ZKsync Era broad | 128 | 53.0% | 0.0% | 45.0% | 56.8% | 63.5% |
| SimplePIR-full-api | ZKsync Era sample | 128 | 52.0% | 0.0% | 39.6% | 52.3% | 51.1% |
