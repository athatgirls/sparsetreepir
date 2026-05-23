# Height-4 Sparse SMT Example

- `height = 4`
- `sparsity = 0.80` (interpreted as 80% empty leaves)
- `seed = 20260407`
- `total leaves = 16`
- `occupied leaves = 3`
- `occupied leaf heap indices = [16, 27, 31]`
- `occupied leaf slots (0-based) = [0, 11, 15]`
- `stored proof-bearing nodes = 4`
- `num colors = 2`
- `count loads = [2, 2]`
- `weight loads = [3, 2]`
- `count gap = 0`
- `weight gap = 1`
- `ancestral property valid = True`

## Sample batch-PIR views

- `leaf heap=16, slot=0`: `C1->3, C2->dummy`
- `leaf heap=27, slot=11`: `C1->2, C2->7`
- `leaf heap=31, slot=15`: `C1->2, C2->6`

## Output files

- `height4_sparsity80_full_tree_example.png`
- `height4_sparsity80_full_tree_example.pdf`
- `height4_sparsity80_full_tree_example.json`