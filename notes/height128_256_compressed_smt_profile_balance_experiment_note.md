# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 128,256`
- `occupied_counts = 256,1024`
- `trials per cell = 3`
- `initial_rounds = 80`
- `refine_rounds = 15`
- `max_active_nodes = 5000`

The experiment compares `count_balanced`, `hybrid`, and the self-contained count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | empty leaves | occupied | active | m | pruned-h max | lower | profile max | profile/lower | reduction | profile gap | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 128 | 100.0000% | 256.0 | 510.0 | 10.33 | 104.00 | 49.67 | 50.00 | 1.007 | 15.7% | 1.00 | 63.5 | 100.0% |
| 128 | 100.0000% | 1024.0 | 2046.0 | 14.00 | 401.33 | 147.00 | 147.00 | 1.000 | 16.2% | 1.00 | 647.9 | 100.0% |
| 256 | 100.0000% | 256.0 | 510.0 | 11.00 | 102.67 | 47.00 | 47.00 | 1.000 | 14.5% | 1.00 | 95.1 | 100.0% |
| 256 | 100.0000% | 1024.0 | 2046.0 | 13.67 | 408.67 | 150.67 | 150.67 | 1.000 | 15.4% | 1.00 | 664.4 | 100.0% |

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