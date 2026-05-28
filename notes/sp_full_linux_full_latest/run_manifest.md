# S&P Linux Experiment Run Manifest

- Mode: `full`
- Started: `20260528_181935`
- Examples: `examples/sp_full_linux_full_latest`
- Notes: `notes/sp_full_linux_full_latest`
- Workloads: `all`
- Structural heights: `128,256`
- Backend height: `128`
- Backend seeds: `73000,83000,93000`
- Backend query samples per seed: `50`
- Backends: `simplepir,piano`
- Scale heights: `64,128,256`
- Scale occupied counts: `100,1000`
- Scale trials per setting: `3`
- Exact-balance settings: `10:0.98,12:0.99,14:0.995`

## Paper-Facing Outputs

- `examples/sp_full_linux_full_latest/real_smt_final_suite_layouts.csv`
- `examples/sp_full_linux_full_latest/small_opt_balance_results.csv`
- `notes/sp_full_linux_full_latest/profile_balance_scale_experiment_note.md`
- `examples/sp_full_linux_full_latest/real_backend_showcase_repeats_summary.csv`
- `examples/sp_full_linux_full_latest/real_backend_showcase_raw_means.csv`
- `examples/sp_full_linux_full_latest/end_to_end_paired_comparison.csv`
- `notes/sp_full_linux_full_latest/end_to_end_cost_breakdown_note.md`

## Review-Risk Coverage

- TreePIR/pruned/full-layout comparison: `real_smt_final_suite_layouts.csv`; optional official TreePIR run in `official_treepir_perfectized_baseline.csv`.
- ActiveBalance optimality check: `small_opt_balance_results.csv`.
- Scale and distribution sensitivity: `profile_balance_scale_experiment_note.md`.
- Paired executable SimplePIR/PIANO backend evidence: `real_backend_showcase_repeats_*.csv`.
- End-to-end accounting: `end_to_end_paired_comparison.csv`.
