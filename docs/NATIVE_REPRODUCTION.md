# Native reproduction and frozen evidence verification

Run the commands below from the artifact root. Each command requires a **new
output directory** and refuses to reuse an existing one. No entry point writes
new measurements or restored inputs into the checked-in `examples/` evidence.
The Python entry points use only the standard library.

## 1. Verify the recorded evidence without executing a backend

Use Python 3.12 or newer, without `-O`:

```sh
python3 reproduce/verify.py --output .reproduce/frozen-check
```

This copies the frozen input snapshots and observations into the output tree,
restores the omitted per-process `input.json` files, and invokes the original
independent Python auditors with explicit input and output paths. Every restored
input must reproduce its pre-execution SHA-256. The auditors check result hashes,
paired targets, actual recovered records, original proof levels, authentication
roots, three negative controls, parameter/accounting invariants and process means.
Allow several GB of free disk space for the expanded per-process inputs.

The output is `.reproduce/frozen-check/verification_summary.json`, with full
derived CSV/JSON tables under `analysis/{vbpir,simplepir}/`. The expected broader
frozen archive outcomes are:

| Backend | Complete processes | Audited failed processes | Verified measured proofs | Including warmups |
| --- | ---: | ---: | ---: | ---: |
| VBPIR | 48 | 0 | 480 | 576 |
| SimplePIR | 83 | 1 | 837 | 1005 |

The SimplePIR status remains `audited_with_observed_failures`: the recorded PBC
failure is preserved and its successful prefix is audited. It is excluded from
complete-process performance aggregates. Successful evidence verification does
not turn that experiment into an entirely successful run. The verifier compares
the regenerated audit outcomes with the checked-in audit outcomes and exits
nonzero on a mismatch or failed audit.

The current paper selects **72 complete processes, 720 measured proofs and 144
warmups**: all four SimplePIR layouts on the three uniform cohorts (36 processes),
AB/PBC on the three VBPIR uniform cohorts (18), and AB/PBC/CSA on VBPIR complete
trees of heights 10 and 14 (18). The prefix, clustered, and SimplePIR complete-tree
observations remain separately available in the archive. Verification checks the
whole archive so this selection can be traced to its source observations.

This operation does not rerun lattice operations or timing measurements. Raw
matrix/ciphertext wires are not retained; the auditor verifies the recorded
recovered bytes and accounting against the source-reviewed adapter contract.

## 2. Build fresh native executables on Linux

The native runners use Linux process limits, `/proc`, and sequential processes.
Ubuntu 24.04 is a suitable baseline. Required tools are Python 3.12+, Bash, Git,
CMake **3.22+**, a C/C++17 compiler, Go **1.18+** with CGO enabled, and the OpenSSL,
zlib and Zstandard development libraries. For example:

```sh
sudo apt-get update
sudo apt-get install -y python3 git cmake build-essential golang-go libssl-dev zlib1g-dev libzstd-dev
python3 reproduce/build_native.py --output .reproduce/build --jobs 2
```

The builder checks the included upstream-source hashes, builds SimplePIR and
runs its adapter's Go tests, then fetches and builds the exact official SEAL
commit below. SEAL is installed under the new build directory; no system-wide
SEAL installation is required. Network access is needed for that fetch. The
included SimplePIR module has no external Go module dependencies.

| Component | Official source | Pin |
| --- | --- | --- |
| SimplePIR | [ahenzinger/simplepir](https://github.com/ahenzinger/simplepir/tree/e9020b03bf2872c75b8954e749e32408b5db87ed) | `e9020b03bf2872c75b8954e749e32408b5db87ed` |
| VBPIR core used by the adapter | [PIR-PIXR/TreePIR](https://github.com/PIR-PIXR/TreePIR/tree/930063c5aefc441244abb4890fdf35383f3aa956/VBPIR_PBC) | `930063c5aefc441244abb4890fdf35383f3aa956` |
| Microsoft SEAL | [SEAL 4.3.2](https://github.com/microsoft/SEAL/releases/tag/v4.3.2) | `e3476fad1d5bb5e5222c51a551b5a4d7e2cb4f91` |

The adapter sources and their documented observations/wrappers are included.
The three VBPIR cryptographic `.cpp` files are unchanged upstream copies; the
headers include the documented observational getters and standard-header fix.
SimplePIR uses the official cryptographic operations with the documented 256-bit
vertical-record input/recovery wrapper. See each adapter's `source_manifest.json`
and `README.md` for the precise boundary.
The original SimplePIR manifest also lists an empty `pir/simple-cpu.out`
profiling output excluded by the original archive packager. The builder records
that one non-source omission explicitly; it does not relax checks on source files.

The SEAL build uses Release mode, C++17, system zlib/Zstandard, no Microsoft GSL,
and no Intel HEXL; ciphertext serialization explicitly uses no compression.
Dependencies and compiler versions can affect performance. The captured benchmark
environment records remain the authority for the original timing observations.

If SEAL 4.3.2 is already installed, use its prefix. Its exact version and CMake
dependency targets are checked; this does not authenticate the origin of an
existing local installation:

```sh
python3 reproduce/build_native.py --output .reproduce/build-local --seal-prefix /usr/local
```

Both build paths save binary hashes, source pins and commands in
`build_manifest.json`. `--backend simplepir` or `--backend vbpir` builds just one
backend. Builds use separate output/cache directories and keep the packaged
source copies intact. An interrupted build can be retained for diagnosis; choose
a new output directory to try again.

## 3. Bounded native smoke and independent audit

```sh
python3 reproduce/run_native.py --build .reproduce/build --output .reproduce/smoke --mode smoke
```

The default smoke uses `uniform_n1000`, one process per method, one warmup and
two measured queries per process: two VBPIR methods and four SimplePIR methods.
It retains each runner's sampling behavior; use the full seven-case protocol
below when requiring the original cross-backend target pairing.
It sets the original one-thread policies and applies a 600-second timeout and
10-GiB address-space limit to each process. It builds no new snapshots and writes
each new command, selected target, input, result, stderr, status and timing to the
new output tree. The independent auditors then verify those new outputs.

Inspect `rerun_summary.json` and each backend's
`analysis/INDEPENDENT_VERIFICATION.json`. Smoke observations are explicitly
excluded from performance evidence. An audited observed backend failure remains
visible as a failure in the retained completion record; it is never retried with
a replacement target. Incomplete or invalid outputs cause a nonzero exit.

For a smaller SimplePIR-only check:

```sh
python3 reproduce/run_native.py --build .reproduce/build --output .reproduce/smoke-ab --backend simplepir --mode smoke --methods ab
```

Use `--timeout SECONDS` to bound each process more tightly. A timeout may prevent
a complete independent audit and is retained as an unsuccessful observation.

## 4. Full original protocol, including every current main cohort

```sh
python3 reproduce/run_native.py --build .reproduce/build --output .reproduce/full --mode full
```

This retains the original seven-case order and scheduling policy: three fresh
processes per method/case, two warmups and ten measured queries per process. It
reruns all 48 VBPIR and 84 SimplePIR planned processes, including the 72 selected
for the current paper. SimplePIR consumes the frozen VBPIR target schedule; the
full VBPIR runner reproduces its original deterministic sampling schedule from
the same seven inputs and seed. The full run may be substantially longer and use
more memory than the smoke; it has not been silently invoked by the smoke command.

`--backend`, `--cases` and SimplePIR `--methods` can restrict a new experiment.
For example, the current main SimplePIR cohorts alone are:

```sh
python3 reproduce/run_native.py --build .reproduce/build --output .reproduce/simplepir-main --backend simplepir --mode full --cases uniform_n1000 uniform_n10000 uniform_n100000
```

For VBPIR, changing the case list changes the deterministic generator's random
draw sequence and therefore may select different targets from the same frozen
pool. Use the full seven-case command when requiring the original VBPIR target
pairing. Repetition/query counts are the two supported original protocols;
arbitrary counts are not offered because the SimplePIR auditor explicitly checks
the fixed full/smoke designs.

All layouts retain the frozen parameter policy: native 32-byte records; VBPIR
uses the supplied BFV dimensions/moduli and SEAL `tc128` validation; SimplePIR
uses `PickParams(U,256,1024,32)` with the original parameter-table restrictions,
expanded public A and one shared rectangular dimension choice per layout.
Cryptographic randomness remains fresh. New binary hashes, process scheduling,
machine load and elapsed times need not equal the captured observations. The
results describe serialized processing within one process, with no network
timing or isolated client-memory claim. A fresh rerun does not automatically
replace the paper's frozen tables or extend its empirical claims.
