from __future__ import annotations

import argparse
import csv
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence


def read_layout_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def wsl_path(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    rest = str(resolved)[3:].replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def parse_runner_csv(stdout: str) -> Dict[str, float]:
    stdout = stdout.replace("\x00", "")
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    header_index = None
    for idx, line in enumerate(lines):
        if "setup_ms," in line:
            header_index = idx
            lines[idx] = line[line.index("setup_ms,") :]
            break
    if header_index is None or header_index + 1 >= len(lines):
        raise RuntimeError(f"PIANO runner did not emit CSV metrics:\n{stdout}")
    headers = lines[header_index].split(",")
    values = lines[header_index + 1].split(",")
    parsed: Dict[str, float] = {}
    for key, raw in zip(headers, values):
        if key == "queries":
            parsed[key] = float(int(raw))
        else:
            parsed[key] = float(raw)
    return parsed


def run_piano(
    repo: Path,
    sizes: Sequence[int],
    queries: int,
    seed: int,
    timeout: int,
) -> Dict[str, float]:
    sizes_arg = ",".join(str(max(1, int(size))) for size in sizes)
    repo_arg = shlex.quote(wsl_path(repo) if os.name == "nt" else str(repo.resolve()))
    cmd = (
        f"cd {repo_arg} && "
        f"GOPROXY=https://goproxy.cn,direct go run eval/smt_layout_benchmark.go "
        f"-sizes {sizes_arg} -queries {queries} -seed {seed}"
    )
    runner = (
        ["wsl.exe", "-d", os.environ.get("SPARSETREEPIR_WSL_DISTRO", "Ubuntu-24.04"), "--", "bash", "-lc", cmd]
        if os.name == "nt"
        else ["bash", "-lc", cmd]
    )
    result = subprocess.run(
        runner,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    return parse_runner_csv(result.stdout)


def build_rows(layout_csv: Path, repo: Path, queries: int, timeout: int) -> List[Dict[str, object]]:
    layout_rows = read_layout_rows(layout_csv)
    wanted = {"pbc_smt_active", "sparsetreepir_activebalance"}
    rows: List[Dict[str, object]] = []
    for row in layout_rows:
        if int(row["height"]) != 128:
            continue
        if row["scheme"] not in wanted:
            continue
        width = int(row["width"])
        max_bucket = int(row["max_bucket"])
        stored_records = int(row["stored_records"])
        if row["scheme"] == "pbc_smt_active":
            # Reconstruct nearly equal PBC bucket sizes.
            base, rem = divmod(stored_records, width)
            sizes = [base + (1 if idx < rem else 0) for idx in range(width)]
            scheme = "PBC-SMT"
        else:
            # We only need the backend-facing bucket vector. The summary CSV
            # stores the max bucket and total records, not every color load, so
            # use a conservative equal-fill vector capped by max_bucket. This
            # matches the near-lower-bound ActiveBalance profile reported in
            # the experiment and avoids reconstructing the full tree again.
            remaining = stored_records
            sizes = []
            for _ in range(width):
                value = min(max_bucket, remaining)
                sizes.append(value)
                remaining -= value
            idx = 0
            while remaining > 0:
                room = max_bucket - sizes[idx]
                add = min(room, remaining)
                sizes[idx] += add
                remaining -= add
                idx = (idx + 1) % len(sizes)
            scheme = "SparseTreePIR"
        metrics = run_piano(
            repo=repo,
            sizes=sizes,
            queries=queries,
            seed=1009 + len(rows) * 17,
            timeout=timeout,
        )
        rows.append(
            {
                "backend": "PIANO-local-runner",
                "dataset": row["dataset"],
                "height": int(row["height"]),
                "scheme": scheme,
                "active_records": int(row["active_records"]),
                "width": width,
                "max_bucket": max_bucket,
                "query_samples": queries,
                "setup_ms": metrics["setup_ms"],
                "client_query_ms": metrics["client_query_ms"],
                "server_total_ms": metrics["server_total_ms"],
                "server_parallel_ms": metrics["server_parallel_ms"],
                "online_upload_kb": metrics["online_upload_kb"],
                "online_download_kb": metrics["online_download_kb"],
                "online_total_kb": metrics["online_total_kb"],
                "offline_kb": metrics["offline_kb"],
                "completed_queries": int(metrics["queries"]),
            }
        )
    return rows


def summarize(rows: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    grouped: Dict[tuple[str, int], Dict[str, Dict[str, object]]] = {}
    for row in rows:
        key = (str(row["dataset"]), int(row["height"]))
        grouped.setdefault(key, {})[str(row["scheme"])] = row
    out: List[Dict[str, object]] = []
    for (dataset, height), schemes in sorted(grouped.items()):
        if "PBC-SMT" not in schemes or "SparseTreePIR" not in schemes:
            continue
        pbc = schemes["PBC-SMT"]
        sparse = schemes["SparseTreePIR"]
        out.append(
            {
                "backend": "PIANO-local-runner",
                "dataset": dataset,
                "height": height,
                "pbc_width": pbc["width"],
                "sparse_width": sparse["width"],
                "pbc_online_kb": pbc["online_total_kb"],
                "sparse_online_kb": sparse["online_total_kb"],
                "online_reduction": 1.0 - float(sparse["online_total_kb"]) / max(1e-9, float(pbc["online_total_kb"])),
                "pbc_query_ms": pbc["client_query_ms"],
                "sparse_query_ms": sparse["client_query_ms"],
                "query_reduction": 1.0 - float(sparse["client_query_ms"]) / max(1e-9, float(pbc["client_query_ms"])),
                "pbc_parallel_ms": pbc["server_parallel_ms"],
                "sparse_parallel_ms": sparse["server_parallel_ms"],
                "parallel_reduction": 1.0 - float(sparse["server_parallel_ms"]) / max(1e-9, float(pbc["server_parallel_ms"])),
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout-csv", type=Path, default=Path("examples/real_smt_final_suite_layouts.csv"))
    parser.add_argument("--piano-repo", type=Path, default=Path(".tools/piano-pir-new"))
    parser.add_argument("--queries", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path, default=Path("examples/piano_wsl_backend_results.csv"))
    parser.add_argument("--summary", type=Path, default=Path("examples/piano_wsl_backend_summary.csv"))
    args = parser.parse_args()
    rows = build_rows(args.layout_csv, args.piano_repo, args.queries, args.timeout)
    write_csv(args.output, rows)
    summary = summarize(rows)
    write_csv(args.summary, summary)
    print(f"Wrote {args.output}")
    print(f"Wrote {args.summary}")


if __name__ == "__main__":
    main()
