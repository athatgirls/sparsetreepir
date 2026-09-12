# Certificate-record audit over loopback TCP

The final evidence is **runs_verified_evidence/**: four methods × five independent
client/server process pairs × 100 measured targets = 2000 complete proofs.
First-fit, ActiveBalance, Nonempty-depth and Full-cache use paired targets.
The earlier **runs/** contains a three-method, 1500-proof development run without
retained proof records; it is preserved but is not pooled into final statistics.
smoke_v1 failed on an encoding-name typo before any measurement; smoke_v2 passed.

## Data and threat model

source/ freezes Google Argon2026h2 CT entries 0–511 and the official log list.
The raw API records include certificates/precertificates. The source manifest
records the actual requests, retrieval time, per-response hashes and CSV hash.
Coordinate = first 128 bits of SHA256(raw leaf_input); value = its full hash.
The publisher constructs a new SMT and locally pins its root in the client input.
This does not validate the native CT root, log consistency, certificate chain or
revocation status. The root is a trusted local input, not a signed publication.
Uniform target selection is controlled, not an observed browser workload.

The honest-but-curious mirror server loads the public snapshot. The client has
only the selected raw records and root initially. It receives all routing
metadata, occupied coordinates, parameters, expanded public A, hints, or the full
cache through TCP. The client does not read server database files. One persistent
connection is bound to 127.0.0.1 per process pair. Each PIR request contains a
fixed batch of eight independent 32-bit chunk queries per logical color.

## Reproduction

Canonical source: backend/simplepir/tifs_tcp_certificate_backend.go.
Build that file alone, because the module eval directory contains other mains.
From WSL Ubuntu-24.04:

```bash
cd /path/to/sparsetreepir
cp backend/simplepir/tifs_tcp_certificate_backend.go .tools/simplepir/simplepir-main/eval/tifs_tcp_certificate_backend.go
cd .tools/simplepir/simplepir-main
go build -o /path/to/sparsetreepir/examples/tifs_revision_20260910/ct_application/tifs_tcp_certificate_backend eval/tifs_tcp_certificate_backend.go
cd /path/to/sparsetreepir
/var/tmp/tifs_revision_20260910_venv/bin/python scripts/run_tifs_ct_application_20260910.py --samples 100 --repeats 5 --warmup 5 --output examples/tifs_revision_20260910/ct_application/new_reproduction
```

Use a new output directory; the driver rejects overwriting completed summaries.
The publisher uses the existing Hungarian ActiveBalance and existing First-fit;
this is separate from the sorting implementation scale study. All process pairs
run serially with GOMAXPROCS=1. Each pair has a 120-second total timeout. The
environment JSON identifies WSL, Go, Python, CPU, seeds and measurement scope.

The retained measured source and binary are in
runs_verified_evidence/source_snapshots/. source_manifest.json pins their hashes;
dependency_source_hashes.json records PIR and coloring dependencies.
The earlier development program and binary remain in runs/source_snapshots/.

## Records and independent verification

Each method/repeat directory contains server/client JSON, command arrays, ready
address/PID, and stderr. Client records retain actual used proof sibling bytes as
`recovered_siblings: [{level, digest_hex}]`, ordered by level, for every audit.
The retention happens after the timed interval but can affect memory and later
garbage collection; final runs use this instrumentation consistently.

The independent standard-library script
scripts/audit_tifs_ct_tcp_20260910.py rebuilds the tree from raw CT records and
checks all 18,476 recovered sibling records, 2000 roots/corruptions, paired targets,
socket byte counters, source pins and five-pair summary statistics. Its result is
manuscripts/tifs/revision_20260910/generated/ct_tcp_independent_audit.json.
The report-generation script scripts/summarize_tifs_ct_application_20260910.py
reads the final runs and produces generated/ct_application_results.tex and
notes/ct_application_findings.md. It never runs performance measurements.

## Accounting

Audit time continuously covers record decoding/hash, routing, Query,
serialization, actual TCP transmission, Answer, answer deserialization, Recover,
proof assembly and the 128-level root check. Full-cache measures the same
record/hash/routing/root-check work without network/PIR. Warmup audits and
post-timing corruption/evidence checks are excluded.

Bootstrap is separately timed from connection setup to reception,
deserialization and directory parsing. It includes actual transfer of metadata,
occupied slots, parameters, full public matrices and hints, or the cache package.
It excludes earlier publisher/server preparation and subsequent one-time default
hash-chain preparation. No continuous cold first-query total was measured.
The server's setup_ms is only its initial PIR construction phase, before
bootstrap serialization; it is not complete server preparation time.

Bytes count successful socket application reads/writes including all framing,
not TCP/IP headers or retransmissions. Both endpoints' counters agree. RSS is
each role's process peak VmHWM, including runtime and transient allocations.
This is loopback, not WAN latency. Full-cache is a real initial download followed
by zero network requests. Its substantially lower costs on this fixed snapshot
are retained as a limitation; no general cache advantage or robust depth
speedup is claimed for ActiveBalance.
