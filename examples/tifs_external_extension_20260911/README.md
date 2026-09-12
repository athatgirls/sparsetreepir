# VBPIR proof-retrieval evidence

This directory contains the frozen VBPIR comparison used by the current paper:
the inputs, source-pinned native adapter, recorded commands, recovered records,
and timing observations. The full archive has 48 complete independent processes,
480 measured proofs, and 576 proofs including warmups. The current paper selects
the uniform-key cohorts and complete-tree controls; the prefix and clustered
cohorts remain available for auditing the original schedule.

One batch retrieves the non-default sibling digests required by one Merkle proof.
AB, PBC, and the complete-tree CSA layout use a common VBPIR adapter. The recorded
timer measures an in-process serialized proof pipeline, including proof recovery
and authentication, without network transport. It is not the running time of the
complete original TreePIR service or its Java indexing algorithm.

## Verify the frozen observations

From the repository root, with Python 3.12 or newer:

```sh
python3 reproduce/verify.py --output .reproduce/frozen-check
```

The output directory must not already exist. The verifier copies the evidence,
restores the deduplicated per-process inputs, checks their original pre-execution
SHA-256 digests, and audits the recovered records, authentication roots, negative
controls, paired schedules, parameters, and communication accounting. It does not
generate new timing measurements or modify the checked-in observations.

## Build and run new measurements

Use the portable build and execution commands in
[`docs/NATIVE_REPRODUCTION.md`](../../docs/NATIVE_REPRODUCTION.md). The builder
uses the included pinned source and obtains the specified SEAL dependency.
Compiler outputs and historical executable binaries are not part of this release.
New runs use separate output directories.

The three cryptographic C++ implementation files match the pinned upstream
TreePIR VBPIR_PBC source. Adapter changes and measurement definitions are recorded
in [`native_adapter/README.md`](native_adapter/README.md) and its source manifest.
The original source-copy preparation script is provenance tooling; it is not
needed to build the included source snapshot.

The repository's root provenance manifest describes this publication snapshot.
Original archive manifests are retained as historical provenance and do not serve
as the file list of the reorganized release. See [`docs/RESULTS.md`](../../docs/RESULTS.md)
for the correspondence between current paper results and their evidence.
