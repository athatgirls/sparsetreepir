# Active Batch Width Scaling Experiment

This note summarizes the sensitivity experiment run by:

```powershell
python .\run_active_batch_width_scaling_experiment.py
```

## Purpose

- Measure how the exact active batch width `m` changes with sparsity on full sparse SMTs.
- Separate two effects of the direct virtual-swapped design:
  - storage reduction from keeping only active proof-bearing nodes
  - batch-width reduction from using the exact minimum active color number `m` instead of the full tree height `h`

## Main Setup

- Full sparse SMT height: `10`
- Sparsities: `0.2, 0.5, 0.8, 0.9, 0.95, 0.98`
- Trials per sparsity: `20`
- Metrics:
  - `avg_active_nodes`
  - `storage_ratio = active_nodes / perfectized_nodes`
  - `avg_m`
  - `m_over_h = m / h`

## Results for Height 10

- sparsity `0.20`
  - `avg_active_nodes = 1636.00`
  - `storage_ratio = 0.800`
  - `avg_m = 10.00`
  - `m/h = 1.000`
- sparsity `0.50`
  - `avg_active_nodes = 1022.00`
  - `storage_ratio = 0.500`
  - `avg_m = 10.00`
  - `m/h = 1.000`
- sparsity `0.80`
  - `avg_active_nodes = 408.00`
  - `storage_ratio = 0.199`
  - `avg_m = 9.95`
  - `m/h = 0.995`
- sparsity `0.90`
  - `avg_active_nodes = 202.00`
  - `storage_ratio = 0.099`
  - `avg_m = 9.15`
  - `m/h = 0.915`
- sparsity `0.95`
  - `avg_active_nodes = 100.00`
  - `storage_ratio = 0.049`
  - `avg_m = 7.70`
  - `m/h = 0.770`
- sparsity `0.98`
  - `avg_active_nodes = 38.00`
  - `storage_ratio = 0.019`
  - `avg_m = 6.05`
  - `m/h = 0.605`

## Interpretation

- Storage shrinks much earlier than batch width.
- At moderate sparsity such as `0.5`, the direct scheme already halves storage, but the active batch width is still essentially the full `h`.
- Noticeable width reduction starts only in a highly sparse regime:
  - at sparsity `0.90`, the direct scheme uses about `91.5%` of the full width
  - at sparsity `0.95`, this drops to about `77.0%`
  - at sparsity `0.98`, it drops to about `60.5%`
- This means the strongest near-term backend gains come from storage and subdatabase-size reduction, while the exact-width theorem gives an additional advantage mainly when the SMT is extremely sparse.

## Additional Cross-Height Check

Running

```powershell
python .\run_active_batch_width_scaling_experiment.py --height-list 8,10,12 --sparsity-list 0.9,0.95,0.98 --trials 20
```

shows the same qualitative trend at other heights:

- width reduction appears across heights in highly sparse regimes
- at the same sparsity, taller trees tend to retain a larger fraction of the full width
- therefore, `m < h` is a genuine but regime-dependent gain, not a universal constant-factor improvement

## Main Takeaway

- The direct protocol has two distinct advantages over perfectized organization:
  - a broad storage advantage on sparse SMTs
  - a narrower but theoretically exact active-width advantage in very sparse regimes
- This sharpens the paper's claim and makes the scope of the improvement more honest and more credible.
