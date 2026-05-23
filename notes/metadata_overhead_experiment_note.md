# Public Metadata Overhead Experiment

## Settings

- `heights = 16,20,24`
- `sparsities = 0.9995,0.99975,0.9999`
- `trials per cell = 3`
- `profile_refine_rounds = 15`
- digest payload: `32` bytes per active node
- compact metadata: `24` bytes per active node

The compact metadata model stores two 64-bit served-interval endpoints, a 16-bit proof level, and alignment/flags.
The database row position is implicit in the sorted metadata table. A more defensive format that stores an explicit 64-bit node id would use 32 bytes per active node.

## Results

| h | empty leaves | active | m | digest KB | metadata KB | meta/digest | setup ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 99.9500% | 64.0 | 7.33 | 2.00 | 1.50 | 0.75 | 6.8 |
| 16 | 99.9750% | 30.0 | 5.67 | 0.94 | 0.70 | 0.75 | 2.3 |
| 16 | 99.9900% | 12.0 | 3.33 | 0.38 | 0.28 | 0.75 | 0.8 |
| 20 | 99.9500% | 1046.0 | 12.00 | 32.69 | 24.52 | 0.75 | 350.6 |
| 20 | 99.9750% | 522.0 | 10.67 | 16.31 | 12.23 | 0.75 | 116.8 |
| 20 | 99.9900% | 208.0 | 9.33 | 6.50 | 4.88 | 0.75 | 40.2 |
| 24 | 99.9500% | 16776.0 | 17.67 | 524.25 | 393.19 | 0.75 | 12525.7 |
| 24 | 99.9750% | 8386.0 | 15.67 | 262.06 | 196.55 | 0.75 | 4637.6 |
| 24 | 99.9900% | 3354.0 | 14.33 | 104.81 | 78.61 | 0.75 | 1623.0 |