# Actual FF/AB algorithm gaps (2026-09-10)

The original algorithms were executed, not simulated with substitute greedy rules. All historical inputs, measured layouts, and manuscript files remain unchanged.

## Reproduce

From the repository root: `python scripts/measure_gap_algorithm_20260910.py`, then `python scripts/plot_gap_algorithm_20260910.py`. Dependencies are the current repository Python modules and Matplotlib. No network, Go backend, or new exact DP run is needed.

This execution used Python 3.14.2 on Windows. Building both layouts and independently checking every target took 2.208 seconds; actual coloring alone totaled 0.009553 s (FF) and 0.912141 s (AB). These are single local execution costs, not repeated timing estimates or backend service latency.

## Scope, algorithm, and validation

The frozen source contains all 1323 source-canonical non-plane binary shapes with 2–14 leaves and width at most 6; its enumeration is uncensored. This is not all shapes without a width restriction, every left/right orientation, or a sample of application demand. Source row order is retained: S0223 means zero-based source_index 223.

A leaf is [], an internal node is its ordered child pair. Leaf path bits are padded with zeroes to the deepest leaf to obtain an actual sparse SMT; unary padding introduces no active record. The current SMT API independently confirms source N and m, recomputes the original structural B, and verifies all target color sets and recovered real SHA-256 proofs (16642 per method, 33284 total).

Forest ordered by (interval_left, -interval_length, heap_node); pre-order candidate traversal. FF chooses smallest unused color. AB starts from FF, Hungarian rows/columns enumerate ascending available color; strict < updates retain first equal-cost/equal-signature encountered candidate. No randomness in coloring.

AB uses the original Hungarian routine with a 20-scan cap, begins at actual FF, and stops on a scan finding no strict improvement. Maximum passes = 6; maximum accepted moves = 5; budget truncations = 0. Thus these output gaps cannot be attributed to hitting this round cap. Changing ties, orientation, initialization, or the legal move set remains a separate algorithm modification.

## Do not confuse lower-bound slack and algorithm error

For largest bucket U, `(U−LB)/LB` is certificate excess, an upper bound on `(U−OPT)/OPT`. The latter is the exact relative algorithm gap. Neither is a latency speedup, and a nonzero certificate excess alone does not prove an algorithm is suboptimal.

| Method | Exact optimum attained | Maximum exact gap | Mean exact gap across enumerated shapes |
|---|---:|---:|---:|
| First-fit | 96/1323 | 100.00% | 43.2156% |
| ActiveBalance | 1123/1323 | 25.00% | 3.6709% |

**The 13 lower-bound counterexamples and 200 AB failures are disjoint.** All thirteen cases with frozen Bhier < OPT have AB = OPT. All 200 suboptimal AB outputs have Bhier = OPT: 178 have OPT 4 / AB 5, 12 have OPT 5 / AB 6, and 10 have OPT 6 / AB 7. Consequently a tighter lower bound cannot improve those 200 algorithm outputs. Their maximum actual gap is 25%.

The first suboptimal AB source row is S0023 (n=7, m=3, OPT=4, AB=5). Full node assignments and per-case metrics are in `small_shape_algorithm_results.json` and the compact CSV.

## Frozen seven-dataset counts

The following are extracted from actual binary layout directories, not rerun estimates. Every service interval is checked against the occupied coordinates using inclusive endpoints; per-color intervals are disjoint, positional records are unique, and the FF/AB record universes match. The source metadata hashes match the prior bound analysis.

| Dataset | n | m | B = Bhier | FF | AB | OPT | FF/B | AB/B | AB exact gap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fuel_h128 | 100 | 9 | 22 | 58 | 23 | 22 | 2.6364 | 1.0455 | 4.5455% |
| polygon-broad_h128 | 7040 | 17 | 829 | 3844 | 829 | 829 | 4.6369 | 1.0000 | 0.0000% |
| polygon-multi_h128 | 1348 | 14 | 193 | 772 | 193 | 193 | 4.0000 | 1.0000 | 0.0000% |
| polygon-recent_h128 | 384 | 11 | 70 | 210 | 70 | 70 | 3.0000 | 1.0000 | 0.0000% |
| zksync-broad_h128 | 7740 | 17 | 911 | 4282 | 911 | 911 | 4.7003 | 1.0000 | 0.0000% |
| zksync-sample_h128 | 956 | 13 | 147 | 556 | 147 | 147 | 3.7823 | 1.0000 | 0.0000% |
| ct-record-mirror | 512 | 13 | 79 | 306 | 79 | 79 | 3.8734 | 1.0000 | 0.0000% |

On six of seven datasets AB = B, which already certifies exact optimality for this largest-bucket objective. There is no lower-bound or max-bucket algorithm gap left on those six. This does not imply minimum communication, fastest sequential PIR, or an advantage over full caching.

Fuel previously had only OPT in [22,23]. The separate capacity-22 integer witness now establishes OPT=22 together with ceil(198/9)=22. This analysis independently checks all 198 witness rows against the original binary metadata, integer colors 0–8, all 100 inclusive target ranks, and nine loads of 22. Frozen AB remains 23, hence its true gap is 1/22 = 4.5455%. The exact feasibility witness is a separate method; its result and solver time are not substituted for AB or old backend measurements. The witness version audited here is frozen in `fuel_capacity22_witness_snapshot.json`.

## Figure and provenance

`remaining13_algorithm_trees.pdf/png` draws the thirteen actual AB retrieval-interval forests with LB, OPT, FF, and AB maxima. The virtual open root is excluded from N. Shared vertex colors describe actual AB assignments; edges are interval containment, not SMT parenthood. All thirteen have AB = OPT > the displayed frozen Bhier. This figure documents the earlier hierarchical bound; any separately derived joint bound is a different certificate and must be identified separately.

`remaining13_figure_index.json` maps every panel to its source index and shape hash; `remaining13_caption.tex` is an uninserted caption. `summary.json` pins source/script hashes, environment, runtime boundaries, budgets, all aggregate counts, and the independent Fuel witness check. No manuscript was edited.
