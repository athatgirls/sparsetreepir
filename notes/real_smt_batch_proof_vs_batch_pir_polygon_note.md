# Real SMT workload: ordinary proof serving vs private proof retrieval

This experiment re-runs the SMT proof-serving comparison on real rollup-derived workloads instead of synthetic random leaves. The ordinary SMT row is the non-private lower bound: the server knows the batch targets and can return a de-duplicated set of real sibling digests. The three PIR rows hide the target set but expose different database shapes. The TreePIR row is the perfectized TreePIR accounting baseline: applying TreePIR faithfully requires completing the SMT to a perfect height-h tree first.

| Dataset | h | B | Keys | Active N | m | Ordinary batch bytes | Perfectized TreePIR width/max bucket | Pruned-h width/max bucket | SparseTreePIR width/max bucket |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Polygon-zkEVM-broad | 128 | 128 | 7,040 | 14,078 | 17 | 33,504 | 128/$\approx 2^{122.0}$ | 128/2,762 | 17/829 |
| Polygon-zkEVM-broad | 256 | 128 | 7,040 | 14,078 | 17 | 33,344 | 256/$\approx 2^{249.0}$ | 256/2,762 | 17/829 |

## Interpretation

- Polygon-zkEVM-broad, h=128: ordinary batch proof serving returns 33,504 bytes for the sampled batch, but reveals the targets. SparseTreePIR uses width 17 instead of the height-pinned width 128; its largest color store has 829 records, versus 2,762 for pruned level-wise PIR (3.33x larger).
- Polygon-zkEVM-broad, h=256: ordinary batch proof serving returns 33,344 bytes for the sampled batch, but reveals the targets. SparseTreePIR uses width 17 instead of the height-pinned width 256; its largest color store has 829 records, versus 2,762 for pruned level-wise PIR (3.33x larger).

The TreePIR baseline is symbolic at heights 128 and 256 because the official TreePIR artifact operates on a perfect-tree input. Perfectizing these real SMT workloads would create $2^{h+1}-2$ private records before coloring, so the reported TreePIR bucket is an accounting value rather than a materialized run.
