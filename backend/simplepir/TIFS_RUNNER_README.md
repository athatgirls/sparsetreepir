# TIFS real-record runner (2026-09-10)

`tifs_full_proof_backend.go` is a separate extension of `smt_full_backend.go`.
The historical runner is unchanged. This runner executes the existing SimplePIR
API over eight 32-bit chunks per 32-byte digest. It returns recovered digest bytes
to a Python SMT verifier; it does not itself claim to implement networking or
malicious-server PIR.

## Build and call

The available Windows Go 1.19.13 runs, but Windows application control blocked the
bundled gcc. No security settings were changed. The verified build uses WSL
Ubuntu-24.04, Go 1.22.2 and gcc 13.3.0. These are new experiments, distinct from
the historical Ubuntu-22.04 measurements.

From WSL, with `$REPO` set to the workspace path:

```bash
cd "$REPO/.tools/simplepir/simplepir-main"
go build -o "$REPO/examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend" eval/tifs_full_proof_backend.go
"$REPO/examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend" -warmup 5 -gomaxprocs 1 -output result.json manifest.json
```

Build the single Go file explicitly; the `eval` directory contains several
independent programs. The canonical source is in `backend/simplepir/`; an identical
copy is placed in `eval/` for building within the upstream module.

`-output` is optional. If omitted, stdout is exactly one JSON object. Library
diagnostics are routed to stderr. The default `-gomaxprocs` is 1. Execution is
sequential even if a different scheduling limit is selected. No modeled
`server_parallel_ms` value is emitted.

## Compatible manifest

```json
{
  "scheme": "activebalance",
  "height": 128,
  "width": 1,
  "active_nodes": 2,
  "query_samples": 2,
  "warmup_queries": 5,
  "subdatabases": [
    {"color": 1, "records": 2, "record_bytes": 32,
     "database_file": "color_01.bin", "query_indices": [0, 1]}
  ]
}
```

Paths are relative to the manifest or absolute native paths. Files contain raw
consecutive 32-byte records. Zero-record files are padded with one zero dummy
record for querying. A width-zero manifest can still contain a positive
`query_samples` count, representing a singleton SMT with no PIR records.
Duplicate file/record-count entries share backend initialization (Flat-active),
while every logical color/slot still issues its scheduled query. Color labels in
the returned records are taken from the manifest even when setup is shared.

`-warmup N` overrides the manifest field. Warmup issues N **additional complete
batches**, cycling through the supplied target sequence. It does not consume or
delete any measured target. `targets[i].sample_index` remains the original
zero-based manifest query index. All chunk recovery checks also run in warmup.

## Output and accounting

- `setup` contains `pick_params_ms`, `make_db_ms`, `init_ms`, `setup_api_ms`,
  `total_setup_wall_ms`, `offline_hint_bytes`, and `public_shared_state_bytes`.
  The four API stages sum only
  their own intervals. Total wall includes reading the database files, slicing
  chunks, constructing parameters/DBs/hints, setup bookkeeping and expected-value
  copies. It excludes process launch, parsing the manifest, Python layout
  construction, client metadata preparation, and output serialization.
- `public_shared_state_bytes` counts the materialized matrices in `pi.Init`'s
  returned public shared state, using their element counts times four bytes
  (`pir.h` defines `Elem` as `uint32_t`). It sums eight chunk backends for each
  unique database file and does not count shared-file cache entries twice. It
  excludes matrix headers and allocator overhead. This is distinct from the
  database-dependent offline hint and **is not actual wire traffic**. A public
  seed can permit reconstruction of A under a suitable implementation; this
  runner calls `Init`, not `InitCompressedSeeded`, and does not measure that
  seed-based protocol. Do not silently equate either this matrix size or its sum
  with hint size to measured client download bytes.
- `parameters` exposes each logical slot's record count and actual SimplePIR
  matrix dimensions, plaintext modulus, LWE dimension, ciphertext modulus and
  noise parameter. Eight chunks share a parameter shape.
- `targets` contains `sample_index`, `recovered_records` (each with `color`,
  `query_index`, `record_hex`), `client_query_ms`, `server_answer_ms`,
  `client_decode_ms`, `backend_wall_ms`, protocol upload/download/total bytes,
  logical record query count and chunk query count.
- Each 32-byte record is reconstructed with the same little-endian chunk order
  used to create its eight backend columns. Every recovered 32-bit value is
  checked against the database; an error aborts with a nonzero exit status.
- Per-target backend wall time includes sequential operations, local correctness
  comparisons and 32-byte record assembly. It excludes Python target routing,
  final SMT proof assembly/root verification, networking and JSON serialization.
- Bytes mean `PIR message matrix element count * Logq / 8`, matching the existing
  backend accounting. They are **not measured serialized transport bytes**.
  JSON debug output carrying returned records is not protocol traffic.
- `completed_queries` counts only measured complete batches, excluding warmup.
  The runner does not silently drop failed queries or return a partial success
  JSON when an index or recovered chunk is incorrect.
- `process_peak_rss_bytes` reads Linux `/proc/self/status` `VmHWM` after retrieval
  and before JSON serialization. It is the **entire combined server/client runner**
  process's resident-memory high-water mark, including retained result records;
  it is not a client memory measurement. It also does not include a parent Python
  verifier or later JSON serialization. The value is null if the counter is
  unavailable, rather than zero. `process_peak_rss_scope` records this scope in
  every result. An external process monitor may observe a later/larger peak.

The root driver should preserve one JSON file per independent process run and
join `sample_index` to the client-only routing context. It should add separately
measured routing, proof assembly and root verification if reporting a broader
end-to-end scope; none of those operations are hidden in `backend_wall_ms`.

## Verified smoke checks

`scripts/verify_tifs_backend_smoke.py` passed on 2026-09-10:

1. Four occupied h=128 leaves: all four full records-to-proof-to-root checks pass.
2. Singleton h=128: m=0 and its root check pass.
3. Shared-file Flat-style slots: one unique initialization, two queries per
   target, four returned records checked against source bytes.
4. Deliberate out-of-range index: rejected with nonzero exit and no success JSON.
5. Warmup is excluded from the recorded target list.

The machine-readable report is
`examples/tifs_revision_20260910/backend_smoke/SMOKE_VALIDATION.json`.
These smoke timings are not a publishable performance sample.
