# Official TreePIR perfectized baseline

We downloaded the official TreePIR artifact from `PIR-PIXR/TreePIR` and ran
`TreePIR-Indexing/src/SubCSA` with a portable JRE. The artifact accepts only
a tree height `h` and a leaf index, so this experiment represents the natural
baseline where an SMT is padded into a perfect binary tree before applying
TreePIR's coloring and fast indexing.

| h | occupied | active nodes | TreePIR records | record reduction | width h -> m | max bucket reduction | official indexing |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 33 | 64 | 131,070 | 2048.0x | 16 -> 7.33 (54.2%) | 877.7x | 991 us |
| 20 | 524 | 1046 | 2,097,150 | 2004.9x | 20 -> 12.00 (40.0%) | 1191.6x | 1146 us |
| 24 | 8389 | 16776 | 33,554,430 | 2000.1x | 24 -> 17.00 (29.2%) | 1412.7x | 1258 us |

Interpretation: TreePIR can be run after perfectizing the SMT, but the
official code's database sizes and color sequence are functions of the
complete tree size `2^(h+1)-2`. Our direct SMT organization keeps only
active proof-bearing nodes and therefore reduces records, width, and largest
color subdatabase on the same fixed-height SMT snapshots.
