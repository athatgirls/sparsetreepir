# Active-Only vs All-Nodes Balance Experiment

This note summarizes the comparison between:

- `active_only`
  - only real active proof-bearing nodes are stored and colored
- `all_nodes`
  - all non-root nodes of the full tree are stored in subdatabases
  - active proof-bearing nodes keep the original valid coloring
  - inactive nodes are treated as zero-weight filler items and packed into color buckets
- `perfectized_depth`
  - all non-root nodes are stored and organized level by level

The experiment was run by:

```powershell
python .\run_all_nodes_vs_active_balance_experiment.py
```

## Setup

- tree height: `10`
- sparsities: `0.2, 0.5, 0.8`
- trials per sparsity: `20`
- strategies:
  - `weighted`
  - `count_balanced`
  - `hybrid`

## Main observation

Putting all nodes into subdatabases does improve the **count balance** very strongly, because the newly added inactive nodes have zero proof weight and can be used as filler items to even out bucket sizes.

However, this does **not** improve the **weighted balance**:

- the added nodes are all `0-weight`
- therefore `weight_gap` remains exactly the same as in `active_only`

So the trade-off is:

- `all_nodes` gives much smaller `size_gap`
- but it roughly doubles storage compared with `active_only`
- and it does not reduce the real proof-traffic imbalance

## Overall results

### `weighted`

- `active_only`
  - `stored_nodes = 1022`
  - `size_gap = 73.767`
  - `weight_gap = 9.367`
- `all_nodes`
  - `stored_nodes = 2046`
  - `size_gap = 6.633`
  - `weight_gap = 9.367`
- `perfectized_depth`
  - `stored_nodes = 2046`
  - `size_gap = 1022.000`
  - `weight_gap = 0.000`

### `count_balanced`

- `active_only`
  - `stored_nodes = 1022`
  - `size_gap = 317.550`
  - `weight_gap = 169.317`
- `all_nodes`
  - `stored_nodes = 2046`
  - `size_gap = 272.217`
  - `weight_gap = 169.317`
- `perfectized_depth`
  - `stored_nodes = 2046`
  - `size_gap = 1022.000`
  - `weight_gap = 0.000`

### `hybrid`

- `active_only`
  - `stored_nodes = 1022`
  - `size_gap = 120.617`
  - `weight_gap = 54.983`
- `all_nodes`
  - `stored_nodes = 2046`
  - `size_gap = 22.700`
  - `weight_gap = 54.983`
- `perfectized_depth`
  - `stored_nodes = 2046`
  - `size_gap = 1022.000`
  - `weight_gap = 0.000`

## Interpretation

- If the goal is only to make subdatabase sizes look more even, `all_nodes` helps a lot.
- If the goal is to improve the balance of *real proof traffic*, `all_nodes` does not help.
- From a PIR-efficiency viewpoint, `all_nodes` is not obviously better than `active_only`, because the extra balance is obtained by inserting many unused zero-weight nodes and increasing storage substantially.
- Relative to the naive level-wise perfectized layout, `all_nodes` is still much more balanced in count, but it loses the main storage advantage of the direct sparse design.
