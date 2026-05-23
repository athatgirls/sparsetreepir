# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 16,20,24`
- `occupied_counts = 256,1024,4096`
- `trials per cell = 5`
- `initial_rounds = 120`
- `refine_rounds = 25`
- `max_active_nodes = 12000`

The experiment compares `count_balanced`, `hybrid`, and the count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | empty leaves | occupied | active | m | count max | hybrid max | profile max | reduction | profile gap | profile ratio | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.6094% | 256.0 | 510.0 | 11.00 | 77.00 | 57.40 | 47.00 | 18.1% | 1.00 | 1.014 | 220.5 | 100.0% |
| 16 | 98.4375% | 1024.0 | 2046.0 | 13.60 | 277.00 | 181.00 | 151.40 | 16.4% | 1.00 | 1.005 | 1732.3 | 100.0% |
| 16 | 93.7500% | 4096.0 | 8190.0 | 15.60 | 1106.80 | 646.40 | 525.60 | 18.7% | 0.60 | 1.000 | 10230.6 | 100.0% |
| 20 | 99.9756% | 256.0 | 510.0 | 11.00 | 77.00 | 56.60 | 47.00 | 17.0% | 1.00 | 1.014 | 228.2 | 100.0% |
| 20 | 99.9023% | 1024.0 | 2046.0 | 13.40 | 287.20 | 184.40 | 153.60 | 16.7% | 1.00 | 1.005 | 1718.2 | 100.0% |
| 20 | 99.6094% | 4096.0 | 8190.0 | 16.20 | 998.80 | 616.60 | 506.00 | 17.9% | 1.00 | 1.000 | 10418.5 | 100.0% |
| 24 | 99.9985% | 256.0 | 510.0 | 11.20 | 74.40 | 53.40 | 46.20 | 13.5% | 1.00 | 1.013 | 247.9 | 100.0% |
| 24 | 99.9939% | 1024.0 | 2046.0 | 13.60 | 276.80 | 180.00 | 151.40 | 15.9% | 1.00 | 1.005 | 1552.4 | 100.0% |
| 24 | 99.9756% | 4096.0 | 8190.0 | 16.00 | 1025.60 | 624.80 | 512.00 | 18.1% | 1.00 | 1.000 | 11994.7 | 100.0% |

## Reading the Table

- `active` is the number of active proof-bearing nodes stored by the direct sparse organization.
- `empty leaves` is the induced SMT sparsity, computed as `1 - occupied / 2^h`.
- `m` is the exact active batch width.
- `profile max` is the largest color subdatabase after subtree-profile refinement.
- `reduction` is the percentage decrease of `profile max` relative to the stronger node-local baseline `hybrid`.
- `profile gap` is the post-refinement subdatabase size gap.
- `profile ratio` is `profile max / average bucket size`; values close to `1` mean near-perfect balance.