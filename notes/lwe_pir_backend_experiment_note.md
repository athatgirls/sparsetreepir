# LWE-PIR Backend Experiment

## Settings

- `heights = 16,20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 1`
- `query_samples = 10`
- `lwe_dimension = 64`
- `profile_refine_rounds = 15`

This experiment uses a randomized LWE-PIR prototype rather than the earlier deterministic matrix surrogate.
It compares Pruned-TreePIR-h against the final profile_balanced organization on the same active proof-bearing nodes.

## Results

| h | empty leaves | active | m | lower | pruned max | profile max | max red. | profile/lower | pruned par. ms | profile par. ms | par. red. |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.9500% | 64.0 | 7.00 | 10.00 | 12.00 | 10.00 | 16.7% | 1.000 | 0.0019 | 0.0041 | -117.6% |
| 16 | 99.9750% | 30.0 | 5.00 | 6.00 | 8.00 | 7.00 | 12.5% | 1.167 | 0.0018 | 0.0015 | 15.3% |
| 16 | 99.9900% | 12.0 | 3.00 | 4.00 | 4.00 | 5.00 | -25.0% | 1.250 | 0.0021 | 0.0015 | 27.8% |
| 20 | 99.9500% | 1046.0 | 12.00 | 88.00 | 228.00 | 88.00 | 61.4% | 1.000 | 0.0051 | 0.0037 | 27.9% |
| 20 | 99.9750% | 522.0 | 10.00 | 53.00 | 108.00 | 53.00 | 50.9% | 1.000 | 0.0029 | 0.0034 | -15.5% |
| 20 | 99.9900% | 208.0 | 9.00 | 24.00 | 42.00 | 24.00 | 42.9% | 1.000 | 0.0020 | 0.0061 | -208.6% |
| 24 | 99.9500% | 16776.0 | 18.00 | 932.00 | 3290.00 | 934.00 | 71.6% | 1.002 | 0.2108 | 0.0948 | 55.0% |
| 24 | 99.9750% | 8386.0 | 15.00 | 560.00 | 1630.00 | 560.00 | 65.6% | 1.000 | 0.1541 | 0.0277 | 82.1% |
| 24 | 99.9900% | 3354.0 | 15.00 | 224.00 | 686.00 | 224.00 | 67.3% | 1.000 | 0.0216 | 0.0064 | 70.3% |

## Interpretation

- `lower` is the structural max-bucket lower bound used as the theoretical certificate.
- `max red.` is the reduction in the largest LWE subdatabase, which is the deterministic server-work bottleneck under parallel color execution.
- `par. ms` is the measured maximum per-color server time. Small instances can be dominated by NumPy overhead, so the largest-bucket work metric should be read together with timing.
- The LWE backend is a SimplePIR-style prototype with public matrix/hint preprocessing, not a production SealPIR or Spiral implementation.