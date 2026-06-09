# Anonymization Notes

This repository is prepared for anonymous review.

## Included

- Source code needed to construct SparseTreePIR layouts.
- Backend adapters for SimplePIR and PIANO.
- Public workload CSVs and test-vector-derived workloads.
- Checked-in result summaries used for paper tables.
- Generated paper-facing figures.
- English reproduction instructions.

## Excluded

- Author names, affiliations, acknowledgments, and manuscript drafts.
- Local machine paths, raw environment dumps, cache directories, and toolchain
  checkouts.
- Presentation decks, Word/PDF page-check files, and development notes.
- Private datasets or credentials.

## External dependencies

The full backend run fetches public third-party repositories for SimplePIR and
PIANO through `scripts/setup_linux_experiment_deps.sh`.  Those dependencies are
not vendored in this anonymized artifact.

## Suggested Anonymous GitHub settings

When creating the anonymous mirror:

- Repository name: `SparseTreePIR`
- Branch: the artifact branch pushed from this directory.
- Visibility: public anonymous mirror.
- Download mode: enabled, if offered.
- Conference label: use the target conference if it appears in the dropdown;
  otherwise leave it blank or use the generic option.

The reviewer-facing link should point to the Anonymous GitHub URL, not to the
source GitHub repository.
