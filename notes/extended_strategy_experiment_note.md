# Extended Coloring Strategy Experiment

This note summarizes the hybrid-strategy and ablation experiment run by:

```powershell
python .\run_extended_strategy_experiment.py
```

## Setup

- Random irregular binary Merkle trees
- Leaf counts: `8, 12, 16, 20`
- Trials per size: `100`
- Strategies:
  - `baseline_depth`
  - `weighted_greedy` (`weighted` with zero rebalance rounds)
  - `weighted`
  - `count_balanced`
  - `hybrid`

## Overall Results

- `baseline_depth`
  - `avg size gap = 4.785`
  - `avg weighted gap = 10.960`
  - `avg hybrid score = 2.202`
  - `avg hybrid excess over lower bound = 1.782`
  - `avg hybrid ratio to lower bound = 6.904`
  - `pass rate = 100.0%`
  - `Seal-like server max = 0.912 ms`
- `weighted_greedy`
  - `avg size gap = 5.093`
  - `avg weighted gap = 2.445`
  - `avg hybrid score = 1.510`
  - `avg hybrid excess over lower bound = 1.090`
  - `avg hybrid ratio to lower bound = 4.266`
  - `pass rate = 100.0%`
  - `Seal-like server max = 0.916 ms`
- `weighted`
  - `avg size gap = 5.072`
  - `avg weighted gap = 2.180`
  - `avg hybrid score = 1.482`
  - `avg hybrid excess over lower bound = 1.063`
  - `avg hybrid ratio to lower bound = 4.163`
  - `pass rate = 100.0%`
  - `Seal-like server max = 0.917 ms`
- `count_balanced`
  - `avg size gap = 3.145`
  - `avg weighted gap = 8.220`
  - `avg hybrid score = 1.553`
  - `avg hybrid excess over lower bound = 1.133`
  - `avg hybrid ratio to lower bound = 4.767`
  - `pass rate = 100.0%`
  - `Seal-like server max = 0.811 ms`
- `hybrid`
  - `avg size gap = 2.465`
  - `avg weighted gap = 6.700`
  - `avg hybrid score = 1.275`
  - `avg hybrid excess over lower bound = 0.855`
  - `avg hybrid ratio to lower bound = 3.657`
  - `pass rate = 100.0%`
  - `Seal-like server max = 0.803 ms`

## New Theoretical Lens

For a coloring $\varphi$, define

- `count gap` as $\Delta_N(\varphi)=\max_c N_c-\min_c N_c$
- `weighted gap` as $\Delta_W(\varphi)=\max_c W_c-\min_c W_c$
- normalized hybrid score as
  $H(\varphi)=\Delta_N(\varphi)/\overline{N}+\Delta_W(\varphi)/\overline{W}$

where $\overline{N}=N/m$ and $\overline{W}=W/m$ are the average node-count and weighted loads per color.

We also compute a universal lower bound

- $H_{\mathrm{lb}}=\Delta_N^{\mathrm{lb}}/\overline{N}+\Delta_W^{\mathrm{lb}}/\overline{W}$

with

- $\Delta_N^{\mathrm{lb}}=0$ if `m` divides `N`, else `1`
- $\Delta_W^{\mathrm{lb}}=\max\{\lceil W/m\rceil, w_{\max}\}-\lfloor W/m\rfloor$

This lower bound applies to every valid ancestral coloring because it already holds for every unconstrained `m`-way partition.

## Main Takeaways

- `weighted_greedy` and `weighted` are close, which means local rebalancing helps, but does not dominate the final outcome in these random-tree settings.
- `hybrid` provides the best overall subdatabase-size balance among the tested direct strategies while keeping the weighted-load gap clearly below `count_balanced`.
- Under the new bicriteria lens, `hybrid` also achieves the smallest average normalized score and the smallest average excess over the universal lower bound.
- All strategies preserve the ancestral distinct-color property in every trial.
- Under size-driven PIR cost proxies, `hybrid` and `count_balanced` align better with reducing the largest subdatabase term, while `weighted` remains best for balancing where real proof material appears.
