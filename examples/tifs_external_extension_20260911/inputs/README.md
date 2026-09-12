# External 32-byte proof-retrieval inputs

The producer is `scripts/prepare_external_extension_20260911.py`. Only a case with
`snapshot_summary.json` and `status: complete` is ready for the native runner.
Each output JSON and every reused source have SHA-256 pins in that summary.
`process.json` records the independent preparation process, exit status and its
explicit 600-second / 10-GiB virtual-address-space limits. These are input
preparation measurements, not PIR timing results. Existing results were not
modified.

## Cases and common cryptographic input

- `uniform_n1000`, `uniform_n10000`, `uniform_n100000`: height 128, deterministic
  synthetic SHA-256 keys (the first 128 hash bits), seed 2026091103. The smaller
  source-index sets are subsets of the larger sets. No coordinate collision was
  silently removed or resampled.
- `prefix64_n10000`: the same source hashes as uniform 10,000, with their top 64
  coordinate bits cleared and the bottom 64 retained. This is a synthetic common
  prefix control; it is not asserted to preserve the uniform case's exact forest.
- `cluster90_n10000`: source indices 0 through 8,999 receive that prefix
  transformation; indices 9,000 through 9,999 retain all 128 coordinate bits.
  This is a synthetic heterogeneous occupancy control, not a real trace.
- `complete_h10`, `complete_h14`: every coordinate is occupied. These are the
  common inputs accepted by unchanged official complete-tree CSA/SubCSA.
  Official TreePIR is not relabeled as a sparse h=128 implementation.

Every occupied value is the unchanged `tifs_revision_smt.default_value(slot,h)`:
SHA-256 of its documented domain, height and fixed-width coordinate. Leaf,
internal and default hashes use the existing domain-separated SHA-256 format.
Only the union of non-default occupied-proof records is served, giving
`N = 2*n - 2` records. The sorted original heap IDs fix record IDs for all methods.
No whole logical tree is materialized for the h=128 cases.

AB calls the existing `build_layout(..., color_strategy="activebalance",
refine_rounds=20)`, which invokes the original count-squared Hungarian algorithm.
Twenty is the scan budget; early termination and actual accepted moves are
reported separately. There is no sorting substitute, new refinement heuristic,
or lower-height fallback. PBC receives the identical record universe and public
intervals; the external native implementation constructs its own three-hash
placement and routes real plus dummy requests.

## Native interface

Files are `ab.json`, `pbc.json`, and (complete trees only) `treepir.json`. Each
contains the same 32 occupied target rank IDs, slots, known values and pinned root.
The runner can select a paired subset per repetition. `targets.needed` and
`targets.by_bucket` are post-recovery audit expectations, not online selectors.

The native command is:

```text
native_adapter/build/serialized_proof_bench INPUT_JSON OUTPUT_JSON WARMUP_COUNT
```

`records` is the server's payload. Public routing fields contain only record IDs,
interval endpoints, original proof levels and positions, without expected
digests. `record_intervals` covers every record exactly once. AB's
`bucket_intervals` follows sorted interval order. Official TreePIR's array follows
the original CSA bucket positions: a routing implementation must retain each
original position while sorting a separate search view. It must not use the
sorted search position as the original PIR index. PBC's `buckets`,
`bucket_intervals` and target `by_bucket` arrays are empty intentionally.

All methods use the requested native parameters: polynomial degree 8192,
coefficient bits [42,58,58,60], plaintext bits 28, first dimension 64, and logical
batch size equal to the input's occupied-proof width. These inputs do not claim
that a logical request is one ciphertext or that backend serialized bytes are
network packet bytes.

## Checks and official provenance

The generator checks exact record partitioning, disjoint same-color intervals,
and independently reconstructed interval routes against every occupied target's
heap-sibling set. It rebuilds and verifies all full proofs for n <= 20,000;
otherwise it checks a fixed uniform sample of 20,000 targets plus both extreme
ranks. Every checked proof also rejects a flipped bit in one used record. The
summary gives the actual count, including any overlap with the extreme ranks.
These are direct-hash input checks, not executed PIR recoveries.

Official CSA and SubCSA sources are pinned to TreePIR commit
`930063c5aefc441244abb4890fdf35383f3aa956`. Height 10 reuses the frozen official
output; height 14 compiles and executes the unchanged Java sources through the
existing serialization-only wrappers. Both validate every occupied target's
official index, while the digest at original heap node v is stored at swapped
node v xor 1. `official_source_audit.json` retains source hashes, commands and
reuse provenance; no Java algorithm is reimplemented.

## Existing pipeline distinctions

The historical balance studies measure structure and construction, not PIR.
The `verified_backend` suite executes real SimplePIR in a combined local harness;
its query-index manifests are not a separated client/server protocol. The CT
`runs_verified_evidence` suite executes real loopback TCP retrieval with retained
proof evidence, but it is a separate 512-record application experiment. It is not
pooled with the new synthetic input preparations or native measurements.

No applicable `AGENTS.md` was found in the workspace or its checked ancestors.

## Completed generation

All seven cases completed under the original algorithm and limits, without a
fallback or retry. Each method receives 32 paired occupied targets.

| Case | n | N | m | AB maximum bucket | Checked full roots |
|---|---:|---:|---:|---:|---:|
| uniform_n1000 | 1,000 | 1,998 | 13 | 154 | 1,000 |
| uniform_n10000 | 10,000 | 19,998 | 17 | 1,179 | 10,000 |
| uniform_n100000 | 100,000 | 199,998 | 21 | 9,552 | 20,002 |
| prefix64_n10000 | 10,000 | 19,998 | 17 | 1,181 | 10,000 |
| cluster90_n10000 | 10,000 | 19,998 | 27 | 1,088 | 10,000 |
| complete_h10 | 1,024 | 2,046 | 10 | 205 | 1,024 |
| complete_h14 | 16,384 | 32,766 | 14 | 2,354 | 16,384 |

All occupied routes were checked, including all 100,000 in the largest case.
For that case the original AB completed 20 scans and accepted 20 moves;
`build_layout` took 150.242281 s and the independent preparation process took
166.853279 s. Peak worker RSS was 5.806686 GiB. These are single input-construction
observations, not repeated performance estimates. They must not be pooled with
the separately scheduled native retrieval measurements.
