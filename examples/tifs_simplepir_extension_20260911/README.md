# SparseTreePIR: native 32-byte SimplePIR experiments

The completed release contains seven fixed snapshots, four layouts, three fresh processes per cell, and ten measured proofs per process. Two additional warmups per process are excluded from performance statistics. Inspect `analysis/INDEPENDENT_VERIFICATION.json` for the actual completion and correctness status rather than inferring success from this planned scope.

Start with `analysis/simplepir_evaluation_brief.pdf` and `analysis/SimplePIR新增实验报告.md`. Publication figures are in `analysis/figures`; the academic subsection and table are in `analysis/paper_ready_simplepir_results.tex`. Full process, query and cost tables remain in CSV/JSON. The historical manuscript and preceding VBPIR release are preserved.

## Reconstruct and verify

The release archive deduplicates repeated per-run `input.json` copies. Their reconstruction checks the exact SHA-256 recorded before execution; it never regenerates experimental results. From the unpacked project root:

```sh
python3 scripts/restore_simplepir_run_inputs_20260911.py
python3 scripts/analyze_simplepir_extension_20260911.py
```

The package also preserves the frozen preceding VBPIR inputs, schedules and raw results needed for cross-backend checks. To independently recheck that previous experiment as well, first restore its deduplicated inputs using `restore_external_run_inputs_20260911.py`, then run `analyze_external_extension_20260911.py`. Optional old smoke records not present in the package are not needed for the previous formal-run verification.

## Build and reproduce new measurements

The pinned official SimplePIR core is included unchanged under `backend/upstream/simplepir`. No wider local repository is required to compile it. Linux, Go with CGo, and GCC are required; exact captured versions and raw environment are recorded under `runs` and `backend/build` in the workspace. Build and run from the unpacked root:

```sh
bash examples/tifs_simplepir_extension_20260911/backend/build.sh
python3 scripts/run_simplepir_extension_20260911.py --output examples/tifs_simplepir_extension_20260911/rerun
```

The recorded executable is included as `backend/recorded_bin/simplepir_proof_bench`; build outputs and caches are omitted. The runner refuses to overwrite existing observations. `--resume` requires an identical configuration, source and binary. The frozen canonical inputs are sufficient for rerunning; regenerating them from the preceding VBPIR snapshots uses `prepare_simplepir_extension_20260911.py`. The latter's PBC exporter directly includes the preserved official C++ utility and its header dependencies, and needs a C++ compiler plus Microsoft SEAL 4.3 headers at the path recorded in its build manifest. These SEAL headers are unnecessary for building or running the SimplePIR backend with the included inputs.

## What was measured

One private batch retrieves the non-default siblings of one sparse Merkle membership proof. Each recovered proof restores original levels and defaults and authenticates the same root. Flat-active initializes one database and reuses its hint and public A across independent full-database queries. PBC retains three placement copies; AB and First-fit partition the actual records. Unused query slots still invoke PIR. No baseline materializes a height-128 empty tree.

The backend uses native 256-bit (32-byte) long records. Only the official uint64 encoding/final-recovery boundary is extended to exact big integers. Init, true Setup, Query and Answer are unmodified. This is separate from the legacy eight-part implementation. The audit documents the official parameter row, actual query padding, one-query Answer semantics and private-randomness handling.

The measured path serializes and loads actual matrix messages in one process. It includes routing, cryptography, proof restoration and root validation, and excludes network delay. Setup excludes external tree and layout construction for all methods. The release separately records hint, expanded public A, directory, logical/raw/encoded database payloads, and combined-role peak RSS. Expanded A is this implementation's transfer policy, not a lower bound on SimplePIR communication. A seed optimization does not remove the database-dependent hint. An unrestricted complete-cache reference remains visible.

Three process means are the independent timing units. Within-backend AB/PBC ratios compare the same costs; absolute timings or differently encoded storage from different cryptosystems are not pooled. PBC positions match the original C++ utility, while the Go cuckoo wrapper has a disclosed insertion-order/RNG adaptation. First-fit remains an internal ablation. All negative observations and rounding effects are retained.

`PROTOCOL.md` records the premeasurement design. `backend/README.md`, `backend/source_manifest.json`, `inputs/README.md` and `audit/PROTOCOL_AUDIT.md` explain provenance and adaptation boundaries. `SOURCE_MANIFEST.json` hashes every archived payload; `PACKAGE_CHECK.json` records final ZIP integrity checks.
