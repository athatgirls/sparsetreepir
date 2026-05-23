# Full SimplePIR Backend Experiment

## Settings

- `heights = 20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 1`
- `query samples per trial = 50`
- backend: official `ahenzinger/simplepir` Go implementation
- interface: direct calls to `Init`, `Setup`, `Query`, `Answer`, and `Recover`
- digest representation: each 32-byte record is retrieved as eight 32-bit SimplePIR chunks
- baselines: `pbc_active` stores three replicated copies over about `1.5m` buckets, `pruned_treepir_h` keeps height-`h` query slots after pruning inactive records, and `flat_normal_pir_m` stores all active nodes in one global PIR database and sends `m` queries to that same database with dummy padding

This experiment differs from the previous SimplePIR bandwidth check: it materializes the color subdatabases, runs full SimplePIR setup/query/answer/decode, and verifies the recovered chunks.

## Results

| h | empty leaves | scheme | width | active | setup ms | server total ms | server parallel ms | online KB | offline KB |
|---:|---:|:---|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.9500% | flat_normal_pir_m | 12 | 1046 | 3.892 | 0.140 | 0.140 | 48.750 | 2048.000 |
| 20 | 99.9500% | pbc_active | 18 | 1046 | 7.208 | 0.054 | 0.054 | 30.938 | 16128.000 |
| 20 | 99.9500% | pruned_treepir_h | 20 | 1046 | 4.615 | 0.051 | 0.051 | 15.125 | 7808.000 |
| 20 | 99.9500% | profile_balanced | 12 | 1046 | 2.066 | 0.070 | 0.070 | 14.250 | 7680.000 |
| 20 | 99.9750% | flat_normal_pir_m | 10 | 522 | 1.044 | 0.040 | 0.040 | 29.062 | 1536.000 |
| 20 | 99.9750% | pbc_active | 15 | 522 | 3.161 | 0.111 | 0.091 | 19.219 | 9600.000 |
| 20 | 99.9750% | pruned_treepir_h | 20 | 522 | 2.063 | 0.083 | 0.083 | 11.469 | 5888.000 |
| 20 | 99.9750% | profile_balanced | 10 | 522 | 3.067 | 0.000 | 0.000 | 9.688 | 5120.000 |
| 20 | 99.9900% | flat_normal_pir_m | 9 | 208 | 0.523 | 0.020 | 0.020 | 16.312 | 896.000 |
| 20 | 99.9900% | pbc_active | 14 | 208 | 1.002 | 0.040 | 0.040 | 12.250 | 7168.000 |
| 20 | 99.9900% | pruned_treepir_h | 20 | 208 | 1.005 | 0.050 | 0.050 | 8.000 | 4352.000 |
| 20 | 99.9900% | profile_balanced | 9 | 208 | 1.575 | 0.060 | 0.060 | 5.906 | 3456.000 |
| 24 | 99.9500% | flat_normal_pir_m | 17 | 16776 | 33.041 | 1.404 | 0.749 | 276.781 | 8320.000 |
| 24 | 99.9500% | pbc_active | 26 | 16776 | 96.981 | 0.581 | 0.446 | 144.625 | 73216.000 |
| 24 | 99.9500% | pruned_treepir_h | 24 | 16776 | 37.488 | 0.092 | 0.072 | 59.000 | 30080.000 |
| 24 | 99.9500% | profile_balanced | 17 | 16776 | 40.768 | 0.212 | 0.192 | 67.531 | 34688.000 |
| 24 | 99.9750% | flat_normal_pir_m | 16 | 8386 | 16.274 | 0.458 | 0.367 | 183.500 | 5888.000 |
| 24 | 99.9750% | pbc_active | 24 | 8386 | 55.671 | 0.292 | 0.281 | 97.500 | 49152.000 |
| 24 | 99.9750% | pruned_treepir_h | 24 | 8386 | 20.526 | 0.153 | 0.133 | 42.406 | 21632.000 |
| 24 | 99.9750% | profile_balanced | 16 | 8386 | 24.863 | 0.080 | 0.070 | 46.438 | 24320.000 |
| 24 | 99.9900% | flat_normal_pir_m | 14 | 3354 | 6.467 | 0.253 | 0.243 | 101.938 | 3712.000 |
| 24 | 99.9900% | pbc_active | 21 | 3354 | 22.325 | 0.202 | 0.182 | 58.406 | 29568.000 |
| 24 | 99.9900% | pruned_treepir_h | 24 | 3354 | 8.023 | 0.160 | 0.160 | 27.219 | 13952.000 |
| 24 | 99.9900% | profile_balanced | 14 | 3354 | 9.156 | 0.024 | 0.024 | 27.219 | 14336.000 |

## Interpretation

- The Go runner performs correctness checks for every recovered chunk.
- Empty color stores are padded with one dummy 32-byte record so that the PIR query interface remains fixed.
- `pbc_active` is a resource-level PBC-style organization over the same active proof records: three replicated copies and about `1.5m` bucket queries, all executed by the same SimplePIR runner.
- `flat_normal_pir_m` reuses setup/offline state for the shared global database, so the comparison does not artificially copy the database `m` times.
- The chunked implementation is conservative: it proves end-to-end API compatibility, but a production implementation could pack 256-bit digests more efficiently.