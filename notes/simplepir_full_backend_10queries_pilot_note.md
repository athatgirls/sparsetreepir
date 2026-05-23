# Full SimplePIR Backend Experiment

## Settings

- `heights = 20`
- `sparsities = 0.9995`
- `trials per cell = 1`
- `query samples per trial = 10`
- backend: official `ahenzinger/simplepir` Go implementation
- interface: direct calls to `Init`, `Setup`, `Query`, `Answer`, and `Recover`
- digest representation: each 32-byte record is retrieved as eight 32-bit SimplePIR chunks
- baseline: `flat_normal_pir_m` stores all active nodes in one global PIR database and sends `m` queries to that same database, with dummy padding

This experiment differs from the previous SimplePIR bandwidth check: it materializes the color subdatabases, runs full SimplePIR setup/query/answer/decode, and verifies the recovered chunks.

## Results

| h | empty leaves | scheme | width | active | setup ms | server total ms | server parallel ms | online KB | offline KB |
|---:|---:|:---|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.9500% | flat_normal_pir_m | 12 | 1046 | 2.123 | 0.152 | 0.152 | 48.750 | 2048.000 |
| 20 | 99.9500% | profile_balanced | 12 | 1046 | 2.199 | 0.000 | 0.000 | 14.250 | 7680.000 |

## Interpretation

- The Go runner performs correctness checks for every recovered chunk.
- Empty color stores are padded with one dummy 32-byte record so that the PIR query interface remains fixed.
- `flat_normal_pir_m` reuses setup/offline state for the shared global database, so the comparison does not artificially copy the database `m` times.
- The chunked implementation is conservative: it proves end-to-end API compatibility, but a production implementation could pack 256-bit digests more efficiently.