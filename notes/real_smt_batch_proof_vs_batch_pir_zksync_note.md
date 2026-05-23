# Real SMT workload: ordinary proof serving vs private proof retrieval

This experiment re-runs the SMT proof-serving comparison on real rollup-derived workloads instead of synthetic random leaves. The ordinary SMT row is the non-private lower bound: the server knows the batch targets and can return a de-duplicated set of real sibling digests. The three PIR rows hide the target set but expose different database shapes. The TreePIR row is the perfectized TreePIR accounting baseline: applying TreePIR faithfully requires completing the SMT to a perfect height-h tree first.

| Dataset | h | B | Keys | Active N | m | Ordinary batch bytes | Perfectized TreePIR width/max bucket | Pruned-h width/max bucket | SparseTreePIR width/max bucket |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ZKsync-Era-broad | 128 | 128 | 7,740 | 15,478 | 17 | 33,632 | 128/$\approx 2^{122.0}$ | 128/3,014 | 17/911 |
| ZKsync-Era-broad | 256 | 128 | 7,740 | 15,478 | 17 | 33,792 | 256/$\approx 2^{249.0}$ | 256/3,014 | 17/911 |

## Interpretation

- ZKsync-Era-broad, h=128: ordinary batch proof serving returns 33,632 bytes for the sampled batch, but reveals the targets. SparseTreePIR uses width 17 instead of the height-pinned width 128; its largest color store has 911 records, versus 3,014 for pruned level-wise PIR (3.31x larger).
- ZKsync-Era-broad, h=256: ordinary batch proof serving returns 33,792 bytes for the sampled batch, but reveals the targets. SparseTreePIR uses width 17 instead of the height-pinned width 256; its largest color store has 911 records, versus 3,014 for pruned level-wise PIR (3.31x larger).

The TreePIR baseline is symbolic at heights 128 and 256 because the official TreePIR artifact operates on a perfect-tree input. Perfectizing these real SMT workloads would create $2^{h+1}-2$ private records before coloring, so the reported TreePIR bucket is an accounting value rather than a materialized run.
