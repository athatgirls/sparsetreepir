# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 8,10,12,14`
- `sparsities = 0.80,0.90,0.95,0.98`
- `trials per cell = 5`
- `initial_rounds = 120`
- `refine_rounds = 25`
- `max_active_nodes = 12000`

The experiment compares `count_balanced`, `hybrid`, and the count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | sparsity | occupied | active | m | count max | hybrid max | profile max | reduction | profile gap | profile ratio | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 0.80 | 51.0 | 100.0 | 7.40 | 21.60 | 16.20 | 14.20 | 12.3% | 1.00 | 1.046 | 17.3 | 100.0% |
| 8 | 0.90 | 26.0 | 50.0 | 6.40 | 11.00 | 9.60 | 8.60 | 10.4% | 1.20 | 1.096 | 4.7 | 100.0% |
| 8 | 0.95 | 13.0 | 24.0 | 5.20 | 6.40 | 6.00 | 5.20 | 13.3% | 1.20 | 1.100 | 1.0 | 100.0% |
| 8 | 0.98 | 5.0 | 8.0 | 3.00 | 3.00 | 3.00 | 3.00 | 0.0% | 1.00 | 1.125 | 0.1 | 100.0% |
| 10 | 0.80 | 205.0 | 408.0 | 10.00 | 71.00 | 49.00 | 41.00 | 16.3% | 1.00 | 1.005 | 146.2 | 100.0% |
| 10 | 0.90 | 102.0 | 202.0 | 9.20 | 34.00 | 24.80 | 22.60 | 8.9% | 1.00 | 1.028 | 47.3 | 100.0% |
| 10 | 0.95 | 51.0 | 100.0 | 7.80 | 19.20 | 15.20 | 13.40 | 11.8% | 1.00 | 1.042 | 18.5 | 100.0% |
| 10 | 0.98 | 20.0 | 38.0 | 5.80 | 8.80 | 8.00 | 7.20 | 10.0% | 1.00 | 1.095 | 3.1 | 100.0% |
| 12 | 0.80 | 819.0 | 1636.0 | 12.00 | 282.20 | 171.80 | 137.00 | 20.3% | 1.00 | 1.005 | 987.7 | 100.0% |
| 12 | 0.90 | 410.0 | 818.0 | 11.60 | 126.20 | 85.80 | 71.40 | 16.8% | 1.00 | 1.011 | 650.9 | 100.0% |
| 12 | 0.95 | 205.0 | 408.0 | 10.20 | 68.40 | 47.80 | 40.40 | 15.5% | 1.00 | 1.009 | 221.0 | 100.0% |
| 12 | 0.98 | 82.0 | 162.0 | 8.60 | 29.60 | 22.40 | 19.20 | 14.3% | 0.40 | 1.015 | 48.2 | 100.0% |
| 14 | 0.80 | 3277.0 | 6552.0 | 14.00 | 1129.40 | 614.80 | 468.00 | 23.9% | 0.00 | 1.000 | 4759.6 | 100.0% |
| 14 | 0.90 | 1638.0 | 3274.0 | 14.00 | 461.00 | 284.80 | 234.00 | 17.8% | 1.00 | 1.001 | 2512.8 | 100.0% |
| 14 | 0.95 | 819.0 | 1636.0 | 13.00 | 231.00 | 153.40 | 126.00 | 17.9% | 1.00 | 1.001 | 1170.7 | 100.0% |
| 14 | 0.98 | 328.0 | 654.0 | 11.20 | 102.40 | 69.40 | 59.00 | 15.0% | 1.00 | 1.009 | 299.8 | 100.0% |

## Reading the Table

- `active` is the number of active proof-bearing nodes stored by the direct sparse organization.
- `m` is the exact active batch width.
- `profile max` is the largest color subdatabase after subtree-profile refinement.
- `reduction` is the percentage decrease of `profile max` relative to the stronger node-local baseline `hybrid`.
- `profile gap` is the post-refinement subdatabase size gap.
- `profile ratio` is `profile max / average bucket size`; values close to `1` mean near-perfect balance.