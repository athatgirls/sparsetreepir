# Ordinary SMT batch serving vs full-proof PIR vs SparseTreePIR

This experiment compares three proof-retrieval views on the same SMT snapshots. `ordinary_smt_batch_serving` is the non-private lower bound: the server knows the target leaves and can return a de-duplicated batch of active sibling digests. `full_coordinate_level_pir` is the naive private complete-proof baseline: query one full SMT coordinate database per proof level. `pruned_level_pir_h` stores only active nodes but still keeps height-`h` proof slots. `sparsetreepir_batch_pir` is our active-interval batch PIR organization.

The table below reports the largest realized target batch for each setting (up to the requested maximum batch size).

| h | Empty | B | Occupied | Active N | m | Ordinary batch bytes | Full-coordinate width/max bucket | Pruned-h width/max bucket | SparseTreePIR width/max bucket |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.950% | 32 | 33 | 64 | 7 | 2,016 | 16/65,536 | 16/14 | 7/10 |
| 16 | 99.975% | 16 | 16 | 30 | 5 | 960 | 16/65,536 | 16/8 | 5/7 |
| 20 | 99.950% | 32 | 524 | 1,046 | 12 | 6,336 | 20/1,048,576 | 20/214 | 12/88 |
| 20 | 99.975% | 32 | 262 | 522 | 12 | 5,376 | 20/1,048,576 | 20/106 | 12/44 |
| 24 | 99.950% | 32 | 8,389 | 16,776 | 17 | 10,560 | 24/16,777,216 | 24/3,312 | 17/987 |
| 24 | 99.975% | 32 | 4,194 | 8,386 | 16 | 9,376 | 24/16,777,216 | 24/1,684 | 16/525 |

## Main observations

- Ordinary SMT batch proof serving is dramatically smaller in bytes, but it is not private: the server receives the target set.
- Naive full-coordinate complete-proof PIR is dominated by the full SMT coordinate space. Its max level database is 6,553.6x to 31,956.6x larger than SparseTreePIR's largest color store in these settings.
- Pruned level-wise PIR removes default records but remains height-pinned. Its largest level bucket is 1.1x to 3.4x larger than SparseTreePIR's largest color store.
- SparseTreePIR does not beat ordinary non-private serving; it reduces the private workload once target privacy is required.
