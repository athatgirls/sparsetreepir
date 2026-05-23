# Height-4 Sparse SMT Example

- `height = 4`
- `sparsity = 0.20` (interpreted as 20% empty leaves)
- `seed = 20260407`
- `total leaves = 16`
- `occupied leaves = 13`
- `occupied leaf heap indices = [16, 17, 18, 19, 20, 23, 24, 25, 26, 27, 28, 30, 31]`
- `occupied leaf slots (0-based) = [0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 14, 15]`
- `stored proof-bearing nodes = 24`
- `num colors = 4`
- `count loads = [3, 5, 9, 7]`
- `weight loads = [13, 12, 12, 12]`
- `count gap = 6`
- `weight gap = 1`
- `ancestral property valid = True`

## Sample batch-PIR views

- `leaf heap=16, slot=0`: `C1->5, C2->9, C3->17, C4->3`
- `leaf heap=24, slot=8`: `C1->2, C2->7, C3->13, C4->25`
- `leaf heap=31, slot=15`: `C1->2, C2->6, C3->14, C4->30`

## Output files

- `height4_sparsity20_full_tree_example.png`
- `height4_sparsity20_full_tree_example.pdf`
- `height4_sparsity20_full_tree_example.json`