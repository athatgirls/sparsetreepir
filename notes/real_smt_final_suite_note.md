# Real-only SMT Evaluation Suite

This note replaces the previous synthetic height/sparsity experiments. Every SMT instance here is induced from a real or engineering SMT workload: Polygon zkEVM key workloads, ZKsync Era key workloads, and FuelLabs SMT test vectors. Synthetic random leaves are not used in this suite.

## Workloads

| Workload | Kind | Key mode | Source |
|---|---|---|---|
| Polygon zkEVM recent | deployment-trace | sha256 | `datasets\polygon_zkevm_account_leaf_workload.csv` |
| Polygon zkEVM multi-window | deployment-trace | sha256 | `datasets\polygon_zkevm_account_leaf_workload_multiwindow.csv` |
| Polygon zkEVM broad | deployment-trace | sha256 | `datasets\polygon_zkevm_account_leaf_workload_broad_multiwindow.csv` |
| ZKsync Era sample | deployment-trace | sha256 | `datasets\zksync_era_account_leaf_workload_sample.csv` |
| ZKsync Era broad | deployment-trace | sha256 | `datasets\zksync_era_account_leaf_workload_broad_sample.csv` |
| FuelLabs SMT test vectors | smt-test-vector | hex-prefix | `datasets\fuel_smt_test_workload.csv` |

## 1. Main real-workload resource shape

| Dataset | h | keys | active N | m | avg path | dummy | PBC width/max | Flat max | Sparse max | Sparse/lower |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| FuelLabs SMT test vectors | 128 | 100 | 198 | 9 | 6.88 | 23.56% | 14/43 | 198 | 23 | 1.045 |
| FuelLabs SMT test vectors | 256 | 100 | 198 | 9 | 6.88 | 23.56% | 14/43 | 198 | 23 | 1.045 |
| Polygon zkEVM broad | 128 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 26/1,625 | 14,078 | 829 | 1.000 |
| Polygon zkEVM broad | 256 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 26/1,625 | 14,078 | 829 | 1.000 |
| Polygon zkEVM multi-window | 128 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 21/385 | 2,694 | 193 | 1.000 |
| Polygon zkEVM multi-window | 256 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 21/385 | 2,694 | 193 | 1.000 |
| Polygon zkEVM recent | 128 | 384 | 766 | 11 | 8.89 | 19.15% | 17/136 | 766 | 70 | 1.000 |
| Polygon zkEVM recent | 256 | 384 | 766 | 11 | 8.89 | 19.15% | 17/136 | 766 | 70 | 1.000 |
| ZKsync Era broad | 128 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 26/1,786 | 15,478 | 911 | 1.000 |
| ZKsync Era broad | 256 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 26/1,786 | 15,478 | 911 | 1.000 |
| ZKsync Era sample | 128 | 956 | 1,910 | 13 | 10.19 | 21.62% | 20/287 | 1,910 | 147 | 1.000 |
| ZKsync Era sample | 256 | 956 | 1,910 | 13 | 10.19 | 21.62% | 20/287 | 1,910 | 147 | 1.000 |

## 2. Improvement source summary

| Comparison | Mean resource change on real workloads | Interpretation |
|---|---:|---|
| vs perfectized TreePIR object | active N <= 15,478, while full h=128/256 trees have $2^{129}-2$ / $2^{257}-2$ records | Full coordinate tree is the wrong PIR-facing object for real SMT workloads. |
| vs PBC-SMT active route | width down 34.8%, max bucket down 48.6% | Generic batch coding does not exploit active interval/path structure. |
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
| Polygon zkEVM recent | 128 | flat_active_pir | 11 | 766 | 20 | 1.541 | 9.726 | 0.125 | 0.583 | 38.844 |
| Polygon zkEVM recent | 128 | pbc_smt_active | 17 | 766 | 20 | 6.561 | 11.676 | 0.000 | 1.008 | 25.500 |
| Polygon zkEVM recent | 128 | sparsetreepir_activebalance | 11 | 766 | 20 | 0.763 | 6.442 | 0.000 | 0.258 | 11.688 |
| Polygon zkEVM multi-window | 128 | flat_active_pir | 14 | 2694 | 20 | 7.752 | 17.705 | 0.161 | 1.365 | 91.438 |
| Polygon zkEVM multi-window | 128 | pbc_smt_active | 21 | 2694 | 20 | 27.938 | 17.597 | 0.101 | 2.108 | 51.844 |
| Polygon zkEVM multi-window | 128 | sparsetreepir_activebalance | 14 | 2694 | 20 | 8.048 | 9.637 | 0.050 | 0.929 | 25.375 |
| Polygon zkEVM broad | 128 | flat_active_pir | 17 | 14078 | 20 | 34.428 | 43.995 | 0.709 | 7.910 | 253.406 |
| Polygon zkEVM broad | 128 | pbc_smt_active | 26 | 14078 | 20 | 100.300 | 30.852 | 0.466 | 4.554 | 133.250 |
| Polygon zkEVM broad | 128 | sparsetreepir_activebalance | 17 | 14078 | 20 | 30.872 | 16.555 | 0.253 | 2.788 | 62.156 |
| ZKsync Era sample | 128 | flat_active_pir | 13 | 1910 | 20 | 2.754 | 14.044 | 0.127 | 1.331 | 71.094 |
| ZKsync Era sample | 128 | pbc_smt_active | 20 | 1910 | 20 | 14.303 | 14.622 | 0.127 | 1.727 | 43.125 |
| ZKsync Era sample | 128 | sparsetreepir_activebalance | 13 | 1910 | 20 | 5.015 | 8.791 | 0.025 | 0.377 | 20.719 |
| ZKsync Era broad | 128 | flat_active_pir | 17 | 15478 | 20 | 29.703 | 47.312 | 0.748 | 7.784 | 265.625 |
| ZKsync Era broad | 128 | pbc_smt_active | 26 | 15478 | 20 | 100.599 | 34.479 | 0.154 | 4.091 | 138.938 |
| ZKsync Era broad | 128 | sparsetreepir_activebalance | 17 | 15478 | 20 | 41.689 | 16.729 | 0.100 | 2.675 | 65.344 |
| FuelLabs SMT test vectors | 128 | flat_active_pir | 9 | 198 | 20 | 1.573 | 6.065 | 0.000 | 0.277 | 16.312 |
| FuelLabs SMT test vectors | 128 | pbc_smt_active | 14 | 198 | 20 | 2.752 | 7.595 | 0.000 | 0.250 | 12.000 |
| FuelLabs SMT test vectors | 128 | sparsetreepir_activebalance | 9 | 198 | 20 | 2.047 | 4.927 | 0.000 | 0.275 | 5.906 |
