# Backend integration status

This note separates executable SparseTreePIR backend integrations from models,
prototypes, and prior-art artifact smoke tests.

## Included in the Linux setup

| Backend | Status | Why it is included |
| --- | --- | --- |
| SimplePIR | SparseTreePIR executable integration | The setup script clones `https://github.com/ahenzinger/simplepir.git`, checks out a pinned commit, and installs `backend/simplepir/smt_full_backend.go`. This runner consumes SparseTreePIR color-subdatabase manifests and retrieves 32-byte digests as eight 32-bit chunks. |
| PIANO | SparseTreePIR executable backend-shape runner | The setup script clones `https://github.com/wuwuz/Piano-PIR-new.git`, checks out a pinned commit, and installs `backend/piano/smt_layout_benchmark.go`. This runner consumes the bucket-size vector induced by SparseTreePIR/PBC-SMT layouts. |

These are the two backends that should be described as current concrete
backend evidence in the paper.

## Already in the repository, but not a production backend integration

| Backend/model | Status | How to describe it |
| --- | --- | --- |
| LWE-style prototype | Local randomized prototype in `scripts/lwe_pir_backend.py` | A sensitivity check, not a production PIR artifact. |
| Two-server XOR PIR model | Analytic communication model inside the multi-backend scripts | A model row, not a downloaded backend. |
| TreePIR Java indexing artifact | Prior-art artifact smoke/indexing results are recorded under `examples/treepir_indexing_results/` and `notes/treepir_artifact_backend_note.md` | Evidence that the prior TreePIR artifact can run on perfect-tree inputs, not a SparseTreePIR backend. |
| TreePIR PBC / VBPIR / Spiral smoke tests | Prior-art artifact checks recorded in `notes/treepir_artifact_backend_note.md` | Useful artifact evidence, but not final SparseTreePIR integrations until we export active color stores into each backend's expected database/query format. |

## Not included yet

| Backend | Current blocker | Next step |
| --- | --- | --- |
| Spiral | Requires the Spiral build stack and backend-specific database/export format. The public implementation uses CMake/vcpkg/HEXL and parameter-selection scripts. | Add a SparseTreePIR-to-Spiral exporter, then a Linux setup path for `menonsamir/spiral`. |
| YPIR | Requires AVX-512 support and a compatible Linux toolchain. | First check the Linux server with `lscpu | grep avx512`; then add a SparseTreePIR exporter and runner. |
| SealPIR / SealPIRplus | The TreePIR route is service/orchestrator-style and needs heavier SEAL/gRPC/Protobuf setup. | Treat as a separate artifact-engineering pass on a prepared Linux server. |
| XPIR or other older PIR libraries | Not currently tied to the paper's main backend comparison. | Only add if we want a broader artifact appendix rather than a focused paper evaluation. |

## Policy for the paper

Use precise wording:

- Current concrete backend evidence: SimplePIR and PIANO.
- Additional backend-shaped evidence: LWE-style prototype and two-server XOR model.
- Prior-art artifact smoke tests: TreePIR/PBC/VBPIR/Spiral-format runs.
- Future work / artifact extension: production Spiral, YPIR, SealPIRplus, and backend-aware packing.

Do not claim that SparseTreePIR has already been fully integrated with every
production PIR backend. The honest claim is that SparseTreePIR changes the
PIR-facing database shape, and we validate that shape with two executable
backends plus supporting models/artifact checks.
