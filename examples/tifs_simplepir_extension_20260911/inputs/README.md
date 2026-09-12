# Frozen SimplePIR extension inputs

Producer: `scripts/prepare_simplepir_extension_20260911.py`.

All seven cases have `ab.json`, `pbc.json`, `flat.json` and `first_fit.json`.
The frozen source is `examples/tifs_external_extension_20260911/inputs`.
Records, occupied slots, values, original proof levels, default hashes, trusted
roots, AB bucket membership/order and all 32 pool targets are reused exactly.
No large SMT was rehashed and no AB construction was repeated.

The primary correctness marker is each case's `cross_backend_audit.json` with
`status: pass`; it pins all four final output files. `source_vbpir_schedule.json`
is a byte-identical copy of the prior 48-process VBPIR schedule.
`target_schedule.json` reduces its duplicate method rows to the same 21
case/repeat pairs, each with the original ordered ten `pool_indices` and
`target_ids`. It does not draw new targets. The prior routing seed is
2026091103 + 1009*repeat; method execution-order randomization is separate.

## Layouts and public routing

- **AB:** original 20-scan Hungarian result, copied unchanged.
- **First-fit:** original `first_fit_coloring` on the forest reconstructed by
  original `build_interval_forest` from frozen record intervals. Its smallest
  permitted color at each ancestor path is unchanged. Empty `covers_leaves`
  lists avoid unnecessary expansion; neither called function consumes them.
  Every occupied target's interval route is checked against its actual heap
  sibling IDs, including all 100,000 targets in the largest case.
- **PBC:** each record has exactly three distinct candidate buckets, obtained by
  directly including and calling the frozen native `utils::get_candidate_buckets`
  in a C++ exporter. Its nonce loop resolves repeated choices. Bucket count is
  ceil(1.5m). Records are inserted in ascending record-ID order, exactly as in the
  measured native adapter. Each record is stored three times, with no within-bucket
  repetition. `official_pbc_candidates.tsv` retains all candidates; JSON
  `hash_candidates` and `buckets` retain the complete placement.
- **Flat-active:** `buckets=[all record IDs]` represents one physical database.
  The public logical width remains m, requiring m repeated full-database queries
  with shared persistent database, hint and public A. It must not create m
  independently initialized copies of the same database.

`bucket_intervals` remains in exact bucket-position order. Structured AB/First-fit
rows are disjoint and sorted. PBC and Flat rows may overlap, so their online
needed-record selection uses the common `record_intervals` forest instead.
`targets.needed` and `targets.by_bucket` are only untimed audit expectations.

## Common backend policy

The final `simplepir` metadata specifies native 256-bit records (32 bytes), one
record part, and the native base-p long-record encoding. The common parameter
selection policy is `PickParams(U, 256, 1024, 32)`, with U the public maximum
bucket load (N for Flat), and expanded public A. Resulting matrix dimensions and
base-p digit counts must be measured and reported by the backend. All buckets
within a layout use that layout's selected dimensions. `pir.batch_size` remains
m; old BFV-only parameters are not carried as SimplePIR parameters.

The first preparation contained an obsolete eight-by-32-bit metadata note. This
was corrected before formal SimplePIR measurements. Each
`metadata_correction.json` preserves the old/new file hashes and verifies that
every field other than `simplepir` and `pir` remained identical. Final hashes are
in `cross_backend_audit.json`. The historical VBPIR files were not modified.

## Cross-backend evidence and limits

The audit checks the PBC and AB bucket-load vectors against every frozen native
result, then checks every filled recovered record/position pair (including dummy
records), actual recovered digest bytes, original levels and recomputed SHA-256
roots in all native measured queries and warmups. It separately validates PBC's
empty-slot sentinels. Across seven cases it covers 42 native result files and
504 full roots. All four new inputs preserve their source common fields and
target values/coordinates/needed records. Per-case audit files retain source
results, inputs, schedule and producer hashes.

This proves input/placement consistency and checks the retained native recovery
evidence. It does not claim fresh C++ and Go cuckoo executions choose identical
random routes. The Go adapter must disclose its insertion/randomness policy,
retain routing failures, and make a real PIR invocation for each public request
slot. Input preparation runs no new PIR or performance benchmark.

To reproduce in a fresh directory with the existing Linux C++/SEAL environment:

```text
python scripts/prepare_simplepir_extension_20260911.py --cases all --output FRESH_DIRECTORY
```

The exporter source, executable, compiler information, official-header hash and
compile command are retained in `_hash_exporter/`. Historical inputs and results
are always read-only.
