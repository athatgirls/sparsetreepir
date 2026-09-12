# External proof-retrieval experiment

This file records the VBPIR experimental protocol. The current publication
snapshot omits unrelated feasibility studies and retains the measured VBPIR
cohorts and their original outcomes.

## Question and common task

Can an interval coloring of the nodes required by one sparse Merkle membership proof reduce private batch-retrieval costs relative to the public Vectorized Batch PIR implementation's probabilistic batch-code layout?

One batch retrieves one proof's non-default 32-byte sibling digests. All methods use the same occupied slots, leaf values, active records, SHA-256 convention, target sequence and trusted root. Default siblings are reconstructed locally. The batch shape is fixed by public snapshot parameters, and unused positions issue ordinary encrypted dummy queries. No complete height-128 tree is materialized for a competing baseline.

The principal comparison uses the original ActiveBalance implementation and the official three-choice PBC routing, with the same official VBPIR core and BFV parameters. On complete trees, the original Java TreePIR CSA provides an additional layout. A shared sparse-proof adapter is attributed separately from the original repositories. Nonempty-depth is not used as a TreePIR substitute.

## Planned inputs and schedule

- Synthetic uniform hashed keys: 1,000, 10,000 and 100,000 occupied leaves, height 128.
- Prefix sensitivity: 10,000 keys sharing a 64-bit prefix, height 128; synthetic sensitivity input, not an observed application trace.
- Mixed-cluster sensitivity: 90% of 10,000 keys share a 64-bit prefix and 10% retain their uniform 128-bit coordinates. This adds structural heterogeneity to the prefix-only control.
- Complete-tree control: heights 10 and 14, without default-node pruning or sparse adaptation of CSA.
- Three fresh processes per method and input; two warmups and ten measured target proofs per process. Targets are sampled without replacement from a frozen target pool and paired across methods. Method and case order are shuffled using recorded deterministic experiment seeds. SEAL's cryptographic randomness is not replaced by these scheduling seeds.
- An initial two-target functional run checks the adapter before formal timing. Its results are excluded from the performance summary.
- All timed runs execute sequentially with one OpenMP thread. Each process initializes persistent client/server objects once and reuses them for the target sequence.
- A 600-second per-process limit and 10-GiB resident-address-space safety budget are used where feasible. Resource failures and cuckoo failures remain in the results. Failed samples are not silently replaced, and repeats are not added to seek statistical significance.

## Measurements

Record setup, query generation, answer generation, decode, route, serialization/deserialization, proof assembly and root verification separately. The main native timing is the serialized proof-processing pipeline, including routing, cryptography, serialization/deserialization and root verification. An in-process roundtrip is not a network deployment or TCP latency measurement.

Online communication uses actual ciphertext serialization with identical compression policy for both methods, including explicit framing. The artifact's `save_size()/2` estimates are not used as wire bytes. Record initialization state by direction, public routing metadata, evaluation keys, raw/padded bucket storage, encoded backend storage where exposed, and combined-process peak RSS. Combined-process RSS is not labelled client RAM or server RAM. Missing quantities are labelled unmeasured instead of estimated as complete memory.

The full active-cache payload and the common public routing state are retained as cost references. The snapshot-generation time is recorded separately from backend setup. The input generator runs the unchanged 20-scan Hungarian ActiveBalance implementation and has an independent 600-second/10-GiB limit. An input-construction failure is not recorded as a measured PIR retrieval. Any stage excluded from a reported timer is stated explicitly. Complete-tree inputs also run PBC as a control; original CSA bucket positions are retained, but the common online proof adapter uses an interval directory rather than timing the official Java fast index.

Every measured query must reconstruct its proof by public routing and recovered record positions, reproduce the pinned authentication root, and reject a modified used sibling. Expected digests in the input are available only to the independent correctness auditor and are not a substitute for PIR recovery. Parameters, source commit IDs, local adapter edits, executable/input hashes, exact commands and raw process outputs are archived.

## Analysis

The independent statistical unit is a process mean. Report the mean and sample standard deviation across three processes; paired differences or ratios may include a descriptive 95% Student-t interval (df=2). These limited repeated measurements do not establish general performance equivalence. A smaller largest bucket is an explanatory metric, not the primary success criterion. Negative outcomes and backend rounding plateaus are retained.
