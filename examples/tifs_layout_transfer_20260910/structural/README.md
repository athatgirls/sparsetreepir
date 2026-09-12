# Frozen structural comparison

This directory adds presentation artifacts only. No earlier result, manuscript, algorithm, or timing was overwritten.

Base: 1323 shapes with 2–14 leaves and m≤6. Holdout: 2115 shapes with 15–16 leaves and m≤6. Each source-canonical shape has equal weight; cohorts are never pooled for the headline figures.

## Definitions and results

Absolute gap Δ=U−OPT counts records. Relative gap is Δ/OPT, not excess over a lower bound. Exact OPT is a reference value from frozen complete search, not a newly timed construction.

| Method | Base hits | Holdout hits | Mean Δ, base / holdout | Max Δ, base / holdout | Max relative gap, base / holdout |
|---|---:|---:|---:|---:|---:|
| First-fit | 96/1323 | 20/2115 | 2.054422 / 3.021749 | 6 / 8 | 100.00% / 140.00% |
| AB | 1123/1323 | 1780/2115 | 0.151172 / 0.158392 | 1 / 1 | 25.00% / 20.00% |
| AB + pair | 1125/1323 | 1796/2115 | 0.149660 / 0.150827 | 1 / 1 | 25.00% / 20.00% |
| AB + 3 | 1314/1323 | 2073/2115 | 0.006803 / 0.019858 | 1 / 1 | 25.00% / 20.00% |
| AB + 3→4 | 1321/1323 | 2112/2115 | 0.001512 / 0.001418 | 1 / 1 | 25.00% / 20.00% |
| Exact OPT | 1323/1323 | 2115/2115 | 0.000000 / 0.000000 | 0 / 0 | 0.00% / 0.00% |

`per_shape_metrics.csv` contains all six methods with exact integer numerator/denominator alongside decimal relative gaps. `method_summary.csv` and `summary.json` additionally contain mean relative gaps and each integer-gap count. `remaining_five.csv` lists every final failure, exact gap, and stored stop reason.

## First-fit provenance and validation

The original first_fit_coloring chooses the smallest color absent from the ancestor path, so a node at forest depth d receives color d. Base First-fit values and all heap-node colors exactly reproduce the frozen older artifact. Holdout First-fit was absent there and is newly computed by a count-only traversal. For every one of the 3438 structures, a second traversal of the saved record-parent relation agrees with the canonical binary shape's depth loads; every same-color pair has disjoint target-rank intervals. No SMT hashes, PIR queries, or timing experiments were run for this addition. All four saved algorithm variants also pass independent capacity and interval-properness checks. See first_fit_validation.json. Historical timing fields are deliberately excluded.

## Five remaining failures

S0606, S0710, H1199, H1265, H1285 all have absolute gap one. Their relative gaps are 1/4, 1/4, 1/5, 1/5, 1/6. This finite observation does not establish U≤OPT+1 for arbitrary structures. The original AB and refined variants retain the stated small-instance scope; these graphs do not measure PIR performance.

## Two logical limits for the surrounding discussion

1. A polynomial capacity-decision algorithm, if available for a stated graph class, decides whether the proposed cap is feasible. It need not answer yes at a merely necessary lower bound. Equality OPT=LB requires a separate sufficiency theorem or a valid witness at LB. The known Bonomo–Mattia–Oriolo fixed-color algorithm is polynomial only for fixed m: [author manuscript, Theorems 11–12](https://staff.dc.uba.ar/fbonomo/docs/papers/BMO11.pdf). The current finite binary census is evidence, not a proof of universal LB feasibility.

2. Maximum bucket size U alone does not determine PIR cost. The number of buckets, complete bucket-size vector, record packing, backend matrix dimensions, preprocessing/hint state, query count and amortization matter. Even under a conditional sum-of-square-roots proxy, same N=10, m=4, U=4 profiles (4,4,1,1) and (4,3,2,1) have different costs (6 versus 2+sqrt(3)+sqrt(2)+1). This illustrates why a scalar balance optimum cannot, without a backend-specific cost analysis, be called a communication optimum. No new numeric PIR cost is inferred here.

## Files and reproduction

`absolute_gap_distribution.pdf/.png` is the primary comparison, with integer-gap categories and exact hit labels. `relative_gap_ecdf.pdf/.png` plots the full unweighted ECDF of U/OPT; closely overlapping curves are expected when most shapes attain OPT. `structural_comparison.tex` is a standalone insert requiring booktabs/graphicx; copy the PDF to the manuscript figures directory when integrating. This script does not edit a manuscript.

Run from repository root with a fresh output directory:

```powershell
python examples/tifs_layout_transfer_20260910/structural/build_structural_comparison.py --out NEW_OUTPUT_DIRECTORY
```

All source paths and SHA-256 hashes are in summary.json. The script refuses to overwrite generated files. All figures are derived only from the saved capacities and the documented count-only First-fit addition.
