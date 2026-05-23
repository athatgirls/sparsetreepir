# SparseTreePIR Project Structure

Current main paper entry points:

- English conference version: `manuscripts/sparsetreepir_conference.tex`
- English body file: `manuscripts/sparsetreepir_body_full_en.tex`
- Compiled PDF: `build/sparsetreepir_conference.pdf`

Folder overview:

- `manuscripts/`: paper source files and compiled PDFs
- `figures/`: figure source `.tex` files and figure PDFs used by the paper; current paper figures use the `sparsetreepir_*` prefix
- `scripts/`: experiments, data processing, and example-generation scripts
- `notes/`: research notes, drafts, and experiment writeups
- `examples/`: generated sparse-Merkle-tree examples and exported example figures
- `build/`: LaTeX auxiliary files such as `.aux`, `.log`, `.out`, and `.synctex.gz`
- `previews/`: screenshot and preview images used during layout checking
- `templates/`: downloaded LaTeX template folders kept for reference
- `archive/legacy_virtual_swapped/`: old drafts, dynamic-side notes, and legacy artifacts kept for reference but no longer part of the active paper

Recommended starting point:

1. Edit the main text in `manuscripts/sparsetreepir_body_full_en.tex`
2. Compile from `manuscripts/sparsetreepir_conference.tex`
3. Update current figures in `figures/sparsetreepir_*.tex` or regenerate them through the corresponding `scripts/plot_sparsetreepir_*.py` scripts

Useful current scripts:

- `scripts/plot_sparsetreepir_concept_figures.py`
- `scripts/plot_sparsetreepir_resource_comparison.py`
- `scripts/plot_sparsetreepir_simplepir_timing.py`
- `scripts/plot_sparsetreepir_additional_figures.py`
- `scripts/build_sparsetreepir_story_deck.py`
- `scripts/build_sparsetreepir_story_deck_stable.py`
- `scripts/build_article_docx.py`
- `scripts/build_pdf_pages_docx.py`

Current paper figure count:

- TreePIR reference PDF: 17 figures and 10 tables.
- SparseTreePIR current PDF: 10 figures, 10 tables, and 4 algorithms.
- Main mechanism/example figure sources:
  - `figures/sparsetreepir_workflow_figure.tex`
  - `figures/sparsetreepir_running_example_figure.tex`
  - `figures/sparsetreepir_active_balance_before_after_figure.tex`
- Newly added resource-story figures:
  - `figures/sparsetreepir_distribution_reduction_figure.pdf`
  - `figures/sparsetreepir_height_vs_active_width_figure.pdf`
  - `figures/sparsetreepir_metadata_overhead_figure.pdf`
