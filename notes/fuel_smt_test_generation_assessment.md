# FuelLabs/smt-test-generation Assessment

Repository:

```text
https://github.com/FuelLabs/smt-test-generation
```

Checked on 2026-05-16.

## What the repository is

The repository description is:

> Generate specification compliant test data used for data-driven sparse Merkle tree testing.

It is a small Go project. Its core generator (`smttestgen.go`) creates a list of SMT tests, including:

- empty root;
- one, two, three, five, ten, and one hundred updates;
- repeated updates;
- overwrite key;
- clustered/union-like update patterns;
- sparse union updates;
- empty-data update;
- delete;
- delete non-existent key;
- interleaved update/delete.

The wrapper (`smtw/smtw.go`) uses `github.com/celestiaorg/smt` with SHA-256, records each operation, and emits an expected root. The output fixture format is roughly:

```json
{
  "name": "...",
  "expected_root": {"value": "...", "encoding": "hex"},
  "steps": [
    {
      "action": "update",
      "key": {"value": "...", "encoding": "hex"},
      "data": {"value": "DATA", "encoding": "utf-8"}
    }
  ]
}
```

Important detail: the generator hashes input keys before recording them:

```go
stepKey := framework.HexValue(digest(key))
```

Therefore, the fixture key field is already a SHA-256-style SMT key, not the raw four-byte input used in the generator.

## Can we use it?

Yes, but not as a real-world SMT dataset.

It is useful for:

1. **Conformance tests**: verify that our SMT workload parser and active-skeleton construction behave correctly on standard update/delete cases.
2. **Edge-case evaluation**: repeated updates, overwrites, deletes, empty values, clustered updates, sparse unions.
3. **Small correctness appendix**: show that SparseTreePIR can consume a specification-style SMT operation trace and derive the final live key workload.
4. **Regression tests**: ensure future code changes do not break active-node extraction on simple SMT fixtures.

It is not useful as:

1. a large-scale SMT dataset;
2. a real deployment workload;
3. a replacement for Polygon/ZKsync/Scroll state-key workloads;
4. evidence that our scheme scales to large production state trees.

## How it complements Polygon

Polygon-zkEVM-derived workload:

- real deployment context;
- real addresses;
- larger workload;
- not a full state-tree node dump.

FuelLabs/smt-test-generation:

- standard SMT operation semantics;
- expected roots;
- update/delete edge cases;
- small synthetic/conformance workload.

So the paper can use them differently:

| Source | Role in paper | Claim supported |
|---|---|---|
| Polygon zkEVM workload | Main real SMT-workload experiment | The organization works on a real SMT-using system workload |
| Fuel SMT tests | Appendix / sanity / conformance experiment | The pipeline can consume SMT update/delete traces and handle edge cases |

## Added converter

I added:

```text
scripts/convert_fuel_smt_tests_to_workload.py
```

It converts generated Fuel fixture JSON into a SparseTreePIR workload CSV:

```powershell
python scripts\convert_fuel_smt_tests_to_workload.py `
  --input external\smt-test-generation\fixtures\smt_test_spec.json `
  --output datasets\fuel_smt_test_workload.csv `
  --summary-output datasets\fuel_smt_test_workload_summary.json
```

Then run our SMT workload experiment:

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\fuel_smt_test_workload.csv `
  --column key `
  --label fuel_smt_test_vectors `
  --heights 128,256 `
  --key-mode hex-prefix `
  --output examples\fuel_smt_test_vector_results.csv
```

If we want to evaluate every intermediate snapshot, not only final live keys:

```powershell
python scripts\convert_fuel_smt_tests_to_workload.py `
  --input external\smt-test-generation\fixtures\smt_test_spec.json `
  --emit-intermediate `
  --output datasets\fuel_smt_test_workload_intermediate.csv `
  --summary-output datasets\fuel_smt_test_workload_intermediate_summary.json
```

## Local execution status

Go was installed locally as a portable workspace tool:

```text
external/go/bin/go.exe
```

Verified version:

```text
go version go1.23.4 windows/amd64
```

The FuelLabs repository was downloaded to:

```text
external/smt-test-generation-master
```

Minor local compatibility patch:

1. create missing `fixtures/` directories before writing;
2. remove a hard-coded author-local `E:\fuel\...` fixture output path.

The generator was run successfully with module caches inside the workspace:

```powershell
$root='C:\Users\15313\Desktop\论文'
$env:PATH="$root\external\go\bin;" + $env:PATH
$env:GOMODCACHE="$root\.gomodcache"
$env:GOCACHE="$root\.gocache"
$env:GOPATH="$root\.gopath"
$env:GOPROXY='https://goproxy.cn,direct'
$env:GOSUMDB='sum.golang.google.cn'
go run .
```

Generated fixtures:

```text
external/smt-test-generation-master/fixtures/smt_test_spec.json
external/smt-test-generation-master/fixtures/smt_test_spec.yaml
external/smt-test-generation-master/fixtures/json/*.json
external/smt-test-generation-master/fixtures/yaml/*.yaml
```

## SparseTreePIR test results

Final live-key workload conversion:

```powershell
python scripts\convert_fuel_smt_tests_to_workload.py `
  --input external\smt-test-generation-master\fixtures\smt_test_spec.json `
  --output datasets\fuel_smt_test_workload.csv `
  --summary-output datasets\fuel_smt_test_workload_summary.json
```

Intermediate-snapshot workload conversion:

```powershell
python scripts\convert_fuel_smt_tests_to_workload.py `
  --input external\smt-test-generation-master\fixtures\smt_test_spec.json `
  --emit-intermediate `
  --output datasets\fuel_smt_test_workload_intermediate.csv `
  --summary-output datasets\fuel_smt_test_workload_intermediate_summary.json
```

Final-live summary:

| Metric | Value |
|---|---:|
| Fuel tests | 19 |
| Workload rows | 174 |
| Unique keys | 100 |
| Max final live keys | 100 |

Intermediate summary:

| Metric | Value |
|---|---:|
| Fuel tests | 19 |
| Workload rows | 6,120 |
| Unique keys | 100 |

SparseTreePIR results:

| Workload | Height | Unique keys | Active nodes | m | Avg. active path | Dummy frac. | Ideal bucket | Profile bucket | Ratio | Gap | Valid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Fuel final live keys | 128 | 100 | 198 | 9 | 6.88 | 23.56% | 22 | 22 | 1.000 | 0 | yes |
| Fuel final live keys | 256 | 100 | 198 | 9 | 6.88 | 23.56% | 22 | 22 | 1.000 | 0 | yes |
| Fuel intermediate snapshots | 128 | 100 | 198 | 9 | 6.88 | 23.56% | 22 | 22 | 1.000 | 0 | yes |
| Fuel intermediate snapshots | 256 | 100 | 198 | 9 | 6.88 | 23.56% | 22 | 22 | 1.000 | 0 | yes |

Output files:

```text
datasets/fuel_smt_test_workload.csv
datasets/fuel_smt_test_workload_summary.json
datasets/fuel_smt_test_workload_intermediate.csv
datasets/fuel_smt_test_workload_intermediate_summary.json
examples/fuel_smt_test_vector_results.csv
examples/fuel_smt_test_vector_intermediate_results.csv
```

## Recommendation

Use this project, but do not promote it as the main real-data experiment.

Best placement:

> Appendix: SMT conformance workloads generated from FuelLabs/smt-test-generation.

Main text should continue to use Polygon zkEVM workload as the real SMT-workload evidence.
