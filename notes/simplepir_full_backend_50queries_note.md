# Full SimplePIR Backend Experiment

## Settings

- `heights = 20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 1`
- `query samples per trial = 50`
- backend: official `ahenzinger/simplepir` Go implementation
- interface: direct calls to `Init`, `Setup`, `Query`, `Answer`, and `Recover`
- digest representation: each 32-byte record is retrieved as eight 32-bit SimplePIR chunks
- baseline: `flat_normal_pir_m` stores all active nodes in one global PIR database and sends `m` queries to that same database, with dummy padding

This experiment differs from the previous SimplePIR bandwidth check: it materializes the color subdatabases, runs full SimplePIR setup/query/answer/decode, and verifies the recovered chunks.

## Results

| h | empty leaves | scheme | width | active | setup ms | server total ms | server parallel ms | online KB | offline KB |
|---:|---:|:---|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.9500% | flat_normal_pir_m | 12 | 1046 | 5.041 | 0.070 | 0.070 | 48.750 | 2048.000 |
| 20 | 99.9500% | pruned_treepir_h | 20 | 1046 | 5.575 | 0.080 | 0.080 | 15.125 | 7808.000 |
| 20 | 99.9500% | profile_balanced | 12 | 1046 | 2.539 | 0.011 | 0.011 | 14.250 | 7680.000 |
| 20 | 99.9750% | flat_normal_pir_m | 10 | 522 | 0.000 | 0.030 | 0.030 | 29.062 | 1536.000 |
| 20 | 99.9750% | pruned_treepir_h | 20 | 522 | 2.157 | 0.000 | 0.000 | 11.469 | 5888.000 |
| 20 | 99.9750% | profile_balanced | 10 | 522 | 3.049 | 0.040 | 0.040 | 9.688 | 5120.000 |
| 20 | 99.9900% | flat_normal_pir_m | 9 | 208 | 1.030 | 0.050 | 0.050 | 16.312 | 896.000 |
| 20 | 99.9900% | pruned_treepir_h | 20 | 208 | 3.109 | 0.038 | 0.038 | 8.000 | 4352.000 |
| 20 | 99.9900% | profile_balanced | 9 | 208 | 1.567 | 0.020 | 0.020 | 5.906 | 3456.000 |
| 24 | 99.9500% | flat_normal_pir_m | 17 | 16776 | 37.578 | 1.928 | 0.975 | 276.781 | 8320.000 |
| 24 | 99.9500% | pruned_treepir_h | 24 | 16776 | 41.888 | 0.251 | 0.231 | 59.000 | 30080.000 |
| 24 | 99.9500% | profile_balanced | 17 | 16776 | 40.273 | 0.175 | 0.175 | 67.469 | 34816.000 |
| 24 | 99.9750% | flat_normal_pir_m | 16 | 8386 | 17.468 | 0.696 | 0.462 | 183.500 | 5888.000 |
| 24 | 99.9750% | pruned_treepir_h | 24 | 8386 | 28.186 | 0.078 | 0.078 | 42.406 | 21632.000 |
| 24 | 99.9750% | profile_balanced | 16 | 8386 | 25.342 | 0.091 | 0.091 | 46.469 | 24448.000 |
| 24 | 99.9900% | flat_normal_pir_m | 14 | 3354 | 7.806 | 0.432 | 0.382 | 101.938 | 3712.000 |
| 24 | 99.9900% | pruned_treepir_h | 24 | 3354 | 7.665 | 0.050 | 0.050 | 27.219 | 13952.000 |
| 24 | 99.9900% | profile_balanced | 14 | 3354 | 9.343 | 0.030 | 0.030 | 27.125 | 14336.000 |

## Interpretation

- The Go runner performs correctness checks for every recovered chunk.
- Empty color stores are padded with one dummy 32-byte record so that the PIR query interface remains fixed.
- `flat_normal_pir_m` reuses setup/offline state for the shared global database, so the comparison does not artificially copy the database `m` times.
- The chunked implementation is conservative: it proves end-to-end API compatibility, but a production implementation could pack 256-bit digests more efficiently.