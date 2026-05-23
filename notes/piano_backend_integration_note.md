# PIANO backend integration note

Date: 2026-05-21

## Goal

Try to connect a modern PIR backend beyond SimplePIR. PIANO is the first target because its public artifact is Go-based and therefore closer to the current SimplePIR bridge workflow than Spiral or YPIR.

## Artifact

Repository downloaded into:

```text
.tools/piano-pir-new
```

The artifact README identifies it as the prototype for:

```text
Piano: Extremely Simple, Single-server PIR with Sublinear Server Computation (IEEE S&P 2024)
```

## What worked

The official mini tutorial runs successfully after setting a reachable Go proxy:

```powershell
$env:GOPROXY = 'https://goproxy.cn,direct'
go run tutorial_new\tutorial_new.go
```

Observed output:

```text
DBSize: 10000, ChunkSize: 100, ChunkNum: 100
Q: 921, M1: 3684, M2: 36
PIR finished successfully
```

This confirms that the artifact and local Go toolchain can execute the official PIANO path.

## Earlier Windows blocker

I wrote a local runner based on the official `tutorial_new` algorithm:

```text
.tools/piano-pir-new/eval/smt_layout_benchmark.go
```

It accepts a vector of subdatabase sizes and measures the same PIANO-style setup/query/server-parity shape for the PBC-SMT and SparseTreePIR bucket vectors.

However, executing the newly generated Go binary is blocked by Windows Application Control:

```text
fork/exec ...\smt_layout_benchmark.exe: An Application Control policy has blocked this file.
```

The same block happens even when:

- building with `go build -o` instead of `go run`;
- using a `subst` drive to avoid the Chinese workspace path;
- renaming the file to `tutorial_new.go`.

The original official `tutorial_new/tutorial_new.go` still runs, so this is not a PIANO algorithm failure. It is a local execution-policy issue for new generated binaries.

This blocker is specific to the Windows application-control environment. The WSL run below supersedes the original "no PIANO results yet" conclusion.

## Paper implication

After the WSL run below, the current paper can honestly say:

- SimplePIR full API bridge is executable.
- PIANO local runner provides executable backend-shape evidence from the public artifact path.
- LWE-style prototype and 2-server XOR model provide additional backend-shape evidence.
- Full optimized production/research integrations such as tuned PIANO digest packing, YPIR, and Spiral remain future work.

## Next practical path

To get true PIANO results, use one of:

1. Run the PIANO bridge in WSL/Linux, where the Go binary execution policy will not block custom compiled executables.
2. Run it on a clean server/VM.
3. Modify and execute inside an environment already allowed by Windows Application Control.

Once runnable, feed each layout's bucket-size vector into the local PIANO runner:

- PBC-SMT: `ceil(1.5m)` buckets, `3N` replicated active records.
- SparseTreePIR: `m` ActiveBalance color stores.

## WSL update: executable backend-shape run

We installed Ubuntu 24.04 under WSL and reran the artifact there. Both the official tutorial and the local SMT layout runner execute successfully in WSL.

Official tutorial smoke test:

```text
cd /mnt/c/Users/15313/Desktop/论文/.tools/piano-pir-new
GOPROXY=https://goproxy.cn,direct go run tutorial_new/tutorial_new.go
```

The run completed with `PIR finished successfully`.

Local SMT layout runner smoke test:

```text
go run eval/smt_layout_benchmark.go -sizes 70,70,70 -queries 3 -seed 7
```

The runner produced setup/query/online/offline CSV metrics. We then ran the real-workload layouts through:

```text
python scripts/run_piano_wsl_backend_from_layouts.py --queries 5 --timeout 300
```

Generated files:

- `examples/piano_wsl_backend_results.csv`
- `examples/piano_wsl_backend_summary.csv`

Summary over the six height-128 real SMT workloads:

- Average online-communication reduction of SparseTreePIR vs PBC-SMT: 51.5%.
- Average client-query-time reduction: 46.1%.
- Per-workload online reductions: Fuel 47.5%, Polygon broad 51.7%, Polygon multi-window 51.5%, Polygon recent 53.8%, ZKsync broad 52.4%, ZKsync sample 52.1%.

Scope note: this is a local runner based on the public PIANO artifact's algorithm path and native entry format. It is useful backend-shape evidence, but it is not an optimized production PIANO service and does not implement tuned 32-byte Merkle-digest packing.
