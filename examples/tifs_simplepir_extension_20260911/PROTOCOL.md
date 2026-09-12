# SimplePIR sparse-proof layout comparison

This protocol is recorded before formal performance measurements.

## Common task and frozen inputs

One batch privately retrieves the non-default 32-byte siblings required by one Merkle membership proof. All four methods use identical active records, occupied coordinates, values, default digests, original levels and trusted root. This is not a batch of unrelated membership proofs. The seven snapshots and the three ten-target schedules per snapshot are reused exactly from `../tifs_external_extension_20260911`; no new favorable input is selected. The cases comprise uniform height-128 trees with 1,000, 10,000 and 100,000 occupied leaves, two 10,000-leaf prefix/cluster sensitivity inputs, and complete trees of heights 10 and 14.

The primary methods are Flat-active, PBC and ActiveBalance (AB). First-fit is an auxiliary ablation. Flat stores each active record once in one database and reuses its state for m independent full-database PIR queries. PBC uses the same official VBPIR three-choice placement as the preceding experiment; its SimplePIR routing wrapper and any differences in cuckoo insertion order/randomness are disclosed. AB reuses the frozen original 20-scan construction. First-fit is reconstructed on the same proof conflict intervals. Default siblings are local; every public query slot, including unused slots, invokes PIR. Neither a target-dependent request count nor an unnecessarily materialized empty tree is allowed.

## Backend and initialization

Use the pinned SimplePIR implementation with its native long-record base-p representation for 256 bits (32 bytes), not eight independent 32-bit databases. The official uint64 input/output boundary is extended with exact big-integer encoding and final reconstruction. Init, Setup, Query and Answer retain their original cryptographic implementations. Each Answer invocation contains one query; the reference multi-query MsgSlice interface partitions rows and must not be used as repeated access to a full Flat database.

Apply the same official parameter-selection policy to all layouts: PickParams(U, 256, 1024, 32), where U is the public largest bucket load (N for Flat). All buckets within a layout share those dimensions. Record the resulting L, M, modulus, error distribution, digit count and padding; common security parameters do not imply identical matrix dimensions. Use ordinary expanded public A initialization. Do not reset the process-global cryptographic PRG from a public seed. Scheduling/routing randomness is separate from cryptographic randomness.

Run actual preprocessing. The upstream performance tests' random replacement hints are not permitted. Serialize and load initialization and online matrices in the adapter's documented format. Count hint, materialized public A, public directory and framing separately. Flat initializes only one unique database. Expanded A is an explicit experimental policy, not a claim that seeded transmission is impossible. Report hint-only and total expanded-state costs so this policy cannot conceal a reversal.

## Schedule, timing and validation

Three fresh sequential processes per method and case; two warmups and ten measured proofs per process (84 formal processes, 840 measured proofs). Reuse the frozen VBPIR target selection for each case/repeat. Shuffle the four method execution order using the new recorded scheduling seed 2026091117. Functional smoke runs are excluded. Fix GOMAXPROCS and native thread settings to one. A process has a 600-second limit and a 10-GiB address-space budget; failures are retained, not silently replaced.

The primary timer covers routing, query generation, query serialization/loading, server computation, answer serialization/loading, long-record recovery, original-level proof reconstruction and root verification in one process. It excludes network latency and is described as serialized proof-processing time, not TCP latency. Setup is measured once per process; snapshot and coloring construction is separate. Record raw record payload, logical padded payload, actual matrix payload and combined-process peak RSS. RSS combines roles and is not isolated server/client RAM.

An independent Python verifier derives needed siblings from original heap coordinates, checks recovered bytes and positions, reconstructs SHA-256 roots and checks modified siblings, coordinates and values. Verify all warmups and formal proofs, fixed message shape, cross-method input equality, and equality with the frozen VBPIR snapshots and targets. Preserve source, executable and input hashes plus commands and raw outcomes.

## Analysis and claim boundaries

The independent statistical unit is the process mean. Report the mean and sample standard deviation of three process means; paired differences may include descriptive 95% Student-t intervals with df=2. Compare AB/PBC within each backend and show whether the direction of benefit persists. Do not pool absolute timings of cryptosystems with different security assumptions or compare these new measurements to the older eight-part SimplePIR path as though they were the same pipeline.

Retain full active-cache communication with the common public metadata. For a fixed snapshot, initialization I plus Q times positive online cost cannot beat cache F in total communication when I >= F. Separate evidence for latency, communication and storage; a smaller maximum bucket alone does not establish a system gain. First-fit outcomes and any unfavorable result remain visible.
