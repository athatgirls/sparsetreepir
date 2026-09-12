# SimplePIR serialized proof adapter

This isolated adapter uses the unchanged official SimplePIR `pir/` source at
commit `e9020b03bf2872c75b8954e749e32408b5db87ed`. The exact copied files and SHA-256
digests are in `source_manifest.json`. The dependency is named
`upstream/simplepir/` to avoid Go's special module-vendoring rules. It has no
external Go module dependencies and therefore no upstream `go.sum`.

## Build and run

The prepared source copy is self-contained. On Linux, from this directory:

```sh
bash build.sh
GOMAXPROCS=1 go test -v .
build/simplepir_proof_bench INPUT_JSON OUTPUT_JSON WARMUP_COUNT
```

`prepare_build.py` reproduces the source copy from the existing local official
checkout; it is unnecessary when using the packaged `upstream/` copy. The
command initializes one persistent state, performs `WARMUP_COUNT` requests from
the start of the provided target array cyclically, then measures each supplied
target once. A failed query produces a failed JSON report and nonzero exit code;
it is never replaced. The parent scheduler selects paired targets and runs
independent processes. `functional_smoke.py` is an excluded, four-method
correctness check, not an experimental sample generator.

## Input

The native input schema is retained: `mode`, `height`, `root_hex`,
`default_hashes` (bottom-up original levels), `occupied_slots_hex`, `records`
(32-byte hex), `record_intervals` (`left,right,level,record`, canonical record ID
order), `buckets` (actual record IDs in actual database position order),
`bucket_intervals` (same order as each bucket), `targets`
(`id,slot_hex,value_hex,needed`), `pir.batch_size`, and `seed`.

Modes are `flat`, `pbc`, `ab`, and `first_fit`. PBC additionally requires
`hash_candidates[record]`, containing exactly three distinct bucket IDs from the
official C++ hash exporter. The PBC layout must contain each record in precisely
those three buckets. Flat must supply exactly one bucket containing every
record. AB/FF partition the records and have disjoint requirement intervals
within each bucket. The field `targets[].needed` is an untimed oracle only.
`by_bucket` and any preselected target route are not used.

The client directory contains no record values. Public coordinates, intervals,
bucket IDs, PBC candidates, defaults and root are serialized as JSON and parsed
into a separate directory before routing. Flat/PBC find the needed records by
stabbing a public laminar interval forest, then pad to `m` distinct existing
record IDs. AB/FF binary-search each bucket's sorted interval view and preserve
the original database positions. All remaining query slots retrieve an ordinary
dummy record (or the zero record of a physically empty bucket) and discard it.

## Cryptographic and algorithmic boundaries

All layouts use `PickParams(U,256,1024,32)`, where `U` is the public maximum
actual bucket load. Every bucket in that layout uses the same rectangular
dimensions. Flat uses the full record count once. The supported experiments are
explicitly restricted to the unmodified official parameter-table row
`n=1024, logq=32, sigma=6.4, p=991, M<=8192`, with 26 base-p digits per record.
The driver checks the exact base-p capacity and row divisibility. Dimensions
vary with public layout capacity; parameter selection never depends on a target.
This uses the official LWE parameter choices and is not a new security estimate.

Ordinary `Init` creates the expanded public matrix A, and actual `Setup` computes
H=D*A and squishes the database. A and H are serialized, loaded into independent
client matrices, and counted. No fake setup, random hint, compressed-seed API,
or process-global secret-PRG reseeding is used.

The official `MakeDB`/`Recover` API takes/returns `uint64`. The adapter widens only
the standard vertical base-p input decomposition and final output reconstruction
to `big.Int` for a complete 256-bit record. Offset, modular subtraction, rounding,
centering, and one H*s multiplication per query follow official `Recover`.
`Init`, `Setup`, `Query`, and `Answer` are the unchanged official implementations.
The first request also compares the result with official `Recover` modulo 2^64,
outside timing. Tests cover zero, all-ones, high-bit, leading-zero, final-row and
repeated-index records. This is one 256-bit long-record request, not eight scalar
32-bit requests.

Flat initializes exactly one database, A and H, and reuses them for `m` queries.
Each query invokes `Answer(DB, MakeMsgSlice(singleQuery))` over the entire same
database. Supplying all `m` queries to one official `Answer` would partition its
rows and is deliberately not done. AB/PBC/FF initialize each physical bucket
once and issue one query per bucket. PBC retains empty-slot-first/random-eviction
cuckoo routing with a 500-recursion limit and a newly cleared table per request.
Its Go insertion order is the padded batch order and its experiment RNG is
independent of cryptographic randomness. Candidate placements are official;
the eviction trace is not claimed to match C++ unordered-map iteration.

## Timing and byte accounting

`queries` and `warmups` are separate arrays. `serialized_proof_wall_ms` includes
online routing, query generation, actual query encode/decode, answer generation,
actual answer encode/decode, complete 32-byte recovery, original-level/default
restoration and trusted-root verification. Separate timings expose those stages.
All calls are sequential (`GOMAXPROCS=1`, `OMP_NUM_THREADS=1`). There is no network.
JSON-oracle comparisons, fingerprints, official uint64 recovery cross-checks,
and three negative root checks are outside timing.

Each matrix envelope is encoded and parsed: 8-byte message count, per-message
8-byte matrix count, per-matrix 8-byte rows and columns, then actual uint32
little-endian entries. All current messages have one matrix. Therefore an online
envelope has `8 + 24*calls + matrix_payload_bytes` bytes, including query padding
to `3*ceil(M/3)`. The server answers loaded queries; the client decodes loaded
answers. Expanded A/hint singleton envelopes each have 32 framing bytes. Setup
JSON components are also actually serialized and parsed; the reported sum is
called `bootstrap_framed_components_bytes`, not a transported protocol packet.

`setup` reports real Init/Setup times, public A and hint matrix/framed bytes,
serialized public metadata and DB-info bytes, logical active/replicated/padded
record payloads, unsquished matrix payload and materialized squished database
payload. `bucket_metrics` provides every physical database's parameters and
payloads. `initialized_databases=1` for Flat. `persistent_setup_wall_ms` includes
input/validation and backend preparation but excludes external tree/layout
construction and the final pre-request garbage collection. A is counted as
server-published public data; no client upload is required by this setup choice.

`combined_peak_rss_*_bytes` is process peak RSS covering both roles, retained
input/oracles, directories, temporaries and outputs. It is not isolated client
memory. Go's soft memory limit is 8 GiB; the tested instances are much smaller.
`encoded_db_bytes` is exact materialized matrix storage, excluding allocator and
language-object overhead. Setup/online counts do not assert a total communication
advantage without an explicit repeated-query amortization calculation.

Each request emits all recovered bytes with bucket/position/record IDs and
original levels, the entire bottom-up proof, the computed root, and results for
bit-flipped sibling, wrong coordinate and wrong known value. These artifacts
allow an independent Python verifier to recompute every proof.
