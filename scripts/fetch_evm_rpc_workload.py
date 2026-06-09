from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set


RPC_PRESETS = {
    "zksync-era": "https://zksync-era.public-rpc.com",
    "scroll": "https://rpc.scroll.io",
    "polygon-zkevm": "https://zkevm-rpc.com",
}


@dataclass
class RpcStats:
    requested_blocks: int = 0
    fetched_blocks: int = 0
    failed_blocks: int = 0
    transactions: int = 0
    unique_addresses: int = 0
    workload_keys: int = 0


def rpc_batch_call(url: str, calls: Sequence[tuple[str, Sequence[object], int]], timeout: int = 60) -> List[dict]:
    payload = json.dumps(
        [
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": list(params)}
            for method, params, request_id in calls
        ]
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "SparseTreePIR-EVMWorkload/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict):
        # Some RPCs reject batch requests. Normalize the shape so callers can
        # fall back to smaller batches without special-casing exceptions.
        return [data]
    if not isinstance(data, list):
        raise RuntimeError(f"Unexpected JSON-RPC response type: {type(data).__name__}")
    return data


def rpc_call(url: str, method: str, params: Sequence[object], timeout: int = 30) -> object:
    response = rpc_batch_call(url, [(method, params, 1)], timeout=timeout)
    item = response[0]
    if "error" in item:
        raise RuntimeError(f"RPC error for {method}: {item['error']}")
    return item.get("result")


def parse_block_number(value: object) -> int:
    if value is None:
        raise ValueError("null block number")
    if isinstance(value, str):
        return int(value, 16)
    return int(value)


def normalize_address(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if len(value) == 42 and value.startswith("0x"):
        return value
    return None


def extract_addresses_from_block(block: Dict[str, object]) -> Set[str]:
    addresses: Set[str] = set()
    transactions = block.get("transactions") or []
    if not isinstance(transactions, list):
        return addresses
    for tx in transactions:
        if not isinstance(tx, dict):
            continue
        for field in ("from", "to"):
            address = normalize_address(tx.get(field))
            if address:
                addresses.add(address)
    return addresses


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
    batch_size = max(1, batch_size)
    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start : batch_start + batch_size]
        calls = [
            ("eth_getBlockTransactionCountByNumber", [hex(block_number)], request_id + idx)
            for idx, block_number in enumerate(batch)
        ]
        request_id += len(calls)
        try:
            responses = rpc_batch_call(rpc_url, calls, timeout=90)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: tx-count batch failed at {batch[0]}..{batch[-1]}: {exc}")
            continue
        if len(responses) == 1 and "error" in responses[0] and len(batch) > 1:
            # RPC likely rejected batch size. Retry as single calls.
            responses = []
            for method, params, rid in calls:
                try:
                    responses.extend(rpc_batch_call(rpc_url, [(method, params, rid)], timeout=30))
                except Exception:
                    continue
        by_id = {item.get("id"): item for item in responses if isinstance(item, dict)}
        for idx, block_number in enumerate(batch):
            item = by_id.get(calls[idx][2])
            if not item or "error" in item:
                continue
            try:
                result = item.get("result")
                count = int(result, 16) if isinstance(result, str) else int(result)
            except (TypeError, ValueError):
                continue
            if count > 0:
                nonempty.append(block_number)
                if max_nonempty_blocks is not None and len(nonempty) >= max_nonempty_blocks:
                    return nonempty
    return nonempty


def fetch_addresses(
    rpc_url: str,
    block_numbers: Sequence[int],
    sleep_seconds: float,
    block_batch_size: int,
    max_addresses: Optional[int],
) -> tuple[List[dict], RpcStats]:
    stats = RpcStats(requested_blocks=len(block_numbers))
    addresses: Dict[str, dict] = {}
    request_id = 1
    block_batch_size = max(1, block_batch_size)
    for batch_start in range(0, len(block_numbers), block_batch_size):
        batch = list(block_numbers[batch_start : batch_start + block_batch_size])
        calls = [
            ("eth_getBlockByNumber", [hex(block_number), True], request_id + idx)
            for idx, block_number in enumerate(batch)
        ]
        request_id += len(calls)
        try:
            responses = rpc_batch_call(rpc_url, calls, timeout=120)
        except Exception as exc:  # noqa: BLE001
            stats.failed_blocks += len(batch)
            print(f"warning: block batch failed {batch[0]}..{batch[-1]}: {exc}")
            continue
        if len(responses) == 1 and "error" in responses[0] and len(batch) > 1:
            responses = []
            for method, params, rid in calls:
                try:
                    responses.extend(rpc_batch_call(rpc_url, [(method, params, rid)], timeout=30))
                except Exception:
                    continue
        by_id = {item.get("id"): item for item in responses if isinstance(item, dict)}
        for idx, block_number in enumerate(batch):
            item = by_id.get(calls[idx][2])
            if not item or "error" in item or not isinstance(item.get("result"), dict):
                stats.failed_blocks += 1
                continue
            block = item["result"]
            stats.fetched_blocks += 1
            txs = block.get("transactions") or []
            if isinstance(txs, list):
                stats.transactions += len(txs)
            for address in extract_addresses_from_block(block):
                if address not in addresses:
                    addresses[address] = {"address": address, "first_seen_block": block_number}
                    if max_addresses is not None and len(addresses) >= max_addresses:
                        stats.unique_addresses = len(addresses)
                        return list(addresses.values()), stats
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
    stats.unique_addresses = len(addresses)
    return list(addresses.values()), stats


def write_addresses(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["address", "first_seen_block"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_account_workload(path: Path, rows: Sequence[dict], chain: str, leaf_types: Sequence[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["key", "address", "leaf_type", "first_seen_block"])
        writer.writeheader()
        for row in rows:
            for leaf_type in leaf_types:
                writer.writerow(
                    {
                        "key": f"{chain}:{row['address']}:account_leaf:{leaf_type}",
                        "address": row["address"],
                        "leaf_type": leaf_type,
                        "first_seen_block": row["first_seen_block"],
                    }
                )
                count += 1
    return count


def parse_list(raw: str) -> List[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a public EVM-chain account workload from JSON-RPC blocks.")
    parser.add_argument("--chain", default="zksync-era")
    parser.add_argument("--rpc-url", default=None)
    parser.add_argument("--latest-minus", type=int, default=1000)
    parser.add_argument("--blocks", type=int, default=50000)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--scan-counts", action="store_true")
    parser.add_argument("--count-batch-size", type=int, default=100)
    parser.add_argument("--max-nonempty-blocks", type=int, default=500)
    parser.add_argument("--block-batch-size", type=int, default=25)
    parser.add_argument("--max-addresses", type=int, default=5000)
    parser.add_argument("--sleep", type=float, default=0.001)
    parser.add_argument("--leaf-types", default="balance,nonce,code,storage_root")
    parser.add_argument("--address-output", type=Path, default=None)
    parser.add_argument("--workload-output", type=Path, default=None)
    parser.add_argument("--summary-output", type=Path, default=None)
    args = parser.parse_args()

    rpc_url = args.rpc_url or RPC_PRESETS.get(args.chain)
    if not rpc_url:
        raise ValueError(f"No RPC URL provided and no preset for chain {args.chain!r}")

    latest = parse_block_number(rpc_call(rpc_url, "eth_blockNumber", []))
    end_block = max(0, latest - args.latest_minus)
    start_block = max(0, end_block - args.blocks + 1)
    if args.scan_counts:
        blocks = scan_nonempty_blocks(
            rpc_url=rpc_url,
            start_block=start_block,
            end_block=end_block,
            step=max(1, args.step),
            batch_size=max(1, args.count_batch_size),
            max_nonempty_blocks=args.max_nonempty_blocks,
        )
    else:
        blocks = list(range(start_block, end_block + 1, max(1, args.step)))
    print(f"latest={latest} range=[{start_block},{end_block}] candidate_blocks={len(blocks)}")

    rows, stats = fetch_addresses(
        rpc_url=rpc_url,
        block_numbers=blocks,
        sleep_seconds=max(0.0, args.sleep),
        block_batch_size=max(1, args.block_batch_size),
        max_addresses=args.max_addresses,
    )
    address_output = args.address_output or Path(f"datasets/{args.chain}_addresses.csv")
    workload_output = args.workload_output or Path(f"datasets/{args.chain}_account_leaf_workload.csv")
    summary_output = args.summary_output or Path(f"datasets/{args.chain}_workload_summary.json")
    write_addresses(address_output, rows)
    workload_keys = write_account_workload(workload_output, rows, args.chain, parse_list(args.leaf_types))
    stats.workload_keys = workload_keys
    summary = {
        "source": f"{args.chain} public JSON-RPC account workload",
        "chain": args.chain,
        "rpc_url": rpc_url,
        "latest_block": latest,
        "start_block": start_block,
        "end_block": end_block,
        "candidate_blocks": len(blocks),
        "fetched_blocks": stats.fetched_blocks,
        "failed_blocks": stats.failed_blocks,
        "transactions": stats.transactions,
        "unique_addresses": stats.unique_addresses,
        "leaf_types": parse_list(args.leaf_types),
        "workload_keys": workload_keys,
        "note": "Address-derived account workload, not a full state-tree node dump.",
    }
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"address_output={address_output}")
    print(f"workload_output={workload_output}")
    print(f"summary_output={summary_output}")


if __name__ == "__main__":
    main()
