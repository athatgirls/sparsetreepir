# ZKsync Era SMT-Workload Evaluation

This note records a second real rollup-derived workload, complementary to the Polygon zkEVM experiment.

## Scope

ZKsync Era is a real rollup system with public transaction data and public RPC access. The experiment below is an address-derived account workload mapped into SMT coordinates.

Important scope:

> This is not a full ZKsync state-tree node dump. It is a ZKsync-Era-derived account workload extracted from public JSON-RPC blocks and expanded into account-level leaf keys.

The workload key format is:

```text
zksync-era:{address}:account_leaf:{leaf_type}
```

The current leaf types are:

```text
balance, nonce, code, storage_root
```

## Data collection

Script:

```text
scripts/fetch_evm_rpc_workload.py
```

Small sample command:

```powershell
python scripts\fetch_evm_rpc_workload.py `
  --chain zksync-era `
  --rpc-url https://mainnet.era.zksync.io `
  --blocks 50000 `
  --step 200 `
  --block-batch-size 20 `
  --max-addresses 3000 `
  --sleep 0.001 `
  --address-output datasets\zksync_era_addresses_sample.csv `
  --workload-output datasets\zksync_era_account_leaf_workload_sample.csv `
  --summary-output datasets\zksync_era_workload_sample_summary.json
```

Broad sample command:

```powershell
python scripts\fetch_evm_rpc_workload.py `
  --chain zksync-era `
  --rpc-url https://mainnet.era.zksync.io `
  --blocks 500000 `
  --step 200 `
  --block-batch-size 30 `
  --max-addresses 10000 `
  --sleep 0.001 `
  --address-output datasets\zksync_era_addresses_broad_sample.csv `
  --workload-output datasets\zksync_era_account_leaf_workload_broad_sample.csv `
  --summary-output datasets\zksync_era_workload_broad_sample_summary.json
```

Collection summary:

| Workload | Candidate blocks | Transactions | Unique addresses | Account-level keys |
|---|---:|---:|---:|---:|
| ZKsync sample | 250 | 272 | 239 | 956 |
| ZKsync broad | 2,500 | 2,806 | 1,935 | 7,740 |

## SparseTreePIR workload experiment

Commands:

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\zksync_era_account_leaf_workload_sample.csv `
  --column key `
  --label zksync_era_account_leaf_workload_sample `
  --heights 128,256 `
  --key-mode sha256 `
  --initial-rounds 120 `
  --refine-rounds 20 `
  --output examples\zksync_era_smt_workload_sample_results.csv
```

```powershell
python scripts\run_real_smt_workload_experiment.py `
  --input datasets\zksync_era_account_leaf_workload_broad_sample.csv `
  --column key `
  --label zksync_era_account_leaf_workload_broad_sample `
  --heights 128,256 `
  --key-mode sha256 `
  --initial-rounds 120 `
  --refine-rounds 20 `
  --output examples\zksync_era_smt_workload_broad_sample_results.csv
```

Results:

| Workload | Height | Keys | Active nodes | m | Avg. active path | Dummy frac. | Ideal max bucket | Profile max bucket | Ratio | Gap | Valid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| ZKsync sample | 128 | 956 | 1,910 | 13 | 10.19 | 21.62% | 147 | 147 | 1.000 | 1 | yes |
| ZKsync sample | 256 | 956 | 1,910 | 13 | 10.19 | 21.62% | 147 | 147 | 1.000 | 1 | yes |
| ZKsync broad | 128 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 911 | 911 | 1.000 | 1 | yes |
| ZKsync broad | 256 | 7,740 | 15,478 | 17 | 13.25 | 22.03% | 911 | 911 | 1.000 | 1 | yes |

## Interpretation

ZKsync broad is now the largest real rollup-derived workload in the workspace:

- 7,740 account-level keys;
- 15,478 active proof-bearing nodes;
- exact active width `m=17`;
- average active path length 13.25;
- profile-balanced maximum bucket exactly matches the ideal equal-split bound.

Together with Polygon zkEVM broad, this gives us two independent real rollup-derived workloads with consistent behavior.

## Files

```text
datasets/zksync_era_addresses_sample.csv
datasets/zksync_era_account_leaf_workload_sample.csv
datasets/zksync_era_workload_sample_summary.json
datasets/zksync_era_addresses_broad_sample.csv
datasets/zksync_era_account_leaf_workload_broad_sample.csv
datasets/zksync_era_workload_broad_sample_summary.json
examples/zksync_era_smt_workload_sample_results.csv
examples/zksync_era_smt_workload_broad_sample_results.csv
examples/real_rollup_smt_workload_summary.csv
```

## Paper wording

Use:

```text
ZKsync-Era-derived account workload
```

Avoid:

```text
ZKsync SMT dataset
full ZKsync state-tree dump
```
