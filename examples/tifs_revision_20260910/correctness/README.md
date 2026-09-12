# TIFS revision correctness checks

Run: `python scripts/test_tifs_revision_smt.py` from the workspace root.

The JSON report and CSV contain completed checks. Small heights exhaust all occupancy masks and use an independent dense reference; h=128/256 never materialize a full coordinate tree.

This directory tests real hashes, metadata lookup, digest-record serialization and root reconstruction. The records are read directly during verification; actual PIR runs belong in a separate backend report. Client context files are private test inputs and contain queried target identities and real/dummy roles.
