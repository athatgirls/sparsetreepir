# Independent SimplePIR analysis

Generator: `scripts/analyze_simplepir_extension_20260911.py`. This directory contains derived evidence only; the analyzer never executes PIR or changes raw runs.

The formal experiment is complete only with all 7 cases × 4 methods × 3 processes: 84 processes, 840 measured proofs, and 1,008 proofs including warmups. Missing, failed, invalid or unauthenticated processes remain explicit. A successful smoke is `smoke_passed`, never formal `passed`.

Observed formal outcome: all 84 scheduled processes executed; 83 completed. The `prefix64_n10000 / pbc / repeat0` process reached the configured 500-attempt cuckoo cap while routing its eighth measured target (target 3455, zero-based measured ordinal 7). Its two warmups and seven previously returned measured proofs independently authenticate. Therefore 837 measured proofs and 168 warmups (1,005 total) authenticate, with status `audited_with_observed_failures`. The 830 measured proofs from complete processes enter performance summaries; the seven partial proofs remain separate. There are 27 complete three-process cells; the remaining PBC cell has two successful processes and is explicitly conditional on success. No additional repetition replaces the failure.

Files produced after verification:

- `query_measurements.csv`: measured proofs only; individual queries are nested within a process and are not treated as independent experimental repetitions.
- `all_proof_verification.csv`: all warmup and measured proofs, with independent root/negative-check flags.
- `partial_query_measurements.csv`, `failure_audit.json`: authenticated results preceding the observed failure, excluded from complete-process performance estimates, and the failed-process diagnosis/first uncompleted target.
- `process_means.csv`: the independent statistical units, including setup/state and source/result hashes.
- `aggregate_results.csv`: mean and sample standard deviation of process means; descriptive structural parameters are not averaged.
- `paired_comparisons.csv`: paired PBC/Flat/First-fit minus AB differences. Positive differences favor AB. The df=2 95% Student-t interval exists only for three matched process means. Mean paired ratios and ratios of aggregate means are different quantities.
- `results.json`, `INDEPENDENT_VERIFICATION.json`: machine-readable results and completeness/provenance/verification status.

The auditor derives record-support intervals and proof needs from the original uncompressed heap identifiers, checks every recovered real and dummy digest and bucket position against frozen records, reconstructs roots from decoded bytes and defaults, and independently rejects changed siblings, coordinates and known values. It checks the original VBPIR targets, snapshot identity, frozen AB placement and official PBC placement. It does not assume the cryptosystems or cuckoo eviction traces are identical.

Public A, hint, DBinfo and metadata are counted separately. Actual binary frame lengths are recomputed from matrix dimensions using the source-reviewed encode/decode format. The raw matrix wires are not retained, so the Python audit does not claim to independently rerun lattice decryption. The Go source consumes decoded query and answer objects and actual hints. Native secret/query uniqueness flags are sanity checks, not a security proof.

`full_cache_reference_bytes` counts active 32-byte digests plus compact JSON with the common height, root, default hashes, occupied slots, record intervals and batch width. It omits method, buckets and hash candidates. `digest_only_cache_bytes` is also listed. This is a concrete reference using shared directory information; neither value is labeled minimum necessary client state. The protocol uses expanded A; seeded A transmission is an available optimization outside this particular measured policy.

The timer is local serialized proof processing, without network latency. Setup excludes external tree/layout construction; combined peak RSS includes both roles and audit buffers. These boundaries apply to favorable and unfavorable results alike.

Nine bounded mutation checks also passed; see `../audit/VERIFIER_MUTATION_CHECKS.json`. Cloned outputs were rehashed after mutation, so forged recovered digests/positions/proofs, warmup flags, frame/hint costs, Flat state count and security parameters were rejected by semantic checks rather than file-hash mismatch alone. An empty outcome list cannot pass. These tests did not execute PIR or modify raw evidence.
