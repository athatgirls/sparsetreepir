# Final experiment suite preview

This file is a compact preview assembled from existing raw experiment outputs. It is meant for deciding which results are strong enough to enter the paper, not as the final manuscript text.

## Experiment 0: Plain SMT serving as the non-private reference

| h | empty | batch | plain dedup bytes | Sparse width | Sparse max bucket | dummy |
|---|---|---|---|---|---|---|
| 16 | 99.950% | 32 | 2,016 | 7 | 10 | 22.3% |
| 16 | 99.975% | 16 | 960 | 5 | 7 | 13.8% |
| 20 | 99.950% | 32 | 6,336 | 12 | 88 | 21.1% |
| 20 | 99.975% | 32 | 5,376 | 12 | 44 | 28.6% |
| 24 | 99.950% | 32 | 10,560 | 17 | 987 | 21.3% |
| 24 | 99.975% | 32 | 9,376 | 16 | 525 | 23.2% |

Effect: ordinary SMT serving is much smaller because it is non-private. SparseTreePIR should be presented as the target-private layer above this lower-cost reference.

## Experiments 1-4: Object selection and organization baselines

| comparison | mean reduction by SparseTreePIR |
|---|---|
| Perfectized records | 100.0% |
| Perfectized max bucket | 100.0% |
| Pruned-h width | 41.5% |
| Pruned-h max bucket | 60.2% |
| PBC-SMT stored records | 66.7% |
| PBC-SMT width | 33.9% |
| PBC-SMT max bucket | 49.5% |
| Flat active max bucket | 91.7% |

Effect: the strongest structural wins are against full-coordinate TreePIR and flat active PIR. Against Pruned-h, storage is intentionally similar, but width and largest bucket still improve. Against PBC-SMT, the effect is stable: remove 3x replication, reduce width by about one third, and halve the largest searched bucket.

## Experiment 5: ActiveBalance ablation

| h | empty | A | m | valid max | ActiveBalance max | AB/LB |
|---|---|---|---|---|---|---|
| 16 | 99.950% | 64 | 7.2 | 10.3 | 9.6 | 1.012 |
| 16 | 99.975% | 30 | 5.4 | 7.3 | 6.3 | 1.094 |
| 16 | 99.990% | 12 | 3.8 | 4.5 | 3.5 | 1.069 |
| 20 | 99.950% | 1,046 | 12.1 | 103.5 | 87.1 | 1.000 |
| 20 | 99.975% | 522 | 11.0 | 57.7 | 48.3 | 1.000 |
| 20 | 99.990% | 208 | 9.4 | 26.7 | 23 | 1.001 |
| 24 | 99.950% | 16,776 | 17 | 1,202.8 | 1,044.2 | 1.058 |
| 24 | 99.975% | 8,386 | 16 | 642.4 | 560 | 1.067 |
| 24 | 99.990% | 3,354 | 14.2 | 291.8 | 240.4 | 1.016 |

Effect: ActiveBalance reduces the largest color store by 14.6% on average versus the valid initializer/hybrid profile, while staying within 1.035x of the structural lower bound on average. All tested colorings remain valid (valid rate 100.0%).

## Experiment 6: High-height compressed SMTs

| h | occupied | A | m | ActiveBalance max | AB/LB |
|---|---|---|---|---|---|
| 128 | 256 | 510 | 10.3 | 50 | 1.007 |
| 128 | 1,024 | 2,046 | 14 | 147 | 1.000 |
| 256 | 256 | 510 | 11 | 47 | 1.000 |
| 256 | 1,024 | 2,046 | 13.7 | 150.7 | 1.000 |

Effect: even at verifier heights 128 and 256, the private retrieval width tracks the occupied-key skeleton rather than the verifier height. The active color-store profile is near the structural lower bound.

## Experiment 7: Real-key / trace-derived workload sanity check

| workload | h | keys | A | m | dummy | max bucket |
|---|---|---|---|---|---|---|
| Polygon recent | 128 | 652 | 1,302 | 12 | 19.4% | 109 |
| Polygon recent | 256 | 652 | 1,302 | 12 | 19.4% | 109 |
| Polygon multi-window | 128 | 1,348 | 2,694 | 14 | 23.4% | 193 |
| Polygon multi-window | 256 | 1,348 | 2,694 | 14 | 23.4% | 193 |
| Polygon broad | 128 | 7,040 | 14,078 | 17 | 22.9% | 829 |
| Polygon broad | 256 | 7,040 | 14,078 | 17 | 22.9% | 829 |
| ZKsync sample | 128 | 956 | 1,910 | 13 | 21.6% | 147 |
| ZKsync sample | 256 | 956 | 1,910 | 13 | 21.6% | 147 |
| ZKsync broad | 128 | 7,740 | 15,478 | 17 | 22.0% | 911 |
| ZKsync broad | 256 | 7,740 | 15,478 | 17 | 22.0% | 911 |

Effect: Polygon and ZKsync-style workloads show the same behavior as the synthetic high-height setting: h is large, but active width remains in the low teens for these samples.

## Experiment 8: Metadata and preprocessing overhead

| h | empty | A | digest KB | metadata KB | meta/digest | setup ms |
|---|---|---|---|---|---|---|
| 16 | 99.950% | 64 | 2 | 1.5 | 0.75 | 4.8 |
| 16 | 99.975% | 30 | 0.9 | 0.7 | 0.75 | 2.0 |
| 16 | 99.990% | 12 | 0.4 | 0.3 | 0.75 | 0.7 |
| 20 | 99.950% | 1,046 | 32.7 | 24.5 | 0.75 | 246.7 |
| 20 | 99.975% | 522 | 16.3 | 12.2 | 0.75 | 95.9 |
| 20 | 99.990% | 208 | 6.5 | 4.9 | 0.75 | 35.2 |
| 24 | 99.950% | 16,776 | 524.2 | 393.2 | 0.75 | 9,333.0 |
| 24 | 99.975% | 8,386 | 262.1 | 196.5 | 0.75 | 3,768.5 |
| 24 | 99.990% | 3,354 | 104.8 | 78.6 | 0.75 | 1,302.0 |

Effect: public metadata scales linearly with active records and is 0.75x of digest payload in the current encoding. This is a real setup cost, but it is active-size rather than full-coordinate-size.

## Experiment 9: SimplePIR executable backend bridge

| comparison | mean reduction by SparseTreePIR |
|---|---|
| vs Flat online KB | 70.8% |
| vs Flat QueryGen | 44.7% |
| vs PBC-SMT online KB | 52.4% |
| vs PBC-SMT QueryGen | 42.9% |
| vs Pruned-h online KB | 3.9% |
| vs Pruned-h QueryGen | 31.2% |

Effect: SparseTreePIR is clearly better than Flat active and PBC-SMT under this SimplePIR runner. The Pruned-h byte result is mixed because backend parameter tiers can favor height-pinned layouts in some small settings; timing and structural metrics still show why Pruned-h is not the clean organization target.

## Experiment 10: Privacy-shape / dummy-ratio analysis

- SparseTreePIR dummy ratio range: 12.5% to 57.1%.

- Pruned-h dummy ratio range: 41.7% to 81.2%.

Effect: fixed-shape privacy costs dummy queries. Reducing the color universe from h to active width m lowers the dummy burden compared with height-pinned layouts, although it cannot remove dummy queries entirely.
