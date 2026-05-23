# Official SimplePIR Backend Experiment

## Settings

- `heights = 16,20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 1`
- `digest record size = 256 bits`
- `profile_refine_rounds = 15`
- backend: official `ahenzinger/simplepir` Go implementation, `TestSimplePirBW`
- local toolchain: Go 1.19 + w64devkit 1.13, required for stable cgo on Windows

The script pads each color subdatabase to the next power-of-two record count because the official benchmark takes `LOG_N` as input.
Empty pruning-only colors are padded to one dummy record and then rounded to two records so that the PIR interface remains defined.
The table reports the exact KB values obtained from SimplePIR's own parameter formulas, avoiding the integer truncation in the printed benchmark output.

## Per-bucket SimplePIR parameter cache

| log records | records | L | M | packed MB | offline KB | online KB |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2 | 26 | 2 | 0.000062 | 104.00 | 0.109 |
| 2 | 4 | 26 | 4 | 0.000123 | 104.00 | 0.117 |
| 3 | 8 | 26 | 8 | 0.000247 | 104.00 | 0.133 |
| 4 | 16 | 26 | 16 | 0.000494 | 104.00 | 0.164 |
| 5 | 32 | 52 | 16 | 0.000987 | 208.00 | 0.266 |
| 6 | 64 | 52 | 32 | 0.001974 | 208.00 | 0.328 |
| 7 | 128 | 78 | 43 | 0.003979 | 312.00 | 0.473 |
| 8 | 256 | 104 | 64 | 0.007897 | 416.00 | 0.656 |
| 9 | 512 | 130 | 103 | 0.015887 | 520.00 | 0.910 |
| 10 | 1024 | 182 | 147 | 0.031743 | 728.00 | 1.285 |
| 11 | 2048 | 234 | 228 | 0.063300 | 936.00 | 1.805 |
| 12 | 4096 | 338 | 316 | 0.126723 | 1352.00 | 2.555 |

## Layout-level results

| h | empty leaves | active | m | pruned max | profile max | P/lower | total online KB | parallel online KB | online red. | par. red. |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.9500% | 64.0 | 7.00 | 12.00 | 10.00 | 1.000 | 2.023$\to$1.148 | 0.164$\to$0.164 | 43.2% | 0.0% |
| 16 | 99.9750% | 30.0 | 5.00 | 8.00 | 7.00 | 1.167 | 1.812$\to$0.664 | 0.133$\to$0.133 | 63.4% | 0.0% |
| 16 | 99.9900% | 12.0 | 3.00 | 4.00 | 5.00 | 1.250 | 1.766$\to$0.367 | 0.117$\to$0.133 | 79.2% | -13.3% |
| 20 | 99.9500% | 1046.0 | 12.00 | 228.00 | 88.00 | 1.000 | 5.684$\to$5.672 | 0.656$\to$0.473 | 0.2% | 28.0% |
| 20 | 99.9750% | 522.0 | 10.00 | 108.00 | 53.00 | 1.000 | 4.215$\to$3.281 | 0.473$\to$0.328 | 22.2% | 30.6% |
| 20 | 99.9900% | 208.0 | 9.00 | 42.00 | 24.00 | 1.000 | 3.258$\to$2.391 | 0.328$\to$0.266 | 26.6% | 19.0% |
| 24 | 99.9500% | 16776.0 | 18.00 | 3290.00 | 934.00 | 1.002 | 21.047$\to$23.133 | 2.555$\to$1.285 | -9.9% | 49.7% |
| 24 | 99.9750% | 8386.0 | 15.00 | 1630.00 | 560.00 | 1.000 | 14.629$\to$19.277 | 1.805$\to$1.285 | -31.8% | 28.8% |
| 24 | 99.9900% | 3354.0 | 15.00 | 686.00 | 224.00 | 1.000 | 9.598$\to$9.844 | 1.285$\to$0.656 | -2.6% | 48.9% |

## Interpretation

- `total online KB` sums SimplePIR query plus answer communication across all color subdatabases.
- `parallel online KB` is the largest per-color online communication after SimplePIR parameter rounding; it is the more relevant number when color subqueries are issued in parallel.
- The result is intentionally more nuanced than the structural model. `profile_balanced` consistently lowers the max bucket and usually lowers the parallel per-color SimplePIR bottleneck, but total communication can increase when many balanced color stores round up to the same SimplePIR parameter tier.
- This supports a cleaner paper claim: profile balancing is a strong exact-width bottleneck reducer, while a production backend may still need a backend-aware secondary objective for total communication.