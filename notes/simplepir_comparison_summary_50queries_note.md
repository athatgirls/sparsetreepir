# Full SimplePIR Comparative Summary

This note derives comparison-oriented metrics from `examples/simplepir_full_backend_results.csv`.

## Aggregate takeaways

- Profile-balanced online communication reduction vs flat normal PIR: 63.8% to 75.6% (avg 70.8%).
- Profile-balanced width reduction vs Pruned-TreePIR-h: 29.2% to 55.0% (avg 41.5%).
- Profile-balanced client query time reduction vs flat normal PIR: 19.9% to 63.1% (avg 44.4%).
- Profile-balanced client query time reduction vs Pruned-TreePIR-h: 6.3% to 49.1% (avg 31.2%).
- Profile-balanced online communication change vs Pruned-TreePIR-h: -14.4% to 26.2% (avg 4.0%). Negative values are SimplePIR tiering cases where Pruned has lower total bytes.

## Per-setting comparison

| h | Empty | m/h | Profile vs flat online | Profile vs pruned online | Profile vs pruned width | Profile vs flat client query | Profile vs pruned client query |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 99.950% | 12/20 | 70.8% | 5.8% | 40.0% | 39.7% | 32.0% |
| 20 | 99.975% | 10/20 | 66.7% | 15.5% | 50.0% | 34.6% | 49.1% |
| 20 | 99.990% | 9/20 | 63.8% | 26.2% | 55.0% | 19.9% | 47.7% |
| 24 | 99.950% | 17/24 | 75.6% | -14.4% | 29.2% | 63.1% | 6.3% |
| 24 | 99.975% | 16/24 | 74.7% | -9.6% | 33.3% | 58.9% | 18.6% |
| 24 | 99.990% | 14/24 | 73.4% | 0.3% | 41.7% | 50.1% | 33.7% |