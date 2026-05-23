# TreePIR-style Backend/Resource Advantage Overview

This note summarizes the TreePIR-style comparison figure generated from the experiments we can currently run or reuse locally.

## Generated files

- `examples/treepir_style_backend_advantage_overview.csv`
- `figures/treepir_style_backend_advantage_overview.pdf`
- `figures/treepir_style_backend_advantage_overview.png`

## What the figure shows

The figure follows TreePIR's resource-first experimental style: it does not claim that every backend has been fully reimplemented around SparseTreePIR. Instead, it separates the evidence into two layers.

### Layer 1: SparseTreePIR on real SMT workloads

Panel A uses the real SMT workload summary against `PBC-active`, averaged over six real/trace-derived SMT workloads:

- FuelLabs SMT test vectors
- Polygon zkEVM recent
- Polygon zkEVM multi-window
- Polygon zkEVM broad
- ZKsync Era sample
- ZKsync Era broad

Across four backend models/runners, SparseTreePIR reduces online communication by roughly 52--62% and query generation by roughly 44--56% relative to PBC-active.

Panel B shows the resource-shape source of the improvement:

- Storage vs PBC-active: 66.7% reduction, because PBC-active uses 3 replicated copies.
- Width vs PBC-active: 34.8% reduction, because PBC-active uses about \(1.5m\) subqueries while SparseTreePIR uses \(m\).
- Max bucket vs PBC-active: 48.6% reduction.
- Max bucket vs flat active PIR: 92.1% reduction, showing that active storage alone is not enough; color-store partitioning matters.

### Layer 2: TreePIR artifact checks

Panel C uses the TreePIR public artifact's VBPIR smoke runs:

- `VBPIR_PBC`: 15 buckets, max bucket size 446.
- `VBPIR_TreePIR`: 10 buckets, max bucket size 205.

Both retrieve 10 examples successfully. In this artifact configuration, query/answer byte counts are equal, so the panel emphasizes resource shape rather than claiming a communication win.

Panel D records the PBC artifact's map size overhead. Across h=10/16/20 runs, the map is about 4.41x the raw database size.

## Interpretation for the paper

The clean claim is:

> TreePIR's experimental style teaches us to evaluate the resource shape exposed to a PIR backend. On real SMT workloads, SparseTreePIR improves that shape over PBC-active by reducing replicated storage, reducing the batch width, and flattening the largest searched color store. TreePIR's own artifact reproduces the same kind of resource-shape lesson: coloring changes bucket profiles even when a particular backend configuration gives equal byte counts.

## Important caveat

The TreePIR VBPIR and Spiral runs are currently artifact smoke tests using TreePIR-format JSON/color-index files. They should not be described as final SparseTreePIR backend integrations until we implement an exporter from SparseTreePIR active color stores to each backend's database and query-index format.
