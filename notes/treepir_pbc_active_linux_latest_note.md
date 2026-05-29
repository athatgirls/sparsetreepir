# TreePIR-Compatible PBC Active Backend Latest Run

This run checks the new TreePIR-compatible PBC active-record baseline with real
PBC mechanics and the executable SimplePIR bridge.

## Configuration

- Workloads: `all`
- Height: `128`
- Seeds: `73000,83000,93000`
- Queries per seed: `50`
- Output directory: `examples/treepir_pbc_active_linux_latest`
- Backend: `SimplePIR`

## Summary

| Dataset | Seeds | Cuckoo failures | Max bucket | Avg online KB | Avg setup ms |
|---|---:|---:|---:|---:|---:|
| FuelLabs SMT test vectors | 3 | 0/150 | 49 | 13.562 | 3.693 |
| Polygon zkEVM broad | 3 | 1/150 | 1693 | 134.062 | 110.369 |
| Polygon zkEVM multi-window | 3 | 1/150 | 418 | 53.812 | 28.192 |
| Polygon zkEVM recent | 3 | 0/150 | 151 | 27.094 | 10.049 |
| ZKsync Era broad | 3 | 0/150 | 1850 | 142.188 | 119.979 |
| ZKsync Era sample | 3 | 0/150 | 317 | 45.000 | 20.919 |

## Output Files

- `examples/treepir_pbc_active_linux_latest/treepir_pbc_active_manifest_summary.csv`
- `examples/treepir_pbc_active_linux_latest/treepir_pbc_active_simplepir_summary.csv`
- `examples/treepir_pbc_active_linux_latest/run_simplepir.log`

The run produced 18 manifest rows and 18 SimplePIR backend rows. Total Cuckoo
failures were 2/900, with a maximum per-row failure rate of 0.02.
