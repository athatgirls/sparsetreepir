# Real executable PIR backend comparison

This note summarizes only concrete backend runs: SimplePIR full API and the PIANO Go runner. It intentionally excludes XOR, LWE cost-model, and TreePIR-format smoke-test data.

| Backend | Workloads | Online KB reduction | Query-generation reduction | Setup reduction | Width reduction |
|---|---:|---:|---:|---:|---:|
| PIANO-local-runner | 6 | 51.5% | 34.9% | 66.3% | 34.8% |
| SimplePIR-full-API | 6 | 52.4% | 39.8% | 56.9% | 34.8% |

Interpretation: SparseTreePIR does not change the PIR primitive. It changes the backend-facing database shape: fewer batch slots than PBC-SMT and smaller active color stores. The plotted numbers are therefore an executable sanity check that this resource shape translates to real PIR API/runner gains on the current workloads.

Figure: `figures/real_pir_backend_comparison.png`
Summary CSV: `examples/real_pir_backend_comparison_summary.csv`
