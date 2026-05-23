# PBC-SMT vs SparseTreePIR experiment

This note isolates the experiment requested here: apply the generic probabilistic-batch-code route directly to SMT active proof records, then compare it with SparseTreePIR on the same SMT instances. We call this baseline **PBC-SMT**: it stores three replicated copies of each active proof record and uses about `1.5m` buckets, following the same resource-model foil used by TreePIR for generic batch retrieval. SparseTreePIR stores each active proof record once, uses active width `m`, and balances color stores with ActiveBalance.

## Resource-model results

| h | Empty | Active N | m | PBC-SMT width | Ours width | PBC-SMT stored | Ours stored | PBC-SMT max bucket | Ours max bucket |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.950% | 1,046 | 12 | 18 | 12 | 3,138 | 1,046 | 175 | 88 |
| 20 | 99.975% | 522 | 10 | 15 | 10 | 1,566 | 522 | 105 | 53 |
| 20 | 99.990% | 208 | 9 | 14 | 9 | 624 | 208 | 47 | 24 |
| 24 | 99.950% | 16,776 | 17 | 26 | 17 | 50,328 | 16,776 | 1,974 | 992 |
| 24 | 99.975% | 8,386 | 16 | 24 | 16 | 25,158 | 8,386 | 1,049 | 535 |
| 24 | 99.990% | 3,354 | 14 | 21 | 14 | 10,062 | 3,354 | 480 | 240 |

- Mean storage reduction: 66.7%.
- Mean width reduction: 33.9%.
- Mean largest-bucket reduction: 49.5%.

## SimplePIR backend results

| h | Empty | PBC-SMT KB | Ours KB | KB red. | PBC-SMT Query ms | Ours Query ms | PBC-SMT Answer ms | Ours Answer ms |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.950% | 30.94 | 14.25 | 53.9% | 11.10 | 6.61 | 0.054 | 0.070 |
| 20 | 99.975% | 19.22 | 9.69 | 49.6% | 8.72 | 5.13 | 0.091 | 0.000 |
| 20 | 99.990% | 12.25 | 5.91 | 51.8% | 7.11 | 4.43 | 0.040 | 0.060 |
| 24 | 99.950% | 144.62 | 67.53 | 53.3% | 29.72 | 15.64 | 0.446 | 0.192 |
| 24 | 99.975% | 97.50 | 46.44 | 52.4% | 23.47 | 12.77 | 0.281 | 0.070 |
| 24 | 99.990% | 58.41 | 27.22 | 53.4% | 15.88 | 8.72 | 0.182 | 0.024 |

- Mean online communication reduction: 52.4%.
- Mean client query-generation reduction: 42.9%.
- Mean server-answer bottleneck reduction: 39.7%.
- Mean client recovery reduction: 51.7%.

## Interpretation

PBC-SMT is a reasonable generic-batch baseline once the SMT proof records have been identified: it treats the active sibling digests as an arbitrary batch-retrieval workload. The experiment shows why this still leaves structure on the table. Compared with PBC-SMT, SparseTreePIR removes the three-copy replication, lowers the fixed batch width from roughly `1.5m` to `m`, and cuts the largest searched bucket by about half. Under the same SimplePIR runner, those resource changes translate into about a half reduction in online bytes and a clear reduction in client-side query generation and answer bottleneck for the tested settings.
