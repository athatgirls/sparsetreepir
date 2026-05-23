# Spiral / YPIR backend attempt note

Date: 2026-05-21

## Goal

Extend the backend-shape evaluation beyond SimplePIR, PIANO, LWE-style prototype, and two-server XOR-PIR by trying Spiral and YPIR artifacts.

## TreePIR artifact availability

The local TreePIR artifact at:

```text
external/TreePIR-main
```

does include backend-related code:

- `PBC`
- `SealPIRplus`
- `Spiral`
- `VBPIR_PBC`
- `VBPIR_TreePIR`
- `TreePIR-Indexing`

This means we can reuse TreePIR's backend-adapter logic as a reference for perfect-tree TreePIR and PBC comparisons. However, these adapters target TreePIR's original perfect-tree/PBC database formats. They are not drop-in SparseTreePIR backends; our SMT color-store vectors must still be exported into each backend's expected database shape.

## Spiral status

TreePIR includes a Spiral integration in:

```text
external/TreePIR-main/Spiral
```

The README / Dockerfile path uses:

```text
vcpkg install hexl nlohmann-json boost-multi-index simdjson
```

The CMake files require:

- `HEXL`
- `nlohmann_json`
- `simdjson`
- `Boost`

and are hard-wired around `/home/ubuntu/vcpkg`.

WSL setup progress:

- Installed `cmake`, `clang`, `git-lfs`, `python3-pip`, build tools.
- Confirmed the TreePIR Spiral source is present.
- Confirmed the CMake project exposes `NOAVX512`, which is needed on the current machine because WSL does not show `avx512f`.
- Installed vcpkg through a zip-based fallback after the first Git clone attempt timed out.
- Installed Spiral dependencies through vcpkg: `hexl`, `nlohmann-json`, `boost-multi-index`, and `simdjson`.
- Patched TreePIR's Spiral `CMakeLists.txt` to fall back from `clang++-12` to the available `clang++`.
- Configured the Spiral CMake project successfully with `NOAVX512=ON`.
- Built the `Seperated` executable successfully.

Smoke-test status:

- TreePIR's Spiral code hard-codes `/tmp/Spiral` as its runtime directory. Directly symlinking to the Windows project path failed because the project path contains Chinese characters and the directory lookup was unreliable inside the artifact.
- Copying the Spiral artifact to an ASCII-only WSL path and then to `/tmp/Spiral` fixes the runtime path issue.
- A single smoke run on TreePIR's bundled `colorA_10_2.json` completed successfully:

```text
Database filename: colorA_10_2.json with 204 hashes.
Number of folds: 6.
Further dimensions: 4.
Number of queries: 1.
Evaluation on core ... is complete.
```

- The check line reports an invalid hash position because we used the artifact's default query index for a backend smoke test rather than a TreePIR proof-consistent query. This does not invalidate the backend execution test; it means we should not present it as an end-to-end proof correctness result.
- The generated Spiral metrics for this smoke run include:

```text
Query bytes:    28672
Response bytes: 11264
Total bytes:    39936
```

Batch smoke-test status:

- Ran the same Spiral executable on TreePIR's bundled color stores `colorA_10_2.json` through `colorJ_10_2.json`.
- Result CSV:

```text
examples/spiral_treepir_smoke_results.csv
examples/spiral_treepir_smoke_summary.csv
```

- Average across the ten TreePIR color-store smoke runs:

```text
average hashes per store: 204.6
average query bytes:      28672
average response bytes:   11264
average total bytes:      39936
average query generation: 4556.1 us
average answer time:      34613.5 us
average extraction time:  829.7 us
```

Custom-size smoke-test status:

- The Spiral JSON database format is simple enough to export: a JSON array containing one object whose keys are record identifiers and whose values are 32-byte hex digests, e.g.:

```json
[{"0":"...32-byte hex digest...","1":"..."}]
```

- Generated synthetic JSON databases with 16, 64, 128, 256, 512, 1024, and 2048 digest records and ran the same Spiral executable on them.
- Result CSV:

```text
examples/spiral_custom_size_smoke_results.csv
```

- All custom-size smoke runs exited successfully under the fixed TreePIR Spiral parameter set. Query and response byte counts stayed constant at 28672 and 11264 bytes respectively under this fixed parameter set. Timing is noisy and should not be used as a final performance claim without tuning Spiral parameters to the database sizes.

Current blocker for paper-level SparseTreePIR comparison:

- The Spiral artifact is now buildable and runnable, but it expects TreePIR's own JSON database format and query/check workflow.
- A fair SparseTreePIR-vs-PBC-vs-TreePIR Spiral experiment requires exporting our active color stores into this JSON/database format and generating proof-consistent query indices.
- Therefore, we can currently cite this as a successful TreePIR-Spiral artifact smoke test, not yet as a SparseTreePIR Spiral benchmark.

## YPIR status

Downloaded the official YPIR artifact into:

```text
.tools/ypir
```

Artifact: `https://github.com/menonsamir/ypir`

The README says YPIR requires:

- Ubuntu
- Rust via rustup
- AVX-512 support, specifically visible as `avx512f` in `lscpu`

Current WSL CPU flags include AVX2 but not AVX-512:

```text
Flags: ... avx avx2 ... (no avx512f)
```

Rust status:

- Installed rustup.
- Installed the requested `nightly-2024-02-07` toolchain and also `nightly-2024-03-01`.
- `cargo +nightly-2024-03-01 --version` and `rustc +nightly-2024-03-01 --version` work.

Current blocker:

- The artifact-pinned `nightly-2024-02-07` toolchain reports:

```text
error: the 'cargo' binary, normally provided by the 'cargo' component,
is not applicable to the 'nightly-2024-02-07-x86_64-unknown-linux-gnu' toolchain
```

- Building with stable cargo fails because `spiral-rs` uses unstable AVX-512 intrinsics:

```text
#![feature(stdarch_x86_avx512)]
error[E0554]: `#![feature]` may not be used on the stable release channel
```

- Building with `cargo +nightly-2024-03-01 check --release` gets past the `spiral-rs` stable-channel issue, but then fails in YPIR source compatibility:

```text
error[E0605]: non-primitive cast: `*const u8` as `std::arch::x86_64::__m512i`
error[E0605]: non-primitive cast: `*const u16` as `std::arch::x86_64::__m512i`
error[E0605]: non-primitive cast: `*const u32` as `std::arch::x86_64::__m512i`
```

- Even if the source/toolchain issue is repaired, the current hardware cannot run YPIR reliably because AVX-512 is missing. The WSL CPU flags show AVX2 but no `avx512f`.

## Paper implication

Do not claim executable YPIR results from this machine.

Do not claim SparseTreePIR Spiral backend results yet. We only have a TreePIR Spiral artifact smoke test on the artifact's bundled database format.

We can honestly say:

- PIANO local runner is executable in WSL.
- SimplePIR full API bridge is executable.
- LWE-style and two-server XOR models provide additional backend-shape evidence.
- TreePIR's Spiral artifact is available, builds under WSL with `NOAVX512=ON`, and runs smoke tests on TreePIR's bundled JSON color stores.
- YPIR artifact is downloaded, but the current CPU/toolchain environment is not suitable for a reliable run.

## Next practical paths

1. Export SparseTreePIR color stores into TreePIR Spiral's expected JSON database format.
2. Generate proof-consistent query indices for the exported Spiral databases, so the artifact's correctness check becomes meaningful.
3. Run YPIR on a machine with AVX-512, such as the AWS `r6i.16xlarge` instance recommended by the YPIR README.
4. If using this local WSL environment, keep YPIR as an attempted-but-hardware-blocked integration rather than a result table entry.
