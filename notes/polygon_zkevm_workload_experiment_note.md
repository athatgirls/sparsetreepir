# Polygon zkEVM SMT-Workload Evaluation

This note records the Polygon-specific replacement for the earlier Xenon "real data" experiment.

## Why Polygon

Polygon zkEVM is a better fit than Xenon for the SMT story because Polygon zkEVM documents its L2 state as a Sparse Merkle Tree / Sparse Merkle Trie. Its state leaves are keyed by account address plus an `SMT_KEY` type, including account-level fields such as balance, nonce, code hash, and code-hash length.

Important scope:

> This experiment is a Polygon-zkEVM-derived SMT workload, not a full Polygon state-tree node dump.

We collect real account addresses from Polygon zkEVM public blocks and expand each observed address into account-level SMT workload keys:

```text
polygon-zkevm:{address}:SMT_KEY:{type}
```

The current experiment uses account-level SMT key types:

| SMT_KEY | Meaning |
|---:|---|
| 0 | balance |
| 1 | nonce |
| 2 | code hash |
| 4 | code-hash length |

We omit storage slot leaves (`SMT_KEY=3`) because a public block transaction alone does not expose a complete state/storage-key snapshot.

## Data collection

### Recent contiguous sample

Script:

```text
scripts/fetch_polygon_zkevm_workload.py
```

Command:

```powershell
python scripts\fetch_polygon_zkevm_workload.py `
  --blocks 200000 `
  --step 1 `
  --scan-counts `
  --count-batch-size 100 `
  --max-nonempty-blocks 1000 `
  --block-batch-size 25 `
  --latest-minus 1000 `
  --max-addresses 5000 `
  --sleep 0.002 `
  --address-output datasets\polygon_zkevm_addresses_1000_nonempty.csv `
  --workload-output datasets\polygon_zkevm_account_leaf_workload_1000_nonempty.csv `
  --summary-output datasets\polygon_zkevm_workload_1000_nonempty_summary.json
```

Collection summary:

| Field | Value |
|---|---:|
| Source | Polygon zkEVM public JSON-RPC |
| RPC endpoint | `https://zkevm-rpc.com` |
| Latest block observed | 32,097,719 |
| Scanned range | 31,896,720--32,096,719 |
| Non-empty blocks fetched | 1,000 |
| Transactions parsed | 1,561 |
| Unique addresses | 163 |
| Account-level workload keys | 652 |

Polygon zkEVM activity in this recent range is sparse; this is why scanning transaction counts first is necessary.

### Multi-window sample

We added a broader multi-window sample to avoid overfitting to a narrow recent range. The script samples four historical windows, scans transaction counts with `step=5`, fetches 200 non-empty blocks per window, and merges addresses.

Script:

```text
scripts/fetch_polygon_zkevm_multiwindow_workload.py
```

Command:

```powershell
python scripts\fetch_polygon_zkevm_multiwindow_workload.py `
  --offsets 1000,1000000,4000000,10000000 `
  --window-blocks 50000 `
  --step 5 `
  --count-batch-size 100 `
  --max-nonempty-per-window 200 `
  --block-batch-size 25 `
  --max-addresses 5000 `
  --sleep 0.001 `
  --address-output datasets\polygon_zkevm_addresses_multiwindow.csv `
  --workload-output datasets\polygon_zkevm_account_leaf_workload_multiwindow.csv `
  --summary-output datasets\polygon_zkevm_workload_multiwindow_summary.json
```

Multi-window collection summary:

| Window offset from latest | Non-empty blocks | Transactions | Unique addresses in window | Merged unique addresses |
|---:|---:|---:|---:|---:|
| 1,000 | 200 | 296 | 66 | 66 |
| 1,000,000 | 200 | 303 | 64 | 94 |
| 4,000,000 | 200 | 264 | 130 | 183 |
| 10,000,000 | 200 | 254 | 199 | 337 |

Total multi-window workload:

| Field | Value |
|---|---:|
| Non-empty blocks fetched | 800 |
| Transactions parsed | 1,117 |
| Unique addresses | 337 |
| Account-level workload keys | 1,348 |

### Broad multi-window sample

For a stronger main-paper result, we also sampled eleven historical windows across the Polygon zkEVM chain. This gives a broader workload than either a recent contiguous range or four-window sample.

Command:

```powershell
python scripts\fetch_polygon_zkevm_multiwindow_workload.py `
  --offsets 1000,500000,1000000,2000000,4000000,8000000,12000000,16000000,20000000,24000000,28000000 `
  --window-blocks 100000 `
  --step 10 `
  --count-batch-size 100 `
  --max-nonempty-per-window 300 `
  --block-batch-size 25 `
  --max-addresses 10000 `
  --sleep 0.001 `
  --address-output datasets\polygon_zkevm_addresses_broad_multiwindow.csv `
  --workload-output datasets\polygon_zkevm_account_leaf_workload_broad_multiwindow.csv `
  --summary-output datasets\polygon_zkevm_workload_broad_multiwindow_summary.json
```

Broad multi-window collection summary:

| Field | Value |
|---|---:|
| Historical windows | 11 |
| Non-empty blocks fetched | 3,240 |
| Transactions parsed | 4,323 |
| Unique addresses | 1,760 |
| Account-level workload keys | 7,040 |

## SparseTreePIR workload experiment

Script:

```text
scripts/run_real_smt_workload_experiment.py
```

Commands:

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\polygon_zkevm_account_leaf_workload_1000_nonempty.csv `
  --column key `
  --label polygon_zkevm_1000_nonempty_account_leaf_workload `
  --heights 128,256 `
  --key-mode sha256 `
  --initial-rounds 120 `
  --refine-rounds 20 `
  --output examples\polygon_zkevm_smt_workload_1000_nonempty_results.csv
```

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\polygon_zkevm_account_leaf_workload_multiwindow.csv `
  --column key `
  --label polygon_zkevm_multiwindow_account_leaf_workload `
  --heights 128,256 `
  --key-mode sha256 `
  --initial-rounds 120 `
  --refine-rounds 20 `
  --output examples\polygon_zkevm_smt_workload_multiwindow_results.csv
```

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\polygon_zkevm_account_leaf_workload_broad_multiwindow.csv `
  --column key `
  --label polygon_zkevm_broad_multiwindow_account_leaf_workload `
  --heights 128,256 `
  --key-mode sha256 `
  --initial-rounds 120 `
  --refine-rounds 20 `
  --output examples\polygon_zkevm_smt_workload_broad_multiwindow_results.csv
```

Results:

| Workload | Height | Keys | Active nodes | m | Avg. active path | Dummy frac. | Ideal max bucket | Profile max bucket | Ratio | Gap | Valid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Polygon recent account leaves | 128 | 652 | 1,302 | 12 | 9.68 | 19.36% | 109 | 109 | 1.000 | 1 | yes |
| Polygon recent account leaves | 256 | 652 | 1,302 | 12 | 9.68 | 19.36% | 109 | 109 | 1.000 | 1 | yes |
| Polygon multi-window account leaves | 128 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 193 | 193 | 1.000 | 1 | yes |
| Polygon multi-window account leaves | 256 | 1,348 | 2,694 | 14 | 10.73 | 23.36% | 193 | 193 | 1.000 | 1 | yes |
| Polygon broad multi-window account leaves | 128 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 829 | 829 | 1.000 | 1 | yes |
| Polygon broad multi-window account leaves | 256 | 7,040 | 14,078 | 17 | 13.11 | 22.86% | 829 | 829 | 1.000 | 1 | yes |

## Interpretation

The key takeaways are:

1. The experiment is now tied to a real SMT-using system, unlike the Xenon transparency-log workload.
2. The private retrieval structure is tiny compared with a height-128 or height-256 logical tree. In the broad multi-window sample, only 14,078 active proof-bearing nodes are stored for 7,040 account-level workload keys.
3. The active private width is `m=17` in the broad sample, while the verification proof remains height 128 or 256.
4. `profile_balanced` reaches the ideal equal-split maximum bucket size on both Polygon workloads.
5. The result is valid for both height 128 and 256 because the workload keys are hash-distributed and the active branching skeleton is unchanged at these heights for these samples.

## Limitations

This should be written carefully in the paper:

- This is not a complete Polygon state-tree dump.
- It is an account-level key workload extracted from public transactions.
- We do not include storage-slot SMT leaves because complete storage keys require state/storage access, not just block transactions.
- Polygon zkEVM recent activity is sparse. The broad multi-window sample improves coverage, but a production-scale experiment should use an explorer/data dump or node-exported state/storage keys.

## How to write it in the paper

Use:

```text
Polygon-zkEVM-derived SMT workload
```

Avoid:

```text
Polygon SMT dataset
full Polygon state-tree dump
```

Suggested sentence:

> Because public full SMT node dumps are rarely available, we evaluate on a Polygon-zkEVM-derived account-level SMT workload. We collect real addresses from Polygon zkEVM public blocks, expand each address into account-level state-leaf keys according to Polygon's documented SMT_KEY layout, and reconstruct the active proof-bearing skeleton under 128- and 256-bit SMT coordinates.

Suggested table rows:

```latex
Polygon recent & 128 & 652 & 1302 & 12 & 9.68 & 19.36\% & 109 & 109 & 1.000 \\
Polygon recent & 256 & 652 & 1302 & 12 & 9.68 & 19.36\% & 109 & 109 & 1.000 \\
Polygon multi-window & 128 & 1348 & 2694 & 14 & 10.73 & 23.36\% & 193 & 193 & 1.000 \\
Polygon multi-window & 256 & 1348 & 2694 & 14 & 10.73 & 23.36\% & 193 & 193 & 1.000 \\
Polygon broad & 128 & 7040 & 14078 & 17 & 13.11 & 22.86\% & 829 & 829 & 1.000 \\
Polygon broad & 256 & 7040 & 14078 & 17 & 13.11 & 22.86\% & 829 & 829 & 1.000 \\
```

CSV summary:

```text
examples/polygon_zkevm_smt_workload_summary.csv
```
