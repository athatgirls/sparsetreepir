# Profile-Balanced Forest Coloring

## Goal

只优化一件事：

- 在 exact-width `m` 不变的前提下，
- 让 interval forest 染色后的颜色子库尽可能平衡。

这里的“平衡”主要看：

- `max_bucket = max_c |D_c|`
- `size_gap = max_c |D_c| - min_c |D_c|`
- `bucket_ratio = max_bucket / average_bucket`

不考虑 backend，不考虑论文表述，不考虑额外颜色预算。


## New idea

当前的 `weighted / count_balanced / hybrid` 都主要是：

- 逐节点贪心；
- 再做单点重染色。

这类方法的局限是：

- 一个高层节点的颜色会影响整个子树的可用颜色结构；
- 单点挪动太局部，难以把整片子树的颜色分布整体调平。

因此我们实现了一个新的 forest-native 方案：

## `profile_balanced`

### Step 1

先用一个已有合法策略初始化（默认从 `hybrid / weighted / count_balanced` 三个起点都试一遍）。

### Step 2

对 interval forest 中的每个节点 `u`，把 `u` 的整棵子树看成一个整体颜色分布 profile：

- 统计该子树中每个颜色包含多少节点；
- 统计该子树中每个颜色包含多少权重。

### Step 3

保持祖先颜色不变，只在“对该子树仍可用的颜色集合”上做一个**整棵子树的颜色置换**。

也就是说，不是把一个节点从红改成蓝，而是把整片子树里的：

- 红类全部换成蓝，
- 蓝类全部换成绿，
- 绿类全部换成红，

这种整体 permutation。

### Why valid

如果一个子树的祖先已经用了某些颜色，那么这个子树内部本来就不会再用这些颜色。  
因此，只要 permutation 只发生在“该子树可用的颜色集合”内部，祖先异色性质就自动保持。

### Step 4

对子树 permutation 的选择，不靠暴力枚举，而是做一个小规模 assignment：

- 把子树内部当前的颜色桶，当作 source buckets；
- 把全局当前较轻的颜色桶，当作 target buckets；
- 用一个小型 DP assignment 选出最优 mapping；
- 如果全局 `(sorted count loads, sorted weight loads)` 目标变好，就接受这次整棵子树的换色。

### Step 5

重复直到没有进一步改进。


## Code

- algorithm:
  `scripts/subtree_permutation_balance.py`
- experiment:
  `scripts/run_profile_balanced_experiment.py`


## Main experimental result

Command:

```powershell
python scripts/run_profile_balanced_experiment.py --height 10 --sparsities 0.5,0.8,0.9,0.95,0.98 --trials 20 --initial-rounds 300 --refine-rounds 80
```

### Overall

- `weighted`
  - `max_bucket = 50.59`
  - `size_gap = 32.12`
  - `bucket_ratio = 1.447`
- `count_balanced`
  - `max_bucket = 78.62`
  - `size_gap = 76.62`
  - `bucket_ratio = 1.731`
- `hybrid`
  - `max_bucket = 47.49`
  - `size_gap = 32.57`
  - `bucket_ratio = 1.222`
- `profile_balanced`
  - `max_bucket = 37.41`
  - `size_gap = 1.00`
  - `bucket_ratio = 1.037`

相对当前最强的 `hybrid`：

- `max_bucket` 再下降约 `21.2%`
- `size_gap` 从 `32.57` 降到 `1.00`
- `bucket_ratio` 从 `1.222` 降到 `1.037`


## By sparsity

### sparsity = 0.50

- `hybrid`: `max_bucket = 139.45`, `size_gap = 118.45`
- `profile_balanced`: `max_bucket = 103.00`, `size_gap = 1.00`

### sparsity = 0.80

- `hybrid`: `max_bucket = 49.45`, `size_gap = 23.00`
- `profile_balanced`: `max_bucket = 41.00`, `size_gap = 1.00`

### sparsity = 0.90

- `hybrid`: `max_bucket = 26.05`, `size_gap = 11.70`
- `profile_balanced`: `max_bucket = 22.90`, `size_gap = 1.00`

### sparsity = 0.95

- `hybrid`: `max_bucket = 14.85`, `size_gap = 6.70`
- `profile_balanced`: `max_bucket = 13.20`, `size_gap = 1.00`

### sparsity = 0.98

- `hybrid`: `max_bucket = 7.65`, `size_gap = 3.00`
- `profile_balanced`: `max_bucket = 6.95`, `size_gap = 1.00`


## Conclusion

这个结果说明：

1. 问题确实应该继续在我们已经得到的 forest 上做。
2. 真正有效的改进，不是单点换色，而是**子树级别的整体颜色重排**。
3. `profile_balanced` 目前已经比现有的 `weighted / count_balanced / hybrid` 更接近“几乎等分”的子库划分。

也就是说，在“只关心颜色子库平衡度”的目标下，这个方案目前是我们现有代码里最合理、效果也最好的版本。

