from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

import fetch_polygon_zkevm_workload as polygon


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("integer list cannot be empty")
    return values


def merge_address_rows(existing: Dict[str, dict], rows: List[dict], window_label: str) -> None:
    for row in rows:
        address = row["address"]
        first_seen = int(row["first_seen_block"])
        if address not in existing:
            existing[address] = {
                "address": address,
                "first_seen_block": first_seen,
                "window": window_label,
            }
        else:
            existing[address]["first_seen_block"] = min(int(existing[address]["first_seen_block"]), first_seen)


def write_merged_addresses(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["address", "first_seen_block", "window"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Collect a larger Polygon zkEVM address workload by sampling several historical windows. "
            "This avoids long single-range scans and gives a broader account workload."
        )
    )
    parser.add_argument("--rpc-url", default=polygon.DEFAULT_RPC_URL)
    parser.add_argument(
        "--offsets",
        default="1000,500000,1000000,2000000,4000000,8000000,12000000,20000000",
        help="Comma-separated distances from latest block. Each offset is the end of one historical window.",
    )
    parser.add_argument("--window-blocks", type=int, default=100000)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--count-batch-size", type=int, default=200)
    parser.add_argument("--block-batch-size", type=int, default=50)
    parser.add_argument("--max-nonempty-per-window", type=int, default=300)
    parser.add_argument("--max-addresses", type=int, default=10000)
    parser.add_argument("--leaf-types", default=polygon.DEFAULT_LEAF_TYPES)
    parser.add_argument("--sleep", type=float, default=0.001)
    parser.add_argument("--address-output", type=Path, default=Path("datasets/polygon_zkevm_addresses_multiwindow.csv"))
    parser.add_argument("--workload-output", type=Path, default=Path("datasets/polygon_zkevm_account_leaf_workload_multiwindow.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("datasets/polygon_zkevm_workload_multiwindow_summary.json"))
    args = parser.parse_args()

    latest = polygon.parse_block_number(polygon.rpc_call(args.rpc_url, "eth_blockNumber", []))
    offsets = parse_int_list(args.offsets)
    leaf_types = polygon.parse_int_list(args.leaf_types)

    merged: Dict[str, dict] = {}
    window_summaries: List[dict] = []

    for offset in offsets:
        end_block = max(0, latest - offset)
        start_block = max(0, end_block - args.window_blocks + 1)
        window_label = f"{start_block}-{end_block}"
        print(f"window={window_label} step={args.step}")

        nonempty = polygon.scan_nonempty_blocks(
            rpc_url=args.rpc_url,
            start_block=start_block,
            end_block=end_block,
            step=max(1, args.step),
            batch_size=max(1, args.count_batch_size),
            max_nonempty_blocks=args.max_nonempty_per_window,
        )
        print(f"  nonempty_blocks={len(nonempty)}")
        rows, stats = polygon.fetch_addresses(
            rpc_url=args.rpc_url,
            block_numbers=nonempty,
            sleep_seconds=max(0.0, args.sleep),
            max_addresses=None,
            block_batch_size=max(1, args.block_batch_size),
        )
        merge_address_rows(merged, rows, window_label)
        window_summaries.append(
            {
                "window": window_label,
                "offset": offset,
                "sampled_blocks": len(list(range(start_block, end_block + 1, max(1, args.step)))),
                "nonempty_blocks": len(nonempty),
                "fetched_blocks": stats.fetched_blocks,
                "transactions": stats.transactions,
                "unique_addresses_in_window": len(rows),
                "unique_addresses_merged": len(merged),
            }
        )
        print(
            f"  tx={stats.transactions}, window_unique={len(rows)}, merged_unique={len(merged)}"
        )
        if len(merged) >= args.max_addresses:
            break

    merged_rows = sorted(merged.values(), key=lambda row: (int(row["first_seen_block"]), row["address"]))
    if len(merged_rows) > args.max_addresses:
        merged_rows = merged_rows[: args.max_addresses]

    write_merged_addresses(args.address_output, merged_rows)
    workload_keys = polygon.write_polygon_leaf_workload(args.workload_output, merged_rows, leaf_types)

    summary = {
        "source": "Polygon zkEVM public JSON-RPC multi-window sample",
        "rpc_url": args.rpc_url,
        "latest_block": latest,
        "offsets": offsets,
        "window_blocks": args.window_blocks,
        "step": args.step,
        "leaf_types": leaf_types,
        "leaf_type_names": {str(key): polygon.LEAF_TYPE_NAMES.get(key, f"type_{key}") for key in leaf_types},
        "window_summaries": window_summaries,
        "unique_addresses": len(merged_rows),
        "workload_keys": workload_keys,
        "note": (
            "Multi-window public-block address workload for Polygon zkEVM. "
            "This is not a full state-tree node dump; account-level SMT keys are expanded from observed addresses."
        ),
    }
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"unique_addresses={len(merged_rows)}")
    print(f"workload_keys={workload_keys}")
    print(f"address_output={args.address_output}")
    print(f"workload_output={args.workload_output}")
    print(f"summary_output={args.summary_output}")


if __name__ == "__main__":
    main()
