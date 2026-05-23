# Height-Sparsity Profile-Balancing Experiment

## Settings

- `heights = 16,20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 3`
- `initial_rounds = 80`
- `refine_rounds = 15`
- `max_active_nodes = 20000`

The experiment compares `count_balanced`, `hybrid`, and the self-contained count-only `profile_balanced` refinement.
All schemes use the exact active width `m` of the generated sparse SMT instance.

## Results

| h | empty leaves | occupied | active | m | pruned-h max | lower | profile max | profile/lower | reduction | profile gap | runtime ms | valid |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.9500% | 33.0 | 64.0 | 7.33 | 15.33 | 9.33 | 9.33 | 1.000 | 9.7% | 0.67 | 4.2 | 100.0% |
| 16 | 99.9750% | 16.0 | 30.0 | 5.33 | 7.33 | 5.67 | 6.33 | 1.111 | 17.4% | 1.33 | 0.8 | 100.0% |
| 16 | 99.9900% | 7.0 | 12.0 | 3.67 | 4.00 | 3.33 | 3.67 | 1.083 | 21.4% | 0.67 | 0.2 | 100.0% |
| 20 | 99.9500% | 524.0 | 1046.0 | 12.00 | 203.33 | 88.00 | 88.00 | 1.000 | 15.1% | 1.00 | 196.5 | 100.0% |
| 20 | 99.9750% | 262.0 | 522.0 | 11.33 | 108.00 | 46.67 | 46.67 | 1.000 | 15.7% | 1.00 | 90.5 | 100.0% |
| 20 | 99.9900% | 105.0 | 208.0 | 8.67 | 44.67 | 24.67 | 25.00 | 1.013 | 16.7% | 1.33 | 16.8 | 100.0% |
| 24 | 99.9500% | 8389.0 | 16776.0 | 17.00 | 3405.33 | 987.00 | 989.67 | 1.003 | 18.3% | 10.67 | 7570.9 | 100.0% |
| 24 | 99.9750% | 4194.0 | 8386.0 | 16.00 | 1679.33 | 525.00 | 525.67 | 1.001 | 17.7% | 4.67 | 3558.0 | 100.0% |
| 24 | 99.9900% | 1678.0 | 3354.0 | 14.00 | 666.00 | 240.00 | 240.00 | 1.000 | 18.0% | 1.00 | 926.4 | 100.0% |

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