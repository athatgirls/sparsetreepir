# Current manuscript: result-to-evidence map

The mapping below follows release `2026-09-12-current-paper`. Roman table numbers refer to the main text; S-prefixed numbers refer to the supplement. References printed in figures/tables follow the manuscript bibliography, provided in `paper-results/references.tex`.

| Manuscript item | Evidence / generator |
|---|---|
| Table I, notation; Figures 1-2, protocol/interval illustrations | Explanatory material, not measurements; vector figures are included in `paper-results/figures/`. |
| Table II, worked batch example | `paper-results/reproduction_scripts/check_worked_batch_example.py`; independently reconstructs all seven targets. |
| Table III and Figure 3, AB versus PBC on two backends | Native `examples/*extension_20260911/analysis/results.json`; `paper-results/reproduction_scripts/generate_external_core.py`. |
| Table IV, First-fit versus AB | Same native SimplePIR evidence and generator; identical records and minimum batch width. |
| Table V, six workload layouts | `datasets/`, `examples/tifs_revision_20260910/verified_backend/`, selected balance evidence; `paper-results/generated/main_layout_table.tex`. |
| Table S1 and Figure S1, exact/construction gaps | `examples/tifs_remaining_gap_20260910/`, `tifs_sufficiency_20260910/construction/`, `tifs_layout_transfer_20260910/structural/`. |
| Table S2, native initialization/client state | Native summaries; `paper-results/reproduction_scripts/build_external_supplement_table.py`. |
| Table S3, comparator provenance | Current provenance table is included in `paper-results/generated/compact_evidence.tex`; source pins remain in each adapter. |
| Figure S2, delete-versus-recolor example | Structural explanatory figure, not benchmark data. |
| Table S4, earlier VBPIR components | `examples/tifs_contribution_gate_20260910/external/`; distinct from the native full proof-processing experiments. |
| Tables S5-S7, workload sources, bootstrap costs, evidence map | `datasets/`, `examples/tifs_revision_20260910/verified_backend/`, captured manifests. |
| Table S8, construction scale | `examples/tifs_revision_20260910/balance_repeats/` and required `balance/` evidence; censored Hungarian runs remain marked as censored. |
| Table S9 and Figure S3, Fuel TCP | `examples/tifs_layout_transfer_20260910/system/`; preserve the capacity-22 witness separately from AB's capacity 23. |
| Table S10, certificate mirror TCP | `examples/tifs_revision_20260910/ct_application/runs_verified_evidence/` and `source/`; the fixed 512-entry mirror's original responses are retained. |
| Capacity and construction verification | `examples/tifs_contribution_gate_20260910/theory/`, `tifs_remaining_gap_20260910/`, `tifs_sufficiency_20260910/`, `tifs_layout_transfer_20260910/theory/`. |

## Interpretation and comparator identity

PBC is a general batch-code layout. The native adapters use the three-choice placement distributed with the VBPIR implementation in TreePIR's repository. The SimplePIR adapter implements that routing policy in Go; it does not claim byte-for-byte reproduction of C++ unordered-map eviction trajectories. Official TreePIR CSA is a separate complete-tree layout control. Nonempty-depth is an internal baseline, not TreePIR. AB and First-fit are compared to isolate the balancing effect.

The native SimplePIR and VBPIR results use 32-byte digest records. Earlier component and TCP experiments use their captured eight-chunk SimplePIR configuration. Those measurements are not pooled. Native cryptosystems are compared within their respective parameterizations; no equal-security cross-backend speed ranking is asserted.

`paper-results/verification/PRIMARY_EVIDENCE_SELECTION.json` and `paper-results/reproduction_scripts/external_core_source_selection.json` identify the reported uniform and complete-tree cohorts. The full frozen archives remain broader than that selection. Full-cache, initialization, partial runs, and censored measurements are retained with their recorded status.

## Historical evidence and portable execution

Native `runs/*/*/repeat*/input.json` copies were deduplicated in the original experiment archives. The restore scripts recreate them byte-for-byte and check the recorded hashes before analysis. Canonical inputs, target schedules, candidate lists, and result records are preserved.

Publication copies may normalize machine-specific path metadata. `provenance/PUBLICATION_TRANSFORMATIONS.json` declares such changes with before/after hashes; the original packaging manifests are historical records, while `RELEASE_MANIFEST.json` describes this release. Historical measured executables and build caches are not distributed. Their recorded hashes remain provenance, not claims that rebuilding produces identical binaries.

Legacy captured drivers under `scripts/` and source snapshots retain their original interfaces and may expect the original experiment directory layout. The supported portable entry points are the root README commands; full legacy reruns require matching the archived parameters and dependencies. The current release does not claim to have rerun every supplemental benchmark on a fresh machine.
