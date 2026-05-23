# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 24`
- `occupied_counts =  `
- `trials per cell = 1`
- `initial_rounds = 80`
- `refine_rounds = 8`
- `max_active_nodes = 25000`

The experiment compares `count_balanced`, `hybrid`, and the self-contained count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | empty leaves | occupied | active | m | pruned-h max | lower | profile max | profile/lower | reduction | profile gap | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 24 | 99.9500% | 8389.0 | 16776.0 | 17.00 | 3390.00 | 987.00 | 1069.00 | 1.083 | 11.1% | 192.00 | 3555.8 | 100.0% |

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