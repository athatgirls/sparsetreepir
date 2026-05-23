# Real-only SMT Evaluation Suite

This note replaces the previous synthetic height/sparsity experiments. Every SMT instance here is induced from a real or engineering SMT workload: Polygon zkEVM key workloads, ZKsync Era key workloads, and FuelLabs SMT test vectors. Synthetic random leaves are not used in this suite.

## Workloads

| Workload | Kind | Key mode | Source |
|---|---|---|---|
| Polygon zkEVM recent | deployment-trace | sha256 | `datasets/polygon_zkevm_account_leaf_workload.csv` |
| Polygon zkEVM multi-window | deployment-trace | sha256 | `datasets/polygon_zkevm_account_leaf_workload_multiwindow.csv` |
| Polygon zkEVM broad | deployment-trace | sha256 | `datasets/polygon_zkevm_account_leaf_workload_broad_multiwindow.csv` |
| ZKsync Era sample | deployment-trace | sha256 | `datasets/zksync_era_account_leaf_workload_sample.csv` |
| ZKsync Era broad | deployment-trace | sha256 | `datasets/zksync_era_account_leaf_workload_broad_sample.csv` |
| FuelLabs SMT test vectors | smt-test-vector | hex-prefix | `datasets/fuel_smt_test_workload.csv` |

## 1. Main real-workload resource shape

| Dataset | h | keys | active N | m | avg path | dummy | Pruned-h width/max | PBC width/max | Flat max | Sparse max | Sparse/lower |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FuelLabs SMT test vectors | 128 | 100 | 198 | 9 | 6.88 | 23.56% | 128/40 | 14/43 | 198 | 23 | 1.045 |
| FuelLabs SMT test vectors | 256 | 100 | 198 | 9 | 6.88 | 23.56% | 256/40 | 14/43 | 198 | 23 | 1.045 |
| Polygon zkEVM broad | 128 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 128/2,762 | 26/1,625 | 14,078 | 829 | 1.000 |
| Polygon zkEVM broad | 256 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 256/2,762 | 26/1,625 | 14,078 | 829 | 1.000 |
| Polygon zkEVM multi-window | 128 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 128/530 | 21/385 | 2,694 | 193 | 1.000 |
| Polygon zkEVM multi-window | 256 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 256/530 | 21/385 | 2,694 | 193 | 1.000 |
| Polygon zkEVM recent | 128 | 384 | 766 | 11 | 8.89 | 19.15% | 128/168 | 17/136 | 766 | 70 | 1.000 |
| Polygon zkEVM recent | 256 | 384 | 766 | 11 | 8.89 | 19.15% | 256/168 | 17/136 | 766 | 70 | 1.000 |
| ZKsync Era broad | 128 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 128/3,014 | 26/1,786 | 15,478 | 911 | 1.000 |
| ZKsync Era broad | 256 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 256/3,014 | 26/1,786 | 15,478 | 911 | 1.000 |
| ZKsync Era sample | 128 | 956 | 1,910 | 13 | 10.19 | 21.62% | 128/370 | 20/287 | 1,910 | 147 | 1.000 |
| ZKsync Era sample | 256 | 956 | 1,910 | 13 | 10.19 | 21.62% | 256/370 | 20/287 | 1,910 | 147 | 1.000 |

## 2. Improvement source summary

| Comparison | Mean resource change on real workloads | Interpretation |
|---|---:|---|
| vs perfectized TreePIR object | active N <= 15,478, while full h=128/256 trees have $2^{129}-2$ / $2^{257}-2$ records | Full coordinate tree is the wrong PIR-facing object for real SMT workloads. |
| vs Pruned TreePIR-h | width down 92.1%, max bucket down 60.7% | Pruning defaults but keeping TreePIR's height-h query universe leaves many empty color slots and unbalanced level buckets. |
| vs PBC-style SMT route | width down 34.8%, max bucket down 48.6% | Generic batch coding does not exploit active interval/path structure. |
| vs flat active PIR | max searched database down 92.1% | Storing only active records is not enough; color partitioning changes backend shape. |
| vs node-local hybrid coloring | max color store down 16.0% | ActiveBalance improves the exact-width active color-store profile. |

## 3. Non-private ordinary SMT batch proof serving

Plain SMT proof serving is included only as a semantic reference. It is much cheaper because the server is told the target leaves, so it is not a privacy-preserving competitor.

| Dataset | h | batch | avg real slots/target | ordinary separate bytes | ordinary dedup bytes |
|---|---:|---:|---:|---:|---:|
| Polygon zkEVM recent | 128 | 128 | 8.82 | 36,128 | 14,528 |
| Polygon zkEVM recent | 256 | 128 | 8.91 | 36,480 | 15,008 |
| Polygon zkEVM multi-window | 128 | 128 | 10.64 | 43,584 | 22,432 |
| Polygon zkEVM multi-window | 256 | 128 | 10.71 | 43,872 | 22,560 |
| Polygon zkEVM broad | 128 | 128 | 13.25 | 54,272 | 33,504 |
| Polygon zkEVM broad | 256 | 128 | 13.20 | 54,080 | 33,344 |
| ZKsync Era sample | 128 | 128 | 10.25 | 41,984 | 20,640 |
| ZKsync Era sample | 256 | 128 | 10.19 | 41,728 | 20,448 |
| ZKsync Era broad | 128 | 128 | 13.27 | 54,368 | 33,632 |
| ZKsync Era broad | 256 | 128 | 13.36 | 54,720 | 33,792 |
| FuelLabs SMT test vectors | 128 | 100 | 6.88 | 22,016 | 6,336 |
| FuelLabs SMT test vectors | 256 | 100 | 6.88 | 22,016 | 6,336 |

## 4. SimplePIR backend bridge on real workloads

| Dataset | h | scheme | width | active | queries | setup ms | query ms | answer parallel ms | recover ms | online KB |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Polygon zkEVM recent | 128 | flat_active_pir | 11 | 766 | 20 | 4.379 | 12.156 | 0.014 | 0.493 | 38.844 |
| Polygon zkEVM recent | 128 | pbc_smt_active | 17 | 766 | 20 | 7.653 | 12.218 | 0.004 | 0.663 | 25.500 |
| Polygon zkEVM recent | 128 | sparsetreepir_activebalance | 11 | 766 | 20 | 4.885 | 7.951 | 0.005 | 0.369 | 11.688 |
| Polygon zkEVM multi-window | 128 | flat_active_pir | 14 | 2694 | 20 | 9.111 | 19.122 | 0.024 | 1.676 | 91.438 |
| Polygon zkEVM multi-window | 128 | pbc_smt_active | 21 | 2694 | 20 | 27.007 | 18.380 | 0.010 | 1.646 | 51.844 |
| Polygon zkEVM multi-window | 128 | sparsetreepir_activebalance | 14 | 2694 | 20 | 9.010 | 10.574 | 0.006 | 0.635 | 25.375 |
| Polygon zkEVM broad | 128 | flat_active_pir | 17 | 14078 | 20 | 35.549 | 40.363 | 0.082 | 5.065 | 253.406 |
| Polygon zkEVM broad | 128 | pbc_smt_active | 26 | 14078 | 20 | 108.728 | 31.277 | 0.013 | 3.289 | 133.250 |
| Polygon zkEVM broad | 128 | sparsetreepir_activebalance | 17 | 14078 | 20 | 40.346 | 17.217 | 0.012 | 1.847 | 62.156 |
| ZKsync Era sample | 128 | flat_active_pir | 13 | 1910 | 20 | 7.985 | 15.850 | 0.015 | 1.104 | 71.094 |
| ZKsync Era sample | 128 | pbc_smt_active | 20 | 1910 | 20 | 19.337 | 15.901 | 0.006 | 1.198 | 43.125 |
| ZKsync Era sample | 128 | sparsetreepir_activebalance | 13 | 1910 | 20 | 8.051 | 9.494 | 0.005 | 0.465 | 20.719 |
| ZKsync Era broad | 128 | flat_active_pir | 17 | 15478 | 20 | 39.721 | 41.299 | 0.065 | 4.618 | 265.625 |
| ZKsync Era broad | 128 | pbc_smt_active | 26 | 15478 | 20 | 127.937 | 32.046 | 0.016 | 3.417 | 138.938 |
| ZKsync Era broad | 128 | sparsetreepir_activebalance | 17 | 15478 | 20 | 44.024 | 18.525 | 0.012 | 1.925 | 65.344 |
| FuelLabs SMT test vectors | 128 | flat_active_pir | 9 | 198 | 20 | 0.925 | 10.988 | 0.015 | 0.339 | 16.312 |
| FuelLabs SMT test vectors | 128 | pbc_smt_active | 14 | 198 | 20 | 3.454 | 9.119 | 0.004 | 0.304 | 12.000 |
| FuelLabs SMT test vectors | 128 | sparsetreepir_activebalance | 9 | 198 | 20 | 1.673 | 6.005 | 0.004 | 0.127 | 5.906 |
