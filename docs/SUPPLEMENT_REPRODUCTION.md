# Supplementary evidence checks

From the repository root, use Python 3.12 or newer with no extra Python packages:

```sh
python3 reproduce_supplement.py --output .reproduce/supplement-check
```

The output directory must be new. The wrapper invokes the included original
verifiers, redirects all reports to that directory, and copies the two small
files needed by verifiers that read beside their outputs. It does not alter
checked-in sources, inputs or observations, execute a PIR backend, or collect
new performance measurements. Do not use `python -O`: the original verifiers
use assertions.

Expected checks are:

| Check | Expected result |
| --- | --- |
| Earlier six-workload experiment | 180 recorded processes; 18,000 reconstructed roots and tamper rejections; 282,000 recovered-record byte checks |
| Joint necessary-bound evaluator | 3,438 frozen rows; zero mismatches |
| Wrapper-family verifier | 109 proofs over six previously specified wrapper counts |
| Five residual states | 222 proofs and 27 projected inequalities |

The compact result is `supplement_verification.json` in the new output directory.
Detailed derived tables and the earlier-workload report are under `legacy/`;
theory certificates are under `joint/`, `wrapper/` and `five_states/`. Verifier
logs are retained there. A failed check exits nonzero; incomplete output is kept
for diagnosis, and another attempt requires a new output directory.

The earlier workload experiment uses its recorded eight-scalar-call SimplePIR
representation per digest. It remains separate from the native 32-byte main
experiments described in [NATIVE_REPRODUCTION.md](NATIVE_REPRODUCTION.md). Its
reported timings are recomputed summaries of frozen observations, not fresh
measurements. The theory commands check the existing rows and explicit
constructions; they do not run a new exact-search census or constitute a proof
of the entire infinite wrapper family.

Either group can be checked independently:

```sh
python3 reproduce_supplement.py --checks legacy --output .reproduce/legacy-check
python3 reproduce_supplement.py --checks theory --output .reproduce/theory-check
```

The source release intentionally omits recorded executables. This wrapper does
not authenticate the original executable bytes or rerun lattice decryption.
The earlier-workload auditor checks recovered records, authentication, pairing
and accounting, including consistency of recorded binary-hash fields.

Several additional original audit scripts require the omitted exact binaries
and are outside this wrapper: `audit_tifs_ct_tcp_20260910.py`,
`audit_layout_transfer_tcp_20260910.py`,
`audit_contribution_gate_external_20260910.py`, and `audit_packed_smoke.py`.
Their unchanged full audits are not advertised as passing in this source-only
release. The packed audit also expects an upstream Git checkout; an outer
repository's commit is not a substitute for the SimplePIR upstream revision.
Rebuilding permits new executions but need not reproduce a recorded binary
hash. No binary-verification check is bypassed here.
