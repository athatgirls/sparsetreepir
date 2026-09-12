# Stronger construction neighborhoods, 2026-09-10

The original AB is locally complete for its stated whole-subtree permutation neighborhood. Its 200 base failures are genuine limitations of that neighborhood, not evidence that its quadratic assignment overlooked a better lexicographic permutation. The new, separately evaluated prototype changes the neighborhood: it can recolor all records in three selected color classes, then four, while fixing the remaining classes.

This is a bounded construction experiment. It does not change the original AB algorithm, old tables, PIR measurements, manuscripts, or the exact-OPT reference data. It does not establish a new general graph-coloring result or a sufficient capacity characterization.

## Results

| Method | Base OPT attained, 1323 shapes | Holdout OPT attained, 2115 shapes | Base maximum exact gap | Holdout maximum exact gap |
|---|---:|---:|---:|---:|
| Original Hungarian AB | 1123 | 1780 | 25% | 20% |
| AB + exact union of two-color Kempe components | 1125 | 1796 | 25% | 20% |
| AB + exact three-color recoloring | 1314 | 2073 | 25% | 20% |
| AB + three-color, then four-color recoloring | 1321 | 2112 | 25% | 20% |

The final variant repairs 198 of 200 original-AB base failures and 332 of 335 holdout failures. It still fails on S0606 and S0710 in the base set, and H1199, H1265, and H1285 in the holdout. Its worst observed relative gap is therefore **not improved**. Exact gaps are `(U−OPT)/OPT`, not certificate excess `(U−B_joint)/B_joint`.

Base means the frozen census with 2–14 leaves and width at most six; holdout means the additional frozen census with 15–16 leaves and width at most six. Each unordered shape has the source's one canonical left/right orientation. The 3→4 design was selected on the base set before the holdout run; the holdout was not used to increase the neighborhood to five colors or global exact search. These fractions are finite census results, not estimates of application success probabilities.

All four measured variants pass every actual-SMT target check: 16,642 targets per method in the base set and 33,015 per method in the holdout, totaling 198,628 standard SHA-256 proofs. Each check independently confirms distinct colors for all required sibling positions, obtains the real digest from the assigned class, fills default entries, and recomputes the root. These are construction and proof-assembly checks; no new PIR service or serialized-client routing performance is claimed.

## Why the original Hungarian step is not the problem

For an allowed subtree, let `a_i` be the inside counts and `b_j` the outside counts for colors not used by its strict ancestors. The candidate cost is the sum of `(a_i+b_pi(i))²`. Terms involving only `a` or `b` are constant, leaving a rank-one assignment cost `2 sum a_i b_pi(i)`.

If `a_i<a_j` and the matched outside counts satisfy `b_pi(i)<b_pi(j)`, exchanging their matches reduces this cost by `2(a_j−a_i)(b_pi(j)−b_pi(i))`. The same exchange moves the two resulting loads inward while preserving their sum, so it also improves their decreasingly sorted pair, hence the global lexicographic load vector. Removing inversions gives reverse ordering. Equality cases exchange equal inside or outside values and preserve the load multiset. Thus a quadratic optimum has the lexicographically minimum attainable load multiset for this one-subtree permutation problem. This statement does not imply global coloring optimality.

An independent exhaustive audit checked **309,200 labeled permutations over 3,710 candidate subtrees** across all 200 nonoptimal original-AB base outputs. Each original Hungarian candidate matched the exact best lexicographic permutation, and none strictly improved the current signature. See `original_AB_subtree_neighborhood_audit.json` for every case. All 1,323 rerun original-AB node assignments also match the frozen earlier assignments exactly.

## What changes in the new prototype

The conflict graph has one vertex per positional proof record and an edge between comparable target-rank intervals. A proper coloring assigns different colors to every ancestor–descendant pair in its interval forest.

1. **Two-color component unions.** For each pair of colors, find every connected component of their induced conflict graph. A Kempe swap exchanges the two colors throughout a component. Any union of components is legal. A component with counts `(a,b)` transfers `a−b` records between the classes when swapped. An exact subset-sum DP considers every attainable total transfer and selects the union yielding the smallest full load signature. Only two additional base cases improve, so this variant is retained as a negative/limited-result control.
2. **Exact three-color recoloring.** Select three current color classes; keep all other colors fixed. Compress paths through unselected vertices, connecting each selected vertex to its closest selected ancestor. Enumerate all feasible count profiles of this induced forest by dynamic programming, preserving a concrete coloring witness for each profile. Choose the profile giving the smallest full load signature. Repeat strict improvements until a valid capacity certificate is met or no such move exists.
3. **Four-color continuation.** If the three-color stage has not reached the certificate, repeat the same exact operation on each four-color palette. This stage starts from the three-color result. The pair-union control is separate and is not used as an extra warm start for these stages.

The induced forest can have unary vertices, more than two children, and more than two roots. The implementation handles arbitrary child and root lists; it does not reuse the prior binary-only profile recurrence. Independent projection checks encountered seven children, seven roots, and 275 unary vertices.

## Formal properties and limits

**Preservation.** Edges to unselected colors remain properly colored because selected vertices retain colors from the selected palette. Among selected vertices, the compressed forest has exactly the original selected ancestor–descendant relations. Its DP assigns each root a color unavailable to every descendant, and independently combines all child forests with that color removed. Consequently every returned witness is proper in the entire original conflict graph.

**Exactness of each palette search.** At a root, every proper coloring chooses one root color and gives each child subtree a proper coloring from the remaining palette. The DP enumerates every root-color choice and convolves all possible child count vectors. The same convolution merges all roots. This is a complete recurrence for an arbitrary rooted forest. The attained count vector is therefore lexicographically best for that selected palette, including rearrangements that are not whole-subtree color permutations. It is not a proof that a sequence of strict improvements reaches global OPT.

**Termination and certificates.** Accepted moves strictly decrease the decreasingly sorted integer load vector, so unrestricted strict improvement terminates on a finite instance. The experiment additionally caps each stage at 100 moves. A proper output with `U=B_joint` attains a separately valid lower bound and therefore proves max-bucket optimality for that instance. The construction takes `B_joint`, never exact OPT, as its stopping input. OPT is read only to score outputs. The useful mechanism is the larger exact recoloring neighborhood; merely stopping original AB at `U=LB` is not presented as a new construction.

**Remaining limitations.** The five reported failures stop without a strict four-color improvement; they are not proved infeasible at `B_joint`. Allowing neutral moves, five selected colors, or global DP could change them, but these were deliberately not used to erase the finite failures. Kempe exchanges and profile-DP techniques are established algorithmic ideas; this experiment does not claim their generic novelty. A connection theorem for unrestricted Kempe moves would not prove monotone capacity- or lex-preserving reachability.

## Bounds and runtime scope

The prototype explicitly rejects inputs beyond **N=30 or m=6**. Each merged profile dictionary is capped at 20,000 states and the rooted-subproblem cache at 10,000 entries. Exceeding a cap raises a visible failure rather than a false local-optimality claim. None was reached; maximum cached rooted subproblems were 117 (base) and 127 (holdout). Each stage has a 100-move cap, also not reached.

Even with fixed small palette size k, complete profile enumeration is not a scalable free operation: a forest of s selected records can have up to `binomial(s+k−1,k−1)` count vectors before structural restrictions, and merges compare profile pairs while retaining witnesses. There is no large-instance runtime claim. In particular, **Fuel's N=198 is outside this bounded prototype**; its separate exact capacity-22 witness is not evidence that this new neighborhood runs efficiently on Fuel.

The final recorded execution used Python 3.14.2 on Windows. These are single execution construction timings, not repeated process means or statistical speedups:

| Cohort | Original AB coloring | Additional pair-union control | Additional 3-color stage | Additional 4-color continuation |
|---|---:|---:|---:|---:|
| Base | 1.356 s | 0.048 s | 0.536 s | 0.188 s |
| Holdout | 3.411 s | 0.099 s | 1.738 s | 2.410 s |

The final construction's coloring cost includes original AB plus the three- and four-color stages. The pair control is not added to that total. Initial SMT hashing/extraction, all-target proof validation, JSON writing, and the independent exhaustive audit are outside these per-stage coloring timers. Full cohort walls were 3.43 s and 10.44 s. The 4-color stage reuses only the same instance's 3-color DP cache; caches are cleared between shapes. No setup, hint, network, or PIR latency saving is inferred from these figures.

## Independent validation and reproduction

Run from the repository root:

```
python scripts/measure_construction_neighborhood_20260910.py
python scripts/validate_construction_profiles_20260910.py
```

The second script checks selected-ancestor closure in 3,542 palette projections and compares all DP profile sets with an independently implemented labeled-color brute force in 44 small cases (1,885 recursion visits, no symmetry pruning). It also checks every rerun original-AB assignment against the frozen 1,323-case result. `independent_DP_validation.json` records the checks.

`base_construction_results.json` and `holdout_construction_results.json` preserve shapes, actual SMT embeddings, original and modified node colors, accepted moves, stopping reasons, per-stage time, and proof checks; compact CSVs accompany them. `summary.json` pins all input and algorithm hashes and scope. The prototype contains both the limited Kempe control and the exact 3/4-color neighborhood. No historical algorithm, manuscript, data, or backend file was edited.
