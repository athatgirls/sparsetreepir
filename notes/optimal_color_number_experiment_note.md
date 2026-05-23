# Optimal Color Number Validation

This note summarizes the exact-color-number validation run by:

```powershell
python .\run_optimal_color_number_experiment.py
```

## Purpose

- Validate the theorem that the minimum number of colors required by a valid ancestral coloring is exactly the maximum active proof length `m`.
- Compare the theorem-predicted width `m` against the exact chromatic number obtained by exhaustive backtracking on small instances.

## Setup

- Random irregular binary Merkle trees
- Leaf counts: `5, 6, 7, 8`
- Trials per size: `25`
- Seeds start from `9000`

## Results

- `5` leaves
  - `avg proof_nodes = 8.00`
  - `avg theorem_width = 3.44`
  - `avg exact_width = 3.44`
  - `match_rate = 100.0%`
- `6` leaves
  - `avg proof_nodes = 10.00`
  - `avg theorem_width = 3.76`
  - `avg exact_width = 3.76`
  - `match_rate = 100.0%`
- `7` leaves
  - `avg proof_nodes = 12.00`
  - `avg theorem_width = 4.24`
  - `avg exact_width = 4.24`
  - `match_rate = 100.0%`
- `8` leaves
  - `avg proof_nodes = 14.00`
  - `avg theorem_width = 4.56`
  - `avg exact_width = 4.56`
  - `match_rate = 100.0%`

## Overall

- `avg proof_nodes = 11.00`
- `avg theorem_width = 4.00`
- `avg exact_width = 4.00`
- `match_rate = 100.0%`

## Main Takeaway

- On all tested small instances, the exact chromatic number agrees with the theorem-predicted value `m`.
- This supports the claim that the direct protocol can use the exact minimum active batch width rather than padding to the full tree height.
