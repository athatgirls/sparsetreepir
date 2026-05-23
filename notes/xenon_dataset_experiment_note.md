# Xenon2024 Dataset Experiment Note

## Dataset summary

- Source file: `c:\Users\15313\Downloads\xenon2024_log_entries`
- File size: `1.831 GiB`
- Parsed unique `entry_number` values: `1,048,574`
- Entry-number range: `[0, 1,048,575]`
- Missing entry numbers inside the range: `2`
- Missing examples: `371982`, `960752`

The local Xenon dump is therefore almost a complete `2^20` batch. Since the coloring metrics in our prototype depend on the induced Merkle tree topology rather than certificate payloads, the experiment uses the real Xenon-derived leaf counts to build CT-style left-balanced Merkle trees and then runs the direct ancestral-coloring algorithm on those tree shapes.

## Command

```powershell
python .\run_xenon_dataset_experiment.py
```

## Default results

| Label | Leaves | Colors | Baseline size gap | Baseline weighted gap | Weighted size gap | Weighted weighted gap | Count-balanced size gap | Count-balanced weighted gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `100000` | 100,000 | 17 | 98,302 | 1,696 | 98,538 | 485 | 98,302 | 1,696 |
| `300000` | 300,000 | 19 | 262,142 | 37,856 | 266,712 | 4,965 | 262,142 | 37,856 |
| `750000` | 750,000 | 20 | 524,286 | 225,712 | 549,505 | 14,114 | 524,286 | 225,712 |
| `actual_unique` | 1,048,574 | 20 | 1,048,570 | 2 | 1,048,571 | 1 | 1,048,570 | 2 |
| `paper_full` | 1,048,576 | 20 | 1,048,574 | 0 | 1,048,574 | 0 | 1,048,574 | 0 |

All runs preserved the ancestral property.

## What this shows

- On these Xenon-derived CT-style trees, the `weighted` strategy consistently reduces the weighted-load gap.
- The improvement is especially visible on irregular prefix sizes such as `300000` and `750000`.
- On this tree family, `count_balanced` collapses to the same result as the depth-based baseline in the tested cases.
- For the near-complete and complete `2^20` cases, the tree is so regular that there is almost no room to improve beyond the baseline.

## Interpretation

These results suggest that on highly regular CT-style left-balanced trees, our current direct-coloring framework is most useful when the optimization goal is query-load balancing rather than subdatabase-size balancing. In contrast, the subdatabase-size objective appears to be largely determined by the tree family itself in this dataset.
