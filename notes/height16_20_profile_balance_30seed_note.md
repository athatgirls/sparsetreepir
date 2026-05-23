# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 16,20`
- `occupied_counts =  `
- `trials per cell = 30`
- `initial_rounds = 80`
- `refine_rounds = 15`
- `max_active_nodes = 5000`

The experiment compares `count_balanced`, `hybrid`, and the self-contained count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | empty leaves | occupied | active | m | pruned-h max | lower | profile max | profile/lower | reduction | profile gap | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.9500% | 33.0 | 64.0 | 7.23 | 14.20 | 9.50 | 9.60 | 1.012 | 6.8% | 1.00 | 3.6 | 100.0% |
| 16 | 99.9750% | 16.0 | 30.0 | 5.37 | 7.87 | 5.70 | 6.27 | 1.094 | 14.2% | 1.23 | 0.8 | 100.0% |
| 16 | 99.9900% | 7.0 | 12.0 | 3.77 | 4.13 | 3.27 | 3.53 | 1.069 | 20.9% | 0.60 | 0.2 | 100.0% |
| 20 | 99.9500% | 524.0 | 1046.0 | 12.13 | 211.73 | 87.10 | 87.10 | 1.000 | 15.8% | 1.07 | 215.9 | 100.0% |
| 20 | 99.9750% | 262.0 | 522.0 | 10.97 | 106.73 | 48.27 | 48.27 | 1.000 | 16.4% | 1.00 | 81.5 | 100.0% |
| 20 | 99.9900% | 105.0 | 208.0 | 9.37 | 43.40 | 22.97 | 23.00 | 1.001 | 13.8% | 1.10 | 21.6 | 100.0% |

## Reading the Table

- `active` is the number of active proof-bearing nodes stored by the direct sparse organization.
- `empty leaves` is the induced SMT sparsity, computed as `1 - occupied / 2^h`.
- `m` is the exact active batch width.
- `pruned-h max` is the largest inherited height-color bucket after pruning empty/default records but keeping width `h`.
- `lower` is the maximum of the equal-split bound `ceil(active / m)` and the active-prefix capacity bound.
- `profile max` is the largest color subdatabase after subtree-profile refinement.
- `profile/lower` measures the instance-wise certified ratio of `profile_balanced` to the structural lower bound.
- `reduction` is the percentage decrease of `profile max` relative to the stronger node-local baseline `hybrid`.
- `profile gap` is the post-refinement subdatabase size gap.
- `profile ratio` is `profile max / average bucket size`; values close to `1` mean near-perfect balance.