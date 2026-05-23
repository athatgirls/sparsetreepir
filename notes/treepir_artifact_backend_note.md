# TreePIR Artifact Backend Notes

This note records which parts of the public TreePIR artifact were executed locally and how they relate to SparseTreePIR.

## Environment

- Host: Windows workspace with WSL Ubuntu 24.04.
- TreePIR artifact working copy: `C:\Users\15313\Desktop\treepir_ascii`.
- Project output directory: workspace `examples/`.
- Microsoft SEAL was installed through vcpkg in WSL for PBC/VBPIR builds.

## Components executed

### TreePIR indexing

The Java indexing artifact runs successfully for perfect-tree heights 10, 16, 20, and 24. The outputs are stored under:

- `examples/treepir_indexing_results/treepir_indexing_summary.csv`
- `examples/treepir_indexing_results/color_indices_*.txt`

Observed indexing times are sub-millisecond in this local run. This supports the paper's interpretation that TreePIR's perfect-tree indexing is not the bottleneck; the mismatch for SMTs is the PIR-facing object and layout, not TreePIR's original indexing routine.

### PBC artifact

The PBC artifact was built after adapting the local working copy to SEAL's vcpkg package name and C++17. It ran successfully for heights 10, 16, and 20. The summary is stored in:

- `examples/treepir_pbc_artifact_results.csv`

Key observation: the public map is about 4.4 times the raw database size in these runs. This is consistent with TreePIR's motivation for avoiding generic PBC-style indexing state.

### Spiral artifact

The TreePIR Spiral directory was built and smoke-tested on the official color-subdatabase JSON files. The summary is stored in:

- `examples/spiral_treepir_smoke_summary.csv`
- `examples/spiral_treepir_smoke_results.csv`

The current Spiral run is a TreePIR-format smoke test, not yet a SparseTreePIR backend experiment. To use it as a SparseTreePIR backend, we still need an exporter that writes active color stores in Spiral's expected JSON format and produces proof-consistent query indices.

### VBPIR artifact

Both `VBPIR_PBC` and `VBPIR_TreePIR` were built after the same SEAL/C++17 compatibility patches in the ASCII working copy.

The code contains hard-coded paths under `/home/quang/...`; WSL symlinks were used to reproduce that directory structure without modifying the source logic. `VBPIR_TreePIR` also required regenerating `subIndices/color_indices_10_2.txt` for the `list_TXs_10_2.txt` bundled with the VBPIR directory, because the indexing program reads `list_TXs` from its current working directory.

The full logs are stored in:

- `examples/treepir_vbpir_pbc_smoke.txt`
- `examples/treepir_vbpir_treepir_smoke.txt`

The compact summary is stored in:

- `examples/treepir_vbpir_artifact_summary.csv`

In the height-10 smoke test, VBPIR_PBC uses 15 buckets with max bucket size 446, while VBPIR_TreePIR uses 10 color buckets with max bucket size 205. Both runs retrieve 10 examples successfully. The query and answer byte counts are identical in this artifact configuration, but the resource shape clearly differs.

### YPIR

YPIR was downloaded and checked under WSL, but the local CPU lacks AVX-512. The artifact also failed to compile cleanly on the local toolchain due AVX-512 intrinsic casts. We should treat YPIR as requiring a Linux server with AVX-512 support rather than a local WSL result.

### SealPIRplus / orchestrator

The SealPIRplus route is organized as a gRPC client/server experiment driven by `SealPIR-Orchestrator/orchestrator.py`. It is not a single local smoke-test binary: it expects generated TreePIR/PBC databases, server lists, `pirmessage_server`, `pirmessage_client`, and Protobuf/gRPC runtime support.

A minimal CMake configure attempt on the local WSL environment reached the Protobuf/gRPC dependency boundary. After switching the ASCII working copy from `find_package(SEAL 4.0 REQUIRED)` to `find_package(SEAL CONFIG REQUIRED)`, CMake stopped at:

```text
Could not find a package configuration file provided by "Protobuf"
```

Installing gRPC/Protobuf through vcpkg started a large source build and did not complete within a 20-minute local timeout. We stopped the background build to avoid leaving a heavy compile process running. This should be treated as an environment/setup limitation, not as a negative backend result.

For the paper, the safer interpretation is:

1. TreePIR's SealPIRplus route exists as a service-level artifact, but it requires a heavier gRPC/Protobuf setup than the local PBC/VBPIR/Spiral smoke tests.
2. We should not claim local SealPIRplus timing unless we run it on a prepared Linux machine or finish the dependency build.
3. The already completed SimplePIR/PIANO/Spiral/VBPIR checks are enough to support backend compatibility in the current draft; SealPIRplus can be listed as future reproducibility work unless we allocate a dedicated setup pass.

## How this should be used in the paper

These results should not be described as final SparseTreePIR backend results. They are artifact-level evidence for the prior routes used by TreePIR:

1. PBC-style generic batch routing has large map/indexing state.
2. TreePIR-style coloring changes the bucket profile seen by a backend.
3. TreePIR's own implementations are specialized to perfect-tree IDs, color-subdatabase JSON files, and fixed tree heights.

For SparseTreePIR, the correct next step is an exporter from active interval color stores to the backend-specific database format. We already have this pattern for SimplePIR/PIANO; Spiral and VBPIR would require format-specific exporters and query-index mapping.
