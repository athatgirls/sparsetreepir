# Real rollup workloads: PBC-SMT vs SparseTreePIR

This experiment applies the same PBC-SMT resource model to real rollup-style SMT workloads. It is not a full PBC implementation; it uses the standard generic batch-code accounting: three replicated copies of each active proof record and about `1.5m` buckets. SparseTreePIR uses the active width `m`, stores each active proof record once, and uses the measured ActiveBalance bucket profile.

| Workload | h | Keys | Active N | m | PBC-SMT width | Ours width | PBC-SMT stored | Ours stored | PBC-SMT max bucket | Ours max bucket |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Polygon recent | 128 | 652 | 1,302 | 12 | 18 | 12 | 3,906 | 1,302 | 217 | 109 |
| Polygon recent | 256 | 652 | 1,302 | 12 | 18 | 12 | 3,906 | 1,302 | 217 | 109 |
| Polygon multi-window | 128 | 1,348 | 2,694 | 14 | 21 | 14 | 8,082 | 2,694 | 385 | 193 |
| Polygon multi-window | 256 | 1,348 | 2,694 | 14 | 21 | 14 | 8,082 | 2,694 | 385 | 193 |
| Polygon broad | 128 | 7,040 | 14,078 | 17 | 26 | 17 | 42,234 | 14,078 | 1,625 | 829 |
| Polygon broad | 256 | 7,040 | 14,078 | 17 | 26 | 17 | 42,234 | 14,078 | 1,625 | 829 |
| ZKsync sample | 128 | 956 | 1,910 | 13 | 20 | 13 | 5,730 | 1,910 | 287 | 147 |
| ZKsync sample | 256 | 956 | 1,910 | 13 | 20 | 13 | 5,730 | 1,910 | 287 | 147 |
| ZKsync broad | 128 | 7,740 | 15,478 | 17 | 26 | 17 | 46,434 | 15,478 | 1,786 | 911 |
| ZKsync broad | 256 | 7,740 | 15,478 | 17 | 26 | 17 | 46,434 | 15,478 | 1,786 | 911 |

- Mean storage reduction: 66.7%.
- Mean width reduction: 34.2%.
- Mean largest-bucket reduction: 49.3%.
- The h=128 and h=256 rows have the same active skeleton for these hashed key workloads; the verifier proof height changes, but the private active retrieval object is governed by the occupied-key skeleton.
