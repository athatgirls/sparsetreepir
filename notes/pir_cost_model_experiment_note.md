# PIR Cost Model Experiment Note

## Goal

This experiment converts our current coloring outputs

- subdatabase sizes `N_c`, and
- weighted loads `W_c`

into end-to-end PIR-style cost indicators.

The main purpose is to answer a precise question:

> Do our new coloring strategies already imply lower PIR cost, or do they mainly improve structural balance?

## Cost model

For a coloring with color classes `D_1, ..., D_h`, let `N_c = |D_c|`.

Following the TreePIR paper, if an underlying PIR backend has per-subdatabase:

- query-generation cost `Q(s)`,
- answer-extraction cost `E(s)`,
- server response-generation cost `S(s)`,

for a database of size `s`, then for an arbitrary partition `{N_c}` we define:

- client query-generation cost:
  `CQ_total = sum_c Q(N_c)`
- client extraction cost:
  `CE_total = sum_c E(N_c)`
- parallel server latency:
  `S_parallel = max_c S(N_c)`
- total server work:
  `S_total = sum_c S(N_c)`

We fit the functions `Q, E, S` from the TreePIR paper's reported measurements on perfect trees:

- `TreePIR + SealPIR`
- `TreePIR + Spiral`

using the corresponding perfect-tree subdatabase size `s = (2^{h+1} - 2) / h`.

## Weighted-load diagnostic

Weighted load does **not** directly determine standard computational PIR cost. Under ordinary single-item PIR, the server still processes one PIR query for every color subdatabase, regardless of whether the returned item is real or dummy.

Therefore we use `W_c` only as a workload-side diagnostic:

- let `L` be the number of leaves,
- define the real-hit probability of color `c` under a uniformly random target leaf by
  `p_c = W_c / L`.

We report:

- `real_hit_gap = max_c p_c - min_c p_c`

This measures how evenly the real proof material is distributed across the fixed batch positions.

## Command

```powershell
python .\run_pir_cost_model_experiment.py
```

## Default setup

- Random binary Merkle trees
- Leaf counts: `8, 12, 16, 20`
- `100` trees per size
- `400` trials in total
- Compared strategies:
  - `baseline_depth`
  - `weighted`
  - `count_balanced`

## Overall results

| Strategy | Avg size gap | Avg weighted gap | Avg real-hit gap | Seal-like server max (ms) | Seal-like server total (ms) | Seal-like query (ms) | Spiral-like server max (ms) | Spiral-like server total (ms) | Spiral-like query (ms) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_depth` | 4.830 | 10.910 | 0.756 | 0.916 | 4.537 | 8.010 | 28.748 | 179.315 | 12.409 |
| `weighted` | 5.232 | 2.330 | 0.163 | 0.922 | 4.492 | 8.008 | 28.755 | 179.192 | 12.406 |
| `count_balanced` | 3.215 | 8.190 | 0.570 | 0.816 | 4.595 | 8.012 | 28.650 | 179.433 | 12.412 |

## Main observations

- `weighted` strongly improves the weighted-load gap and the real-hit gap.
- `count_balanced` still gives the best subdatabase-size gap.
- The estimated size-driven PIR costs differ only slightly across the three strategies.
- In particular, the client query cost is almost unchanged across strategies in both the Seal-like and Spiral-like models.
- `count_balanced` slightly reduces the estimated parallel server latency because it reduces the largest subdatabase.
- `weighted` slightly reduces the estimated total server work because it tends to avoid very uneven medium-to-large buckets in the fitted models.

## Interpretation

This experiment suggests an important and honest conclusion:

- Our current coloring work already improves **structural balance** in meaningful ways.
- However, under standard computational PIR cost models, the cryptographic end-to-end cost is driven mainly by `N_c`, not by `W_c`.
- Therefore, the strongest current claim is not yet
  "our method makes PIR dramatically faster,"
  but rather
  "our method extends TreePIR to arbitrary fixed Merkle trees and improves useful load balance while preserving PIR compatibility."

In short:

- `count_balanced` is the strategy most directly aligned with lowering `max_c S(N_c)`.
- `weighted` is the strategy most directly aligned with balancing where the real proof-bearing traffic appears inside the fixed batch.

## Why this matters for the paper

This gives a cleaner way to write the contribution:

- `N_c`-based metrics support claims about PIR-style computation and latency proxies.
- `W_c`-based metrics support claims about real-proof distribution and useful batch balance.

These are related, but not the same. The paper should avoid merging them into a single over-strong "efficiency" claim.
