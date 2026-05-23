# Active-width threshold experiment

This experiment estimates when the exact active width `m` starts to give a visible reduction over the full SMT height `h`. The experiment samples occupied leaves uniformly, computes the maximum number of branching ancestors on any occupied-leaf path, and reports `m/h`.

## Thresholds

| Height | First empty ratio with m/h <= 0.8 | m/h <= 2/3 | m/h <= 1/2 |
|---:|---:|---:|---:|
| 16 | 99.00000% (n=655) | 99.75000% (n=164) | 99.95000% (n=33) |
| 20 | 99.75000% (n=2621) | 99.90000% (n=1049) | 99.99000% (n=105) |
| 24 | 99.90000% (n=16777) | 99.97500% (n=4194) | 99.99900% (n=168) |
| 32 | 99.99900% (n=42950) | 99.99900% (n=42950) | - |

## Detailed grid

| h | Empty % | occupied n | avg m | m/h | avg active path |
|---:|---:|---:|---:|---:|---:|
| 16 | 90.00000 | 6554 | 16 | 1 | 12.98 |
| 16 | 95.00000 | 3277 | 15 | 0.938 | 12.00 |
| 16 | 98.00000 | 1311 | 14 | 0.875 | 10.70 |
| 16 | 99.00000 | 655 | 12.40 | 0.775 | 9.68 |
| 16 | 99.50000 | 328 | 11.20 | 0.700 | 8.68 |
| 16 | 99.75000 | 164 | 10 | 0.625 | 7.69 |
| 16 | 99.90000 | 66 | 8.60 | 0.537 | 6.42 |
| 16 | 99.95000 | 33 | 7 | 0.438 | 5.34 |
| 16 | 99.97500 | 16 | 6.20 | 0.388 | 4.35 |
| 16 | 99.99000 | 7 | 4 | 0.250 | 3.09 |
| 16 | 99.99500 | 3 | 2 | 0.125 | 1.67 |
| 16 | 99.99900 | 1 | 0 | 0 | 0 |
| 20 | 90.00000 | 104858 | 20 | 1 | 16.98 |
| 20 | 95.00000 | 52429 | 20 | 1 | 16.00 |
| 20 | 98.00000 | 20972 | 18 | 0.900 | 14.68 |
| 20 | 99.00000 | 10486 | 17.40 | 0.870 | 13.69 |
| 20 | 99.50000 | 5243 | 16.40 | 0.820 | 12.69 |
| 20 | 99.75000 | 2621 | 15.20 | 0.760 | 11.69 |
| 20 | 99.90000 | 1049 | 13.20 | 0.660 | 10.38 |
| 20 | 99.95000 | 524 | 12.20 | 0.610 | 9.36 |
| 20 | 99.97500 | 262 | 11 | 0.550 | 8.35 |
| 20 | 99.99000 | 105 | 9.60 | 0.480 | 7.03 |
| 20 | 99.99500 | 52 | 7.80 | 0.390 | 6.02 |
| 20 | 99.99900 | 10 | 5 | 0.250 | 3.64 |
| 24 | 90.00000 | 1677722 | skipped | skipped | skipped |
| 24 | 95.00000 | 838861 | skipped | skipped | skipped |
| 24 | 98.00000 | 335544 | skipped | skipped | skipped |
| 24 | 99.00000 | 167772 | 22 | 0.917 | 17.69 |
| 24 | 99.50000 | 83886 | 21 | 0.875 | 16.69 |
| 24 | 99.75000 | 41943 | 19.80 | 0.825 | 15.69 |
| 24 | 99.90000 | 16777 | 18.20 | 0.758 | 14.37 |
| 24 | 99.95000 | 8389 | 17.40 | 0.725 | 13.37 |
| 24 | 99.97500 | 4194 | 16 | 0.667 | 12.36 |
| 24 | 99.99000 | 1678 | 14.20 | 0.592 | 11.04 |
| 24 | 99.99500 | 839 | 13 | 0.542 | 10.04 |
| 24 | 99.99900 | 168 | 10.20 | 0.425 | 7.72 |
| 32 | 90.00000 | 429496730 | skipped | skipped | skipped |
| 32 | 95.00000 | 214748365 | skipped | skipped | skipped |
| 32 | 98.00000 | 85899346 | skipped | skipped | skipped |
| 32 | 99.00000 | 42949673 | skipped | skipped | skipped |
| 32 | 99.50000 | 21474836 | skipped | skipped | skipped |
| 32 | 99.75000 | 10737418 | skipped | skipped | skipped |
| 32 | 99.90000 | 4294967 | skipped | skipped | skipped |
| 32 | 99.95000 | 2147484 | skipped | skipped | skipped |
| 32 | 99.97500 | 1073742 | skipped | skipped | skipped |
| 32 | 99.99000 | 429497 | skipped | skipped | skipped |
| 32 | 99.99500 | 214748 | skipped | skipped | skipped |
| 32 | 99.99900 | 42950 | 20 | 0.625 | 15.72 |

Interpretation: `m` is usually not useful as a width reducer when the tree is only moderately sparse. The visible width gain starts when the occupied set is small enough that many low-level sibling subtrees are empty. The threshold shifts upward with `h`: a height-24 SMT needs roughly 99.9% empty leaves before `m/h <= 0.8` in this uniform grid, while height-32 needs around 99.99%.
