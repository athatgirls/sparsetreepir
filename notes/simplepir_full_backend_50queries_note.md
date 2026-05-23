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
| 20 | 99.9500% | flat_normal_pir_m | 12 | 1046 | 4.370 | 0.087 | 0.011 | 48.750 | 2048.000 |
| 20 | 99.9500% | pbc_active | 18 | 1046 | 11.293 | 0.056 | 0.007 | 30.938 | 16128.000 |
| 20 | 99.9500% | pruned_treepir_h | 20 | 1046 | 4.519 | 0.052 | 0.008 | 15.125 | 7808.000 |
| 20 | 99.9500% | profile_balanced | 12 | 1046 | 4.225 | 0.034 | 0.005 | 14.250 | 7680.000 |
| 20 | 99.9750% | flat_normal_pir_m | 10 | 522 | 3.325 | 0.064 | 0.010 | 29.062 | 1536.000 |
| 20 | 99.9750% | pbc_active | 15 | 522 | 6.845 | 0.047 | 0.006 | 19.219 | 9600.000 |
| 20 | 99.9750% | pruned_treepir_h | 20 | 522 | 3.289 | 0.057 | 0.007 | 11.469 | 5888.000 |
| 20 | 99.9750% | profile_balanced | 10 | 522 | 3.007 | 0.024 | 0.004 | 9.688 | 5120.000 |
| 20 | 99.9900% | flat_normal_pir_m | 9 | 208 | 1.109 | 0.065 | 0.024 | 16.312 | 896.000 |
| 20 | 99.9900% | pbc_active | 14 | 208 | 3.851 | 0.032 | 0.004 | 12.250 | 7168.000 |
| 20 | 99.9900% | pruned_treepir_h | 20 | 208 | 2.142 | 0.053 | 0.009 | 8.000 | 4352.000 |
| 20 | 99.9900% | profile_balanced | 9 | 208 | 2.046 | 0.021 | 0.003 | 5.906 | 3456.000 |
| 24 | 99.9500% | flat_normal_pir_m | 17 | 16776 | 44.005 | 1.046 | 0.080 | 276.781 | 8320.000 |
| 24 | 99.9500% | pbc_active | 26 | 16776 | 124.669 | 0.282 | 0.019 | 144.625 | 73216.000 |
| 24 | 99.9500% | pruned_treepir_h | 24 | 16776 | 42.990 | 0.129 | 0.019 | 59.000 | 30080.000 |
| 24 | 99.9500% | profile_balanced | 17 | 16776 | 46.374 | 0.112 | 0.010 | 67.469 | 34816.000 |
| 24 | 99.9750% | flat_normal_pir_m | 16 | 8386 | 24.604 | 0.400 | 0.038 | 183.500 | 5888.000 |
| 24 | 99.9750% | pbc_active | 24 | 8386 | 68.214 | 0.170 | 0.011 | 97.500 | 49152.000 |
| 24 | 99.9750% | pruned_treepir_h | 24 | 8386 | 25.208 | 0.104 | 0.013 | 42.406 | 21632.000 |
| 24 | 99.9750% | profile_balanced | 16 | 8386 | 25.500 | 0.079 | 0.008 | 46.469 | 24448.000 |
| 24 | 99.9900% | flat_normal_pir_m | 14 | 3354 | 13.943 | 0.185 | 0.019 | 101.938 | 3712.000 |
| 24 | 99.9900% | pbc_active | 21 | 3354 | 31.617 | 0.107 | 0.009 | 58.406 | 29568.000 |
| 24 | 99.9900% | pruned_treepir_h | 24 | 3354 | 10.248 | 0.080 | 0.008 | 27.219 | 13952.000 |
| 24 | 99.9900% | profile_balanced | 14 | 3354 | 11.366 | 0.056 | 0.007 | 27.125 | 14336.000 |

## Interpretation

- The Go runner performs correctness checks for every recovered chunk.
- Empty color stores are padded with one dummy 32-byte record so that the PIR query interface remains fixed.
- `pbc_active` is a resource-level PBC-style organization over the same active proof records: three replicated copies and about `1.5m` bucket queries, all executed by the same SimplePIR runner.
- `flat_normal_pir_m` reuses setup/offline state for the shared global database, so the comparison does not artificially copy the database `m` times.
- The chunked implementation is conservative: it proves end-to-end API compatibility, but a production implementation could pack 256-bit digests more efficiently.