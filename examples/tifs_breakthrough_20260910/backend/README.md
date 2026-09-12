# Standard long-record SimplePIR: bounded engineering control

The full 32-byte digest can use one SimplePIR query per color. The previous eight independent 32-bit calls are a limitation of the local scalar adapter, not a requirement of SimplePIR. This exploration implements the standard vertical long-record representation and tests the same policies on First-fit, ActiveBalance, and Nonempty-depth. It adds no new theoretical contribution.

Only new files under this directory and `backend/simplepir/tifs_packed_exploration_20260910.go` were created. The original 18,000-proof local measurements, the final 2,000-proof TCP measurements, their sources, and their data were not overwritten or pooled with this smoke.

## What was executed and checked

- Five adapter/dimension policies, each applied to all three layouts of the same frozen 512-record CT-derived SMT. The layouts have 1,022 active digest records, with 13/13/17 logical queries respectively.
- At every color, the real Go `Query`, `Answer`, and recovery path queried index 0, midpoint, last, one deterministic pseudorandom position, and index 0 again. All 1,075 returned real workload records matched the corresponding 32-byte file contents. Another 50 tests covered all-zero/all-one digests and padded-row cases with 1 and 33 records.
- The independent Python audit used the logged recovered first/last bucket records to assemble the minimum/maximum occupied-target proofs for every method/policy. All 30 complete proofs matched the frozen experimental SMT root. It did not read server digest files to fill missing proof entries.
- All 2,700 recorded hashes of private query state and all 1,125 complete-query hashes were distinct. Ninety independently sampled public seeds expanded identically into separate server/client A matrices. These are functional checks, not a proof of query privacy.
- The byte encoder for the eight-chunk baseline exactly reproduced the frozen TCP bootstrap and online byte totals for all three methods. The new optimized messages were encoded into `bytes.Buffer`, **not sent over TCP**. Report their matrix costs as a separate engineering control, not as new network measurements.

`packed_smoke.json` preserves each parameter shape, returned bytes, expected bytes, indices, input hash, state/query hashes, seed/A hashes, and cost totals. `packed_smoke_audit.json` has `status=pass`, raw/source hashes, and all check counts; `packed_costs.csv` contains the 15 compact cost rows. Runtime in the Go JSON is a diagnostic for this bounded local smoke, not a repeated benchmark or a speedup estimate.

## API and parameter reasoning

The pinned upstream is commit `e9020b03bf2872c75b8954e749e32408b5db87ed` of `ahenzinger/simplepir`.

`pir/database.go` already stacks the base-p elements of a record vertically. However, `MakeDB` accepts `[]uint64`, `ReconstructElem` returns `uint64`, and `SimplePIR.Recover` returns `uint64`. Merely changing `Row_length` to 256 cannot represent arbitrary 256-bit input or output. The new adapter therefore calls the unmodified `SetupDB`, writes the digits of each 32-byte value using `big.Int`, and replaces only the final recovery/reconstruction helper with a byte-returning version. The offset, modular subtraction, rounding, centered-digit correction, Query, and Answer remain the upstream algorithms. See `make256` and `recover256` in the new Go source.

All smoke cases retain the unmodified table parameters: LWE secret dimension 1,024; ciphertext modulus 2^32; error sigma 6.4; plaintext modulus p=991; and M<=8192. This is the first applicable row of the pinned `params.csv`. The existing in-memory squishing requirements also hold: p<=2^10 and logq>=3*10. This exploration did not run a new lattice estimator or independently certify a security level.

An exact integer check confirms `991^25 < 2^256 <= 991^26`; thus a digest needs 26 vertical field elements. The old eight 32-bit records each need four elements, totaling 32 before matrix padding. All cases verify `L % Ne = 0` and `L*M >= records*Ne`.

The square policy calls upstream `PickParams(records,256,1024,32)`. The wide policy uses the unchanged parameter selector with M=records and L=26: one row of logical records, each represented by 26 physical rows. Vertical growth does not increase M, the number of LWE samples; the upstream `ConcatDBs` comment states this reason for retaining LWE parameters. Its helper is not directly usable on the old adapters because it requires `Info.Num == L*M`, which the multi-element scalar representation generally violates. The new adapter uses the existing native vertical representation directly.

With 32-bit matrix elements and factor-three query padding, exact per-color costs are:

```
hint payload      = 4 * 1024 * L
expanded A        = 4 * 1024 * M
query payload     = 4 * 3 * ceil(M/3)
answer payload    = 4 * L
```

The old adapter sums these over eight independent instances. The packed adapter uses one. All dimensions are selected separately for each method's actual bucket size using the same policy, rather than optimizing AB alone.

## Public-seed handling

The pinned `InitCompressedSeeded` and `DecompressState` reset the package-global `bufPrgReader`. Calling them in the query client leaves the subsequent secret/error stream derived from a public seed. Blindly using those helpers in this adapter would therefore be unsafe.

`localSeededA` instead creates its own `NewBufPRG(NewPRG(seed))` reader and fills only A. The package-global private Query PRG remains initialized from `crypto/rand`, and each Query creates a fresh secret. A distinct 16-byte public seed is generated per packed color. Both sides independently materialize A and compare its encoded hash. The seed reduces transfer, not the expanded A allocation needed by this implementation. This local helper has not been integrated into the existing TCP client or into a malicious-server/freshness protocol.

## Exact costs on the CT snapshot

All entries below are **bytes**. `Online` is query-plus-answer matrix payload per proof, excluding framing. `Bootstrap encoded` is an actual in-memory serialization size, including Params/DBinfo, directory, occupied coordinates, A or seeds, hints, and the existing framing convention; it is not a new TCP measurement.

| Method | Policy | Hint | Expanded A | Online | Bootstrap encoded |
|---|---|---:|---:|---:|---:|
| First-fit | 8x32, square, A | 6,553,600 | 5,668,864 | 12,544 | 12,279,233 |
| First-fit | 256, square, A | 2,768,896 | 1,421,312 | 4,168 | 4,226,593 |
| First-fit | 256, square, seed | 2,768,896 | 1,421,312 | 4,168 | 2,805,281 |
| First-fit | 256, wide, A | 1,384,448 | 4,186,112 | 5,504 | 5,606,951 |
| First-fit | 256, wide, seed | 1,384,448 | 4,186,112 | 5,504 | 1,420,839 |
| ActiveBalance | 8x32, square, A | 8,519,680 | 6,815,744 | 15,808 | 15,392,350 |
| ActiveBalance | 256, square, A | 2,768,896 | 2,109,440 | 4,828 | 4,914,735 |
| ActiveBalance | 256, square, seed | 2,768,896 | 2,109,440 | 4,828 | 2,805,295 |
| ActiveBalance | 256, wide, A | 1,384,448 | 4,186,112 | 5,504 | 5,606,959 |
| ActiveBalance | 256, wide, seed | 1,384,448 | 4,186,112 | 5,504 | 1,420,847 |
| Nonempty-depth | 8x32, square, A | 7,471,104 | 6,848,512 | 14,784 | 14,383,745 |
| Nonempty-depth | 256, square, A | 3,194,880 | 1,748,992 | 4,908 | 4,981,352 |
| Nonempty-depth | 256, square, seed | 3,194,880 | 1,748,992 | 4,908 | 3,232,360 |
| Nonempty-depth | 256, wide, A | 1,810,432 | 4,186,112 | 5,944 | 6,034,032 |
| Nonempty-depth | 256, wide, seed | 1,810,432 | 4,186,112 | 5,944 | 1,847,920 |

Encoded online bytes add 32 bytes of batch/frame counts plus 48 bytes per scalar call to the matrix payload. Thus packed square FF/AB/depth are 4,824/5,484/5,756 encoded bytes. Seeds do not change online bytes. The 8-byte difference between FF/AB wide encoded bootstrap is JSON-header length, not a matrix-cost advantage.

The standard packing reduces square-policy AB online matrix payload from 15,808 to 4,828 bytes, about 3.27x. It does not reverse the FF comparison: packed-square FF uses 4,168 bytes, less than AB, with identical hint size; the wide policy ties their hint and online matrix sizes on this snapshot. A smaller maximum bucket is therefore not a guarantee of lower sequential-backend communication, even after removing the inefficient scalar adapter.

None of these candidates beats Full-cache on total transferred payload for this fixed snapshot. The frozen Full-cache application bootstrap is 65,566 bytes and its subsequent online transfer is zero. Even the smallest tested AB bootstrap, wide+seed, is 1,420,847 encoded bytes (about 21.67x larger), before any online query. Its hint alone is 1,384,448 bytes. The expanded A also remains materialized by the client. These results agree with the separate hint-floor/frontier analysis; this smoke does not establish a lower bound for other PIR schemes or a deployment advantage under other workloads.

## Reproduction

The existing WSL environment uses Go 1.22.2 and gcc 13.3.0; GOMAXPROCS=1. Run one bounded smoke process, not concurrently with timing experiments. Set `REPO` to the artifact root and run from the pinned upstream module so Go resolves its local dependency:

```bash
cd "$REPO/.tools/simplepir/simplepir-main"
go build -o "$REPO/examples/tifs_breakthrough_20260910/backend/packed_exploration" \
  "$REPO/backend/simplepir/tifs_packed_exploration_20260910.go"
"$REPO/examples/tifs_breakthrough_20260910/backend/packed_exploration" \
  -source "$REPO/examples/tifs_revision_20260910/ct_application/runs_verified_evidence/publisher" \
  -output "$REPO/examples/tifs_breakthrough_20260910/backend/packed_smoke.json" \
  2> "$REPO/examples/tifs_breakthrough_20260910/backend/packed_smoke.stderr.txt"
cd "$REPO"
python3 examples/tifs_breakthrough_20260910/backend/audit_packed_smoke.py
```

The source and binary hashes are in `packed_smoke_audit.json`. No upstream code needs modification, and the new Go file need not be copied into `eval/`. This command overwrites only the new exploration outputs named above; it does not run or overwrite the frozen manuscript experiments.
