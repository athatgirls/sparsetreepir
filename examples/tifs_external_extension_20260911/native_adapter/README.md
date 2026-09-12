# Common VBPIR serialized proof adapter

This adapter uses the same pinned `VBPIR_PBC` `Client`, `Server`, `PirParams`, and utility implementation for PBC, AB, and official-CSA layouts. It measures a **same-process serialized proof pipeline**, without network transport. It is not a measurement of the original full TreePIR service or its fast indexing algorithm.

Sources: [TreePIR](https://github.com/PIR-PIXR/TreePIR), commit `930063c5aefc441244abb4890fdf35383f3aa956`; the underlying project is [Vectorized Batch PIR](https://github.com/mhmughees/vectorized_batchpir). `source_manifest.json` verifies copied official files against the pinned Git tree. The three cryptographic `.cpp` files are unchanged. `server.h` adds observational payload getters, and `database_constants.h` adds a missing standard include.

## Build and invocation

Build from the repository root in Linux using the portable entry point:

```sh
python3 reproduce/build_native.py --output .reproduce/build --jobs 2
```

See [`docs/NATIVE_REPRODUCTION.md`](../../../docs/NATIVE_REPRODUCTION.md) for
dependencies, fresh smoke runs, and the current-paper schedule. The output
directory must be new. The included `prepare_build.py` records how the vendor
snapshot was originally prepared from a broader checkout; source regeneration is
not required to compile the included files. The native executable accepts
`INPUT_JSON OUTPUT_JSON WARMUP_COUNT`.

The driver constructs one persistent server and client per invocation. It cycles over the first input targets for warmups, then measures every target once, in input order. It does not shuffle or replace targets; the outer experiment runner controls paired schedules and independent processes. A routing/recovery failure writes an error result and returns nonzero. There is no retry with a different placement or target.

The implementation supports a single vectorized group: `bucket_count <= poly_degree / first_dimension`. It requires `2 <= batch_size <= N`, so that PBC has at least three candidate buckets. Unsupported inputs fail explicitly. The process sets `OMP_NUM_THREADS=1` and a 10 GiB address-space limit.

## Input

```json
{
  "schema_version": 1,
  "mode": "ab",
  "height": 128,
  "root_hex": "64 hexadecimal characters",
  "default_hashes": ["level-0 digest", "... through level h-1"],
  "occupied_slots_hex": ["sorted, distinct, big-endian occupied coordinates"],
  "records": ["32-byte digest encoded as 64 hexadecimal characters"],
  "record_intervals": [{"left": 0, "right": 4, "level": 2, "record": 0}],
  "buckets": [[0]],
  "bucket_intervals": [[{"left": 0, "right": 4, "level": 2, "record": 0}]],
  "targets": [{
    "id": "paired target id",
    "slot_hex": "target coordinate",
    "value_hex": "known raw value as hexadecimal bytes",
    "needed": [{"record": 0, "level": 2}],
    "by_bucket": [0]
  }],
  "pir": {
    "poly_degree": 8192,
    "coeff_bits": [42, 58, 58, 60],
    "plain_bits": 28,
    "first_dimension": 64,
    "batch_size": 2
  },
  "seed": 20260911
}
```

The schematic arrays above are not a runnable tree. `mode` is `ab`, `pbc`, or `treepir`. For `pbc`, explicit `buckets`, `bucket_intervals`, and `by_bucket` are ignored. All IDs and indices are zero-based; intervals are inclusive occupied-rank intervals. There must be exactly one `record_intervals` entry per record. `needed` is optional independent audit data and is checked only after the timed pipeline; `by_bucket` is not trusted or used to select records.

For AB/TreePIR, each `bucket_intervals[b]` initially follows the same order as `buckets[b]`. The adapter builds a separate interval-sorted search view and preserves `record -> original bucket position`. In particular, official CSA bucket ordering is unchanged. The online code finds the coordinate rank and performs one binary search per bucket. Absent colors select an ordinary valid record index and discard the recovered value.

For PBC, a public laminar interval index finds the required records online. The batch is padded to `m` with distinct existing record IDs, without adding logical database records. The official three-candidate hash and recursive cuckoo insertion route that batch into `ceil(1.5m)` buckets. The upstream table-reuse bug is fixed by resetting the table on every query. The experiment RNG seed replaces time-based `rand` seeding only in routing; SEAL encryption randomness is unchanged. Unoccupied PBC buckets retain the original encrypted-zero-query behavior. Added dummy records and empty-bucket outputs are discarded locally.

## Correctness and measurements

The actual recovered bytes are restored to their original SMT levels; supplied defaults fill all other levels. The root is recomputed using `leaf=SHA256(00 || value)` and `parent=SHA256(01 || left || right)`, with child order determined by the known coordinate bits. Output includes every recovered bucket value and the complete bottom-up proof. Publisher-digest equality, expected needed-set equality, and wrong-value/coordinate/digest checks are additional untimed audits.

`query_ms` measures the unchanged encrypted query creation. `answer_ms` includes both the unchanged server computation and the original `merge_responses_chunks_buckets` packing step. `decode_ms` measures the unchanged client decoder. Query/answer roundtrip metrics serialize every ciphertext with `compr_mode_type::none`, wrap it with explicit count/length fields, and load fresh ciphertext objects into the same validated context. No `save_size()/2` estimate is used. `serialized_proof_wall_ms` runs continuously from online local routing through trusted-root verification; there is no socket, WAN, or TCP E2E claim.

`persistent_setup_wall_ms` includes parsing, public-index construction, PBC bucket construction, backend preprocessing, key generation, and key serialization/load. AB/CSA coloring occurs in external input generation and must be reported separately when comparing total layout construction costs. `server_preprocess_ms` and `client_keygen_ms` are separately available.

Public key payloads use real uncompressed SEAL saves/loads; the two directions are reported separately from query/answer traffic. Map and common metadata sizes refer to actually constructed binary payloads. The map is parsed back into client lookup tables; common metadata is counted as serialized payload without a complete client-bootstrap parser. These numbers are **not measured network bootstrap bytes**. Keys, plaintext-modulus parameters, and a `tc128`-validated SEAL context are recorded.

Storage includes logical active digests, replicated records, maximum-capacity padding, backend dimension padding, and the actual number of allocated NTT plaintext coefficients. NTT coefficient payload excludes object/allocator overhead. Peak RSS combines server, client, input/oracle data, public tables, and retained validation output; it is not isolated client or server memory. The driver does not claim a production deployment or a new cryptographic security result.
