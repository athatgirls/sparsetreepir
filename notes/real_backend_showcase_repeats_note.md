# Real Backend Showcase Repeated Runs

Seeds: 73000, 83000, 93000

This note aggregates repeated runs of the real-workload, executable-backend showcase. Means and sample standard deviations are computed over seed-level summary rows.

## Backend Averages

| Backend | Workloads | Online mean | Online std | Query mean | Query std | Answer mean | Answer std | Setup mean | Setup std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | 6 | 57.4% | 0.0% | 58.3% | 11.1% | n/a | n/a | 67.8% | 8.3% |
| SimplePIR-full-api | 6 | 52.4% | 0.0% | 40.5% | 1.3% | 44.1% | 3.5% | 57.3% | 3.5% |

## Per-Workload Means

| Backend | Dataset | h | Online mean | Online std | Query mean | Answer mean | Setup mean |
|---|---|---:|---:|---:|---:|---:|---:|
| PIANO-local-runner | FuelLabs SMT test vectors | 128 | 68.9% | 0.0% | 70.4% | n/a | 62.6% |
| PIANO-local-runner | Polygon zkEVM broad | 128 | 51.7% | 0.0% | 67.9% | n/a | 78.2% |
| PIANO-local-runner | Polygon zkEVM multi-window | 128 | 51.5% | 0.0% | 53.4% | n/a | 68.4% |
| PIANO-local-runner | Polygon zkEVM recent | 128 | 67.6% | 0.0% | 63.0% | n/a | 61.7% |
| PIANO-local-runner | ZKsync Era broad | 128 | 52.4% | 0.0% | 51.9% | n/a | 69.5% |
| PIANO-local-runner | ZKsync Era sample | 128 | 52.1% | 0.0% | 43.1% | n/a | 66.3% |
| SimplePIR-full-api | FuelLabs SMT test vectors | 128 | 50.8% | 0.0% | 34.5% | 30.2% | 43.1% |
| SimplePIR-full-api | Polygon zkEVM broad | 128 | 53.4% | 0.0% | 46.7% | 53.1% | 61.6% |
| SimplePIR-full-api | Polygon zkEVM multi-window | 128 | 51.1% | 0.0% | 40.2% | 42.0% | 60.0% |
| SimplePIR-full-api | Polygon zkEVM recent | 128 | 54.2% | 0.0% | 37.5% | 34.1% | 58.7% |
| SimplePIR-full-api | ZKsync Era broad | 128 | 53.0% | 0.0% | 45.3% | 55.2% | 62.0% |
| SimplePIR-full-api | ZKsync Era sample | 128 | 52.0% | 0.0% | 38.8% | 50.2% | 58.6% |
