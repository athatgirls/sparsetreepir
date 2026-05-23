# PBC-active vs SparseTreePIR on SMT active proof records

This focused experiment compares the generic batch-code adaptation against the final active-interval organization on the same SMT active proof objects. PBC-active follows TreePIR's main generic-batch-code foil at the resource-model level: three replicated active records, about `1.5m` buckets, and a maximum bucket close to `2N/m`. SparseTreePIR stores each active proof record once, uses exact active width `m`, and balances the color stores with ActiveBalance.

| h | Empty | Active N | m | PBC stored | Ours stored | PBC width | Ours width | PBC max bucket | Ours max bucket |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.950% | 1,046 | 12 | 3,138 | 1,046 | 18 | 12 | 175 | 88 |
| 20 | 99.975% | 522 | 10 | 1,566 | 522 | 15 | 10 | 105 | 53 |
| 20 | 99.990% | 208 | 9 | 624 | 208 | 14 | 9 | 47 | 24 |
| 24 | 99.950% | 16,776 | 17 | 50,328 | 16,776 | 26 | 17 | 1,974 | 992 |
| 24 | 99.975% | 8,386 | 16 | 25,158 | 8,386 | 24 | 16 | 1,049 | 535 |
| 24 | 99.990% | 3,354 | 14 | 10,062 | 3,354 | 21 | 14 | 480 | 240 |

## Aggregate reductions

- Storage / linear sequential record work: 66.7% mean reduction.
- Batch width: 33.3% to 35.7% reduction (mean 33.9%).
- Parallel bottleneck bucket: 48.9% to 50% reduction (mean 49.5%).
- Sequential searched records under a linear cost model: 66.7% mean reduction.

## Interpretation

This is not a full PBC implementation. It is the same type of resource-model PBC baseline used by TreePIR: the question is what happens if active SMT proof records are treated as an arbitrary batch rather than as a path-structured interval forest. The result is stable across the tested SMT settings: generic PBC pays replication, wider fixed-shape query width, and roughly twice the largest searched bucket. SparseTreePIR's advantage comes from using the SMT proof structure after active records have already been identified.
