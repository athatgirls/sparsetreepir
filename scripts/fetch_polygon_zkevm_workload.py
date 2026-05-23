from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set


DEFAULT_RPC_URL = "https://zkevm-rpc.com"
DEFAULT_LEAF_TYPES = "0,1,2,4"
LEAF_TYPE_NAMES = {
    0: "balance",
    1: "nonce",
    2: "code_hash",
    3: "storage",
    4: "code_hash_length",
}


@dataclass
class RpcStats:
    requested_blocks: int = 0
    fetched_blocks: int = 0
    failed_blocks: int = 0
    transactions: int = 0
    unique_addresses: int = 0
    workload_keys: int = 0


def rpc_call(url: str, method: str, params: Sequence[object], request_id: int = 1, timeout: int = 30) -> object:
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": list(params),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "SparseTreePIR-PolygonWorkload/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    data = json.loads(raw.decode("utf-8"))
    if "error" in data:
        raise RuntimeError(f"RPC error for {method}: {data['error']}")
    return data.get("result")


def rpc_batch_call(
    url: str,
    calls: Sequence[tuple[str, Sequence[object], int]],
    timeout: int = 60,
) -> List[dict]:
    payload = json.dumps(
        [
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": list(params),
            }
            for method, params, request_id in calls
        ]
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "SparseTreePIR-PolygonWorkload/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list):
        raise RuntimeError(f"Expected JSON-RPC batch response, got {type(data).__name__}")
    return data


def parse_block_number(value: object) -> int:
    if value is None:
        raise ValueError("RPC returned null block number.")
    if isinstance(value, str):
        return int(value, 16)
    if isinstance(value, int):
        return value
    raise TypeError(f"Unsupported block-number value: {value!r}")


def normalize_address(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip().lower()
    if value == "0x" or len(value) != 42 or not value.startswith("0x"):
        return None
    return value


def parse_int_list(raw: str) -> List[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("list cannot be empty")
    return values


def extract_addresses_from_block(block: Dict[str, object]) -> Set[str]:
    addresses: Set[str] = set()
    transactions = block.get("transactions") or []
    if not isinstance(transactions, list):
        return addresses

    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        for field in ("from", "to"):
            address = normalize_address(tx.get(field) if isinstance(tx.get(field), str) else None)
            if address:
                addresses.add(address)
    return addresses


def fetch_addresses(
    rpc_url: str,
    block_numbers: Sequence[int],
    sleep_seconds: float,
    max_addresses: Optional[int],
    block_batch_size: int,
) -> tuple[List[dict], RpcStats]:
    stats = RpcStats()
    addresses: Dict[str, dict] = {}
    stats.requested_blocks = len(block_numbers)

    request_id = 1
    for batch_start in range(0, len(block_numbers), max(1, block_batch_size)):
        batch = list(block_numbers[batch_start : batch_start + max(1, block_batch_size)])
        calls = [
            ("eth_getBlockByNumber", [hex(block_number), True], request_id + idx)
            for idx, block_number in enumerate(batch)
        ]
        request_id += len(calls)
        try:
            responses = rpc_batch_call(rpc_url, calls, timeout=90)
        except Exception as exc:  # noqa: BLE001 - robust data collection.
            stats.failed_blocks += len(batch)
            print(f"warning: failed block batch {batch[0]}..{batch[-1]}: {exc}")
            continue

        by_id = {item.get("id"): item for item in responses if isinstance(item, dict)}
        for idx, block_number in enumerate(batch):
            item = by_id.get(calls[idx][2])
            if not item or "error" in item or not isinstance(item.get("result"), dict):
                stats.failed_blocks += 1
                continue
            result = item["result"]
            stats.fetched_blocks += 1
            transactions = result.get("transactions") or []
            if isinstance(transactions, list):
                stats.transactions += len(transactions)

            for address in extract_addresses_from_block(result):
                if address not in addresses:
                    addresses[address] = {
                        "address": address,
                        "first_seen_block": block_number,
                    }
                    if max_addresses is not None and len(addresses) >= max_addresses:
                        stats.unique_addresses = len(addresses)
                        return list(addresses.values()), stats

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    stats.unique_addresses = len(addresses)
    return list(addresses.values()), stats


def scan_nonempty_blocks(
    rpc_url: str,
    start_block: int,
    end_block: int,
    step: int,
    batch_size: int,
    max_nonempty_blocks: Optional[int],
) -> List[int]:
    candidates = list(range(start_block, end_block + 1, step))
    nonempty: List[int] = []
    request_id = 1

    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start : batch_start + batch_size]
        calls = [
            ("eth_getBlockTransactionCountByNumber", [hex(block_number)], request_id + idx)
            for idx, block_number in enumerate(batch)
        ]
        request_id += len(calls)
        try:
            responses = rpc_batch_call(rpc_url, calls)
        except Exception as exc:  # noqa: BLE001 - keep a robust data-collection script.
            print(f"warning: tx-count batch failed at {batch[0]}..{batch[-1]}: {exc}")
            continue

        by_id = {item.get("id"): item for item in responses if isinstance(item, dict)}
        for idx, block_number in enumerate(batch):
            item = by_id.get(calls[idx][2])
            if not item or "error" in item:
                continue
            result = item.get("result")
            if result is None:
                continue
            try:
                count = int(result, 16) if isinstance(result, str) else int(result)
            except (TypeError, ValueError):
                continue
            if count > 0:
                nonempty.append(block_number)
                if max_nonempty_blocks is not None and len(nonempty) >= max_nonempty_blocks:
                    return nonempty

    return nonempty


def write_address_csv(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["address", "first_seen_block"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_polygon_leaf_workload(path: Path, address_rows: Sequence[dict], leaf_types: Sequence[int]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["key", "address", "leaf_type", "leaf_type_name", "first_seen_block"],
        )
        writer.writeheader()
        for row in address_rows:
            address = row["address"]
            for leaf_type in leaf_types:
                key = f"polygon-zkevm:{address}:SMT_KEY:{leaf_type}"
                writer.writerow(
                    {
                        "key": key,
                        "address": address,
                        "leaf_type": leaf_type,
                        "leaf_type_name": LEAF_TYPE_NAMES.get(leaf_type, f"type_{leaf_type}"),
                        "first_seen_block": row["first_seen_block"],
                    }
                )
                count += 1
    return count


def write_summary(path: Path, stats: RpcStats, rpc_url: str, start_block: int, end_block: int, leaf_types: Sequence[int]) -> None:
    summary = {
        "source": "Polygon zkEVM public JSON-RPC",
        "rpc_url": rpc_url,
        "start_block": start_block,
        "end_block": end_block,
        "leaf_types": list(leaf_types),
        "leaf_type_names": {str(key): LEAF_TYPE_NAMES.get(key, f"type_{key}") for key in leaf_types},
        "requested_blocks": stats.requested_blocks,
        "fetched_blocks": stats.fetched_blocks,
        "failed_blocks": stats.failed_blocks,
        "transactions": stats.transactions,
        "unique_addresses": stats.unique_addresses,
        "workload_keys": stats.workload_keys,
        "note": (
            "This is a Polygon-zkEVM-derived SMT key workload built from public block addresses. "
            "It is not a full Polygon state-tree node dump. Account-level leaf keys are represented "
            "by address plus Polygon SMT_KEY type and then mapped to experiment coordinates by the "
            "SparseTreePIR workload script."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch a Polygon zkEVM address workload and expand it into account-level SMT leaf keys."
    )
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument("--start-block", type=int, default=None)
    parser.add_argument("--end-block", type=int, default=None)
    parser.add_argument("--latest-minus", type=int, default=5000)
    parser.add_argument("--blocks", type=int, default=500)
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--scan-counts", action="store_true", help="Scan tx counts first and fetch only non-empty blocks.")
    parser.add_argument("--count-batch-size", type=int, default=100)
    parser.add_argument("--block-batch-size", type=int, default=25)
    parser.add_argument("--max-nonempty-blocks", type=int, default=None)
    parser.add_argument("--sleep", type=float, default=0.03)
    parser.add_argument("--max-addresses", type=int, default=5000)
    parser.add_argument("--leaf-types", default=DEFAULT_LEAF_TYPES)
    parser.add_argument("--address-output", type=Path, default=Path("datasets/polygon_zkevm_addresses.csv"))
    parser.add_argument("--workload-output", type=Path, default=Path("datasets/polygon_zkevm_account_leaf_workload.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("datasets/polygon_zkevm_workload_summary.json"))
    args = parser.parse_args()

    latest = parse_block_number(rpc_call(args.rpc_url, "eth_blockNumber", []))
    if args.end_block is None:
        end_block = max(0, latest - args.latest_minus)
    else:
        end_block = args.end_block
    if args.start_block is None:
        start_block = max(0, end_block - args.blocks + 1)
    else:
        start_block = args.start_block

    leaf_types = parse_int_list(args.leaf_types)
    if args.scan_counts:
        block_numbers = scan_nonempty_blocks(
            rpc_url=args.rpc_url,
            start_block=start_block,
            end_block=end_block,
            step=max(1, args.step),
            batch_size=max(1, args.count_batch_size),
            max_nonempty_blocks=args.max_nonempty_blocks,
        )
        print(f"nonempty_blocks_found={len(block_numbers)}")
    else:
        block_numbers = list(range(start_block, end_block + 1, max(1, args.step)))

    address_rows, stats = fetch_addresses(
        rpc_url=args.rpc_url,
        block_numbers=block_numbers,
        sleep_seconds=max(0.0, args.sleep),
        max_addresses=args.max_addresses,
        block_batch_size=args.block_batch_size,
    )
    write_address_csv(args.address_output, address_rows)
    stats.workload_keys = write_polygon_leaf_workload(args.workload_output, address_rows, leaf_types)
    write_summary(args.summary_output, stats, args.rpc_url, start_block, end_block, leaf_types)

    print(f"latest_block={latest}")
    print(f"range=[{start_block}, {end_block}], step={args.step}, scan_counts={args.scan_counts}")
    print(f"fetched_blocks={stats.fetched_blocks}/{stats.requested_blocks}, failed={stats.failed_blocks}")
    print(f"transactions={stats.transactions}")
    print(f"unique_addresses={stats.unique_addresses}")
    print(f"workload_keys={stats.workload_keys}")
    print(f"address_output={args.address_output}")
    print(f"workload_output={args.workload_output}")
    print(f"summary_output={args.summary_output}")


if __name__ == "__main__":
    main()
