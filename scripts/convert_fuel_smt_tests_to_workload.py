from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


def load_tests(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise ValueError(f"Unsupported Fuel SMT test spec shape: {type(data).__name__}")


def encoded_value_to_string(value: dict | None) -> str:
    if not value:
        return ""
    return str(value.get("value", ""))


def step_deletes_key(step: dict) -> bool:
    action = step.get("action")
    if action == "delete":
        return True
    if action == "update":
        data = step.get("data")
        # The Fuel test generator includes an "Update With Empty Data Performs Delete"
        # case. Treat empty update data as deletion for final live-key workloads.
        return encoded_value_to_string(data) == ""
    return False


def final_live_keys(test: dict) -> List[str]:
    live: Dict[str, None] = {}
    for step in test.get("steps", []):
        if not isinstance(step, dict):
            continue
        key = encoded_value_to_string(step.get("key"))
        if not key:
            continue
        if step_deletes_key(step):
            live.pop(key, None)
        elif step.get("action") == "update":
            live[key] = None
    return sorted(live.keys())


def iter_workload_rows(tests: Sequence[dict], emit_intermediate: bool) -> Iterable[dict]:
    for test in tests:
        name = str(test.get("name", "unnamed"))
        expected_root = encoded_value_to_string(test.get("expected_root"))
        if emit_intermediate:
            live: Dict[str, None] = {}
            for step_index, step in enumerate(test.get("steps", []), start=1):
                if not isinstance(step, dict):
                    continue
                key = encoded_value_to_string(step.get("key"))
                if not key:
                    continue
                if step_deletes_key(step):
                    live.pop(key, None)
                elif step.get("action") == "update":
                    live[key] = None
                for live_key in sorted(live):
                    yield {
                        "key": live_key,
                        "test_name": name,
                        "snapshot": f"step_{step_index}",
                        "expected_root": expected_root,
                    }
        else:
            for key in final_live_keys(test):
                yield {
                    "key": key,
                    "test_name": name,
                    "snapshot": "final",
                    "expected_root": expected_root,
                }


def write_workload(path: Path, rows: Sequence[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["key", "test_name", "snapshot", "expected_root"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(path: Path, tests: Sequence[dict], rows: Sequence[dict], input_path: Path) -> None:
    test_live_counts = {
        str(test.get("name", "unnamed")): len(final_live_keys(test))
        for test in tests
    }
    summary = {
        "source": "FuelLabs/smt-test-generation",
        "input": str(input_path),
        "test_count": len(tests),
        "output_rows": len(rows),
        "unique_keys": len({row["key"] for row in rows}),
        "max_final_live_keys": max(test_live_counts.values(), default=0),
        "test_live_counts": test_live_counts,
        "note": (
            "This is a conformance/test-vector workload, not a real deployed SMT dataset. "
            "It is useful for checking update/delete semantics and small SMT edge cases."
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert FuelLabs smt-test-generation fixture JSON into a SparseTreePIR key workload CSV."
    )
    parser.add_argument("--input", type=Path, required=True, help="Fuel smt_test_spec.json or individual fixture JSON.")
    parser.add_argument("--output", type=Path, default=Path("datasets/fuel_smt_test_workload.csv"))
    parser.add_argument("--summary-output", type=Path, default=Path("datasets/fuel_smt_test_workload_summary.json"))
    parser.add_argument(
        "--emit-intermediate",
        action="store_true",
        help="Emit one workload snapshot per update/delete step instead of only final live keys.",
    )
    args = parser.parse_args()

    tests = load_tests(args.input)
    rows = list(iter_workload_rows(tests, emit_intermediate=args.emit_intermediate))
    write_workload(args.output, rows)
    write_summary(args.summary_output, tests, rows, args.input)
    print(f"tests={len(tests)}")
    print(f"rows={len(rows)}")
    print(f"unique_keys={len({row['key'] for row in rows})}")
    print(f"output={args.output}")
    print(f"summary={args.summary_output}")


if __name__ == "__main__":
    main()
