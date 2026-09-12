# Frozen Fuel layout transfer to TCP SimplePIR

A max-bucket improvement does not automatically reduce real PIR cost. The separate capacity-22 witness lowers U from the frozen AB value 23 to the proven optimum 22, but both layouts transmit exactly 9,536 online application bytes per proof. The witness needs 32,768 more bootstrap bytes. Its paired timing interval includes zero improvement. First-fit uses fewer online/bootstrap bytes, and full caching dominates this small fixed snapshot.

## Exact comparison and security/interface scope

All methods use the same 100 occupied slots, height 128, 198 original 32-byte sibling digests, deterministic experimental leaf values, and root 283ea1495be5cd0619e21c176a986dab657f1b29ecf35d8309e94cb1f9599ecb. First-fit and AB binary directories are byte-for-byte identical to the old frozen layouts. The new witness layout is checked against every original positional record and every target. It is an independent exact feasible assignment, **not** AB, the small-palette recoloring prototype, or a timed scalable construction.

The prior TCP client only accepted raw CT records and derived slots from their hashes. Applying it unchanged would rekey Fuel and violate this experiment. A new derived Go file therefore accepts an already-known 16-byte slot and 32-byte value; the client receives only these selected inputs and the pinned root locally. All public lookup and PIR state arrives through TCP. The original backend file is preserved. Query/Answer/Recover, eight independent 32-bit chunks per digest, serialization, timing boundaries, and PickParams(records,32,1024,32) are retained.

The measured parameters use lattice dimension 1024, logq=32, sigma=6.4 and plaintext modulus 991. There are nine logical PIR slots / 72 chunk calls for all three PIR layouts. The server enforces a fixed batch size, and unused slots use valid dummy queries. This is a loopback, fixed-snapshot, known-value membership experiment, not a native Fuel service, hidden-occupancy protocol, or certificate application.

## Five paired process means

Each repeat starts a fresh server and client process, uses one persistent loopback TCP connection, excludes five warmups, and measures all 100 distinct targets in a new deterministic shuffled order. The same target order is used by every method; method order is separately shuffled. All 20 process pairs run serially with GOMAXPROCS=1 on the recorded WSL environment. CIs below use the five process means, not 500 target observations.

| Layout | U | Query ms | Server ms | Recover ms | E2E ms | 95% CI for E2E mean | Upload / download bytes |
|---|---:|---:|---:|---:|---:|---|---:|
| First-fit | 58 | 5.419153 | 0.023296 | 0.222794 | 6.009418 | [5.789531, 6.229305] | 4336 / 4304 |
| AB | 23 | 5.557357 | 0.018622 | 0.293551 | 6.239323 | [5.831180, 6.647465] | 4336 / 5200 |
| OPT witness | 22 | 5.312694 | 0.017778 | 0.286736 | 5.980383 | [5.693312, 6.267453] | 4336 / 5200 |
| Full-cache | 198 | 0.000000 | 0.000000 | 0.000442 | 0.028301 | [0.025446, 0.031155] | 0 / 0 |

Full-cache U=198 denotes the cached payload database, not a 198-record PIR query; it has zero online queries. All timing components and CIs are retained in process_mean_CIs.json.

| Layout | Bootstrap bytes | Bootstrap ms | Metadata + slots bytes | Hint bytes | Expanded A bytes | Client peak RSS MiB | Server peak RSS MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| First-fit | 4938178 | 16.027485 | 4842 + 1600 | 2621440 | 2293760 | 21.260 | 29.626 |
| AB | 5888474 | 18.555154 | 4842 + 1600 | 3538944 | 2326528 | 23.307 | 30.039 |
| OPT witness | 5921242 | 17.852132 | 4842 + 1600 | 3538944 | 2359296 | 23.176 | 30.235 |
| Full-cache | 12830 | 0.976923 | 4778 + 1600 | 0 | 0 | 5.475 | 4.075 |

Bootstrap includes actual serialized directory, occupied slots, Params/DBinfo, full public A, hints or the full cache, plus framing. Full-cache sends 6,336 digest payload bytes and has 12,830 total bootstrap bytes. RSS values are means of five separate process peaks from Linux VmHWM; they are not isolated logical client-state sizes. The full per-process values and CIs are available.

## Why the capacity gain does not become a bandwidth gain

The AB loads are (23,22,22,21,22,22,22,22,22); the witness has nine loads of 22. A 23-record and a 22-record chunk both select L=12, M=8. The 21-record AB bucket uses L=12, M=7; making it 22 changes its M to 8. SimplePIR pads query length to a multiple of DBinfo.Squishing=3, so both M=7 and M=8 send a 9-element query. Answers have the same L=12. Consequently upload and download shapes are identical between AB and the witness.

Expanded A is not padded in the same way: changing M=7 to M=8 adds 8 × 1024 × 4 = 32,768 bytes. Hint dimensions do not change. The server output records each color/chunk Params and DBinfo; the independent auditor derives exact query/answer wire bytes from those dimensions and verifies the socket counters.

Paired timing comparisons (baseline minus witness, positive favors witness):
- First-fit: mean difference 0.029036 ms; 95% interval [-0.114048, 0.172119] ms. Mean of paired E2E ratios = 1.005278.
- AB: mean difference 0.258940 ms; 95% interval [-0.307234, 0.825113] ms. Mean of paired E2E ratios = 1.045138.

Both intervals contain zero. These five paired runs do not establish a reliable latency advantage of the exact witness. This does not prove equality or exclude smaller effects; bytes and matrix sizes, unlike timing, are deterministic here. The experiment supports a narrow negative result: optimizing U alone can leave online cost unchanged and increase initialization state.

## Accounting and reproduction

Warm E2E continuously includes known-value hex decoding, public-directory routing, query generation, serialization, actual loopback request/response, server Answer, Recover, proof assembly and root verification. Bootstrap, process launch, earlier publisher/server setup, and post-timing corruption/evidence checks are separate. Wire counters include successful application reads/writes and framing, excluding TCP/IP headers and retransmissions. Full-cache uses the same client proof task after its one-time download.

Linux/WSL reproduction needs Python 3 with matplotlib (an existing imported layout helper uses it), Go and a C compiler for the unchanged cgo backend. Run the following from the project root. The module is .tools/simplepir/simplepir-main/go.mod; it has no external Go requirements or go.sum. Build only the new Go file, using a new binary name to preserve the measured binary:
```bash
project_root="$PWD"
cd "$project_root/.tools/simplepir/simplepir-main"
go build -o "$project_root/examples/tifs_layout_transfer_20260910/system/tifs_layout_transfer_tcp_rebuilt" "$project_root/scripts/tifs_layout_transfer_tcp_20260910.go"
cd "$project_root"
python scripts/run_layout_transfer_tcp_20260910.py --binary "$project_root/examples/tifs_layout_transfer_20260910/system/tifs_layout_transfer_tcp_rebuilt" --samples 100 --repeats 5 --warmup 5 --output examples/tifs_layout_transfer_20260910/system/new_reproduction
python scripts/audit_layout_transfer_tcp_20260910.py --runs examples/tifs_layout_transfer_20260910/system/new_reproduction --output examples/tifs_layout_transfer_20260910/system/new_reproduction_audit.json
```

The runner refuses an output directory containing a measured summary. runs/ is the sole formal 20-pair result. smoke_v2/ is an 8-proof development check and is not pooled. The first smoke/ stopped before measurements on a Python tuple/list comparison; that input check was fixed before smoke_v2 and the formal run.

Run `python scripts/audit_layout_transfer_tcp_20260910.py` for standard-library-only reproduction checks. It does not import the SMT, layout, or measurement implementation. It independently rebuilds the frozen root, validates 792 stored records across four layouts, verifies all 13,760 recovered sibling records and 2,000 proofs/bit flips, and checks paired targets, process IDs, fixed wire shapes, socket byte conservation, matrix-derived bytes, source pins, and statistics. Report: independent_raw_audit.json.

run_summary.csv and query_measurements.csv accompany all raw client/server JSONs; every result retains recovered sibling digests. runs/source_snapshots/ preserves the derived source/binary and original TCP source, while source_manifest.json and dependency_source_hashes.json pin the environment inputs. The report and figure are generated without rerunning measurements.
