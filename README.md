# SparseTreePIR

Reproducibility artifact for **SparseTreePIR: Target-Private Retrieval of Sparse Merkle Proofs via Interval Coloring**.

Release: **2026-09-12-current-paper**. Start with the commands below and the [result-to-evidence map](docs/RESULTS.md).

SparseTreePIR retrieves the non-default sibling digests needed for **one complete sparse Merkle proof** as a structured batch. Interval coloring puts simultaneously required digests into distinct databases; ActiveBalance (AB) balances their loads. The client restores public default digests at their original levels and checks the trusted root. Here, batch retrieval refers to the multiple nodes of one proof.

The main experiments compare AB with PBC on **SimplePIR and VBPIR**, with First-fit/Flat-active ablations and official TreePIR CSA complete-tree controls. Supporting directories contain the correctness, workload, theory, construction, and TCP experiments cited by the supplement.

## Start here

| Task | Entry point |
|---|---|
| Audit frozen native run records and recovered proofs | `python3 reproduce/verify.py --output ../sparsetreepir-audit` |
| Build the two native backends on Linux | `python3 reproduce/build_native.py --output ../sparsetreepir-build` |
| Execute a short fresh test and audit it | `python3 reproduce/run_native.py --build ../sparsetreepir-build --output ../sparsetreepir-smoke --mode smoke` |
| Regenerate Tables III–IV, S2 and Figure 3; check the Table II example | `python3 reproduce_paper_results.py --output ../sparsetreepir-figures` |
| Check release file hashes | `python3 verify_release_files.py` |
| Check supplemental proof records and capacity certificates | `python3 reproduce_supplement.py --output ../sparsetreepir-supplement` |

Use a new output directory for every command. Archived observations are never overwritten by these entry points. A frozen-evidence audit reconstructs and checks recorded recovered bytes; it does not rerun cryptographic operations or reproduce the old timings. A smoke run checks the executable pipeline and is not a substitute for the manuscript's repeated experiments.

Use Python 3.12+ for the portable entry points. Install figure/theory dependencies with `python3 -m pip install -r requirements.txt`. Building/running the native backends requires Linux, a C++17 toolchain, CMake >=3.22, Go >=1.18, and OpenSSL/zlib/zstd development libraries. The VBPIR build helper uses pinned SEAL 4.3.2; an existing compatible installation can be supplied. See [native reproduction](docs/NATIVE_REPRODUCTION.md) for prerequisites, source pins, full-run commands, memory requirements, and output definitions, and [supplement reproduction](docs/SUPPLEMENT_REPRODUCTION.md) for the supporting checks.

## Reported experiment scope

The main numerical cohorts comprise 72 independent processes, 720 measured proofs, and 144 warmups:

- SimplePIR, uniform 1k/10k/100k occupied leaves: AB, PBC, Flat-active, First-fit (36 processes).
- VBPIR, the same uniform snapshots: AB and PBC (18 processes).
- VBPIR, complete trees of heights 10 and 14: AB, PBC, and official TreePIR CSA (18 processes).

Each process uses two warmups and ten measured targets. Compare layouts within a backend. Reported processing time includes routing, cryptographic processing, serialization, recovery, and root verification in one process; network delay and initialization are separate. Initialization, client state, encoded server storage, and the Full-cache reference are retained.

The source archives also contain prefix-concentrated and clustered sensitivity cohorts. All executed records in those cohorts are retained, including the partial SimplePIR PBC routing run. The independent verifier reports 83 complete SimplePIR processes and one audited partial process, not an all-successful full suite. The 72-process main cohort has its own explicit selection manifest. See [results and provenance](docs/RESULTS.md).

## Repository structure

- `reproduce/`: portable build, fresh-run, and frozen-audit entry points.
- `scripts/`: experiment code and the dependency closure used by retained studies.
- `examples/tifs_simplepir_extension_20260911/`: native 32-byte SimplePIR implementation, inputs, observations, and analyses.
- `examples/tifs_external_extension_20260911/`: native VBPIR implementation, PBC/CSA sources, inputs, observations, and analyses.
- Other selected `examples/` directories: evidence cited in the supplement.
- `datasets/`: fixed input coordinate sets and their provenance.
- `paper-results/`: current numerical table/figure generators, frozen summaries, and included vector figures.
- `provenance/`: publication scope, original archive manifests, and declared release-copy transformations.

Third-party implementations remain subject to their original notices; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Source availability alone does not grant an additional project-wide license.
