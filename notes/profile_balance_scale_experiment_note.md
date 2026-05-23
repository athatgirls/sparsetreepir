# Profile-Balanced Scale Experiment

## Goal

Extend the exact-width structural study beyond `height = 10` and beyond uniform random leaves.

We now test:
- heights: `16, 20, 24`
- occupied-leaf counts: `256`, `1024`
- distributions:
  - `uniform`
  - `clustered`
  - `adversarial`

The focus remains structural:
- active-node count
- exact width `m`
- largest subdatabase under `hybrid`
- largest subdatabase under `profile_balanced`
- largest-bucket reduction
- remaining size gap
- runtime of `profile_balanced`

## Script

`scripts/run_profile_balance_scale_experiment.py`

## Distribution meanings

- `uniform`: sample occupied leaves uniformly at random.
- `clustered`: place leaves into a small number of local windows.
- `adversarial`: mix a dense left prefix with a sparse tail spread across the address space.

## Commands

### 256 occupied leaves

```powershell
python scripts/run_profile_balance_scale_experiment.py --heights 16,20,24 --occupied-counts 256 --distributions uniform,clustered,adversarial --trials 3 --initial-rounds 80 --refine-rounds 10
```

### 1024 occupied leaves

```powershell
python scripts/run_profile_balance_scale_experiment.py --heights 16,20,24 --occupied-counts 1024 --distributions uniform,clustered,adversarial --trials 3 --initial-rounds 100 --refine-rounds 8
```

## Main observations

1. For fixed occupied-leaf count `n`, the active proof-bearing set is driven mainly by the occupied skeleton rather than by the full logical height:
   - `n = 256` gives about `510` active nodes
   - `n = 1024` gives about `2046` active nodes

2. The exact width `m` grows much more slowly than the full SMT height and depends strongly on the leaf distribution.

3. `profile_balanced` keeps improving the largest bucket in all tested settings.

4. The gain is especially strong on the adversarial family:
   - about `60%` reduction for `n = 256`
   - about `65%` to `75%` reduction for `n = 1024`

## Averaged results used in the English draft

### 256 occupied leaves

| h | dist | active | m | hybrid max | profile max | reduction | profile gap | runtime ms |
|---|------|--------|---|------------|-------------|-----------|-------------|------------|
| 16 | uniform | 510.0 | 10.67 | 60.33 | 48.33 | 19.9% | 0.67 | 314.5 |
| 16 | clustered | 510.0 | 12.00 | 48.67 | 43.33 | 11.0% | 1.33 | 421.7 |
| 16 | adversarial | 510.0 | 14.00 | 133.00 | 53.00 | 60.2% | 43.00 | 436.5 |
| 20 | uniform | 510.0 | 10.67 | 56.33 | 48.33 | 14.2% | 0.67 | 317.9 |
| 20 | clustered | 510.0 | 12.33 | 45.33 | 42.33 | 6.6% | 4.00 | 456.9 |
| 20 | adversarial | 510.0 | 15.00 | 133.00 | 53.00 | 60.2% | 44.00 | 495.7 |
| 24 | uniform | 510.0 | 10.67 | 57.33 | 48.33 | 15.7% | 0.67 | 325.2 |
| 24 | clustered | 510.0 | 12.33 | 46.33 | 42.67 | 7.9% | 7.33 | 445.6 |
| 24 | adversarial | 510.0 | 15.00 | 133.00 | 53.00 | 60.2% | 44.00 | 499.4 |

### 1024 occupied leaves

| h | dist | active | m | hybrid max | profile max | reduction | profile gap | runtime ms |
|---|------|--------|---|------------|-------------|-----------|-------------|------------|
| 16 | uniform | 2046.0 | 13.00 | 192.33 | 158.00 | 17.9% | 1.00 | 1261.7 |
| 16 | clustered | 2046.0 | 14.67 | 169.67 | 141.00 | 16.9% | 1.33 | 1704.6 |
| 16 | adversarial | 2046.0 | 16.00 | 770.00 | 191.00 | 75.2% | 177.00 | 1625.6 |
| 20 | uniform | 2046.0 | 13.67 | 179.00 | 151.00 | 15.6% | 5.33 | 1682.5 |
| 20 | clustered | 2046.0 | 14.33 | 164.33 | 146.33 | 11.0% | 40.00 | 1856.2 |
| 20 | adversarial | 2046.0 | 18.00 | 524.00 | 181.00 | 65.5% | 178.00 | 2112.1 |
| 24 | uniform | 2046.0 | 13.00 | 191.00 | 158.00 | 17.3% | 1.33 | 1487.7 |
| 24 | clustered | 2046.0 | 15.00 | 146.67 | 139.67 | 4.8% | 46.67 | 2101.9 |
| 24 | adversarial | 2046.0 | 18.00 | 522.00 | 178.00 | 65.9% | 177.00 | 2148.9 |
