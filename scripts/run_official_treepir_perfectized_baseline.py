"""Run the official TreePIR indexing code as a perfectized SMT baseline.

The upstream TreePIR artifact takes a tree height h and assumes a complete
perfect binary tree. This script runs its Java indexing class on a few heights,
then aligns the resulting perfect-tree costs with our direct SMT profile results.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TREEPIR_ROOT = Path(os.environ.get("TREEPIR_ROOT", ROOT / "external" / "TreePIR-main"))
TREEPIR_DIR = TREEPIR_ROOT / "TreePIR-Indexing"
WINDOWS_JAVA_EXE = ROOT / "external" / "jre21" / "jdk-21.0.11+10-jre" / "bin" / "java.exe"
DIRECT_RESULTS = ROOT / "examples" / "height16_24_fixed_sparsity_profile_balance_results.csv"
OUT_CSV = ROOT / "examples" / "official_treepir_perfectized_baseline.csv"
OUT_NOTE = ROOT / "notes" / "official_treepir_perfectized_baseline_note.md"

HEIGHTS = [16, 20, 24]
SPARSITY = "0.9995"
TARGET_LEAF = 17


def parse_int_list(raw: str) -> list[int]:
    values = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not values:
        raise ValueError("height list cannot be empty")
    return values


def java_exe() -> str:
    if WINDOWS_JAVA_EXE.exists():
        return str(WINDOWS_JAVA_EXE)
    found = shutil.which("java")
    if found:
        return found
    raise SystemExit("Could not find Java. Install a JRE/JDK or run scripts/setup_linux_extra_backend_sources.sh.")


def run_official_indexing(treepir_dir: Path, height: int, target_leaf: int) -> dict[str, float]:
    if not treepir_dir.exists():
        raise SystemExit(
            f"TreePIR indexing directory not found: {treepir_dir}\n"
            "Run scripts/setup_linux_extra_backend_sources.sh on Linux first."
        )
    list_file = treepir_dir / f"list_TXs_{height}_2.txt"
    list_file.write_text(f"{target_leaf}\n", encoding="utf-8")

    proc = subprocess.run(
        [java_exe(), "-cp", "src", "SubCSA", str(height), "."],
        cwd=treepir_dir,
        check=True,
        text=True,
        capture_output=True,
    )
    stdout = proc.stdout
    match_c = re.search(r"c = \[([^\]]+)\]", stdout)
    match_time = re.search(r"Execution time in microseconds: (\d+)", stdout)
    if not match_c or not match_time:
        raise RuntimeError(f"Could not parse TreePIR output for h={height}:\n{stdout}")

    color_sizes = [int(x.strip()) for x in match_c.group(1).split(",")]
    perfect_records = (2 ** (height + 1)) - 2
    return {
        "height": height,
        "treepir_records": perfect_records,
        "treepir_width": height,
        "treepir_max_bucket": max(color_sizes),
        "treepir_index_us": int(match_time.group(1)),
    }


def load_direct_results(path: Path, sparsity: str) -> dict[int, dict[str, float]]:
    by_height: dict[int, dict[str, float]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["sparsity"] != sparsity:
                continue
            h = int(row["height"])
            by_height[h] = {
                "occupied": float(row["occupied"]),
                "active_nodes": float(row["active"]),
                "direct_width": float(row["m"]),
                "direct_max_bucket": float(row["profile_max"]),
                "direct_gap": float(row["profile_gap"]),
            }
    return by_height


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official TreePIR indexing as a perfectized SMT baseline.")
    parser.add_argument("--treepir-root", type=Path, default=TREEPIR_ROOT)
    parser.add_argument("--direct-results", type=Path, default=DIRECT_RESULTS)
    parser.add_argument("--output", type=Path, default=OUT_CSV)
    parser.add_argument("--note", type=Path, default=OUT_NOTE)
    parser.add_argument("--heights", default=",".join(str(height) for height in HEIGHTS))
    parser.add_argument("--sparsity", default=SPARSITY)
    parser.add_argument("--target-leaf", type=int, default=TARGET_LEAF)
    args = parser.parse_args()

    treepir_dir = args.treepir_root / "TreePIR-Indexing"
    direct = load_direct_results(args.direct_results, args.sparsity)
    rows: list[dict[str, float | int | str]] = []
    for h in parse_int_list(args.heights):
        if h not in direct:
            raise SystemExit(f"height {h} with sparsity {args.sparsity} not found in {args.direct_results}")
        official = run_official_indexing(treepir_dir=treepir_dir, height=h, target_leaf=args.target_leaf)
        ours = direct[h]
        rows.append(
            {
                "height": h,
                "sparsity": args.sparsity,
                "occupied": round(ours["occupied"], 3),
                "direct_active_nodes": round(ours["active_nodes"], 3),
                "treepir_records": official["treepir_records"],
                "record_reduction_x": official["treepir_records"] / ours["active_nodes"],
                "treepir_width": official["treepir_width"],
                "direct_width_m": ours["direct_width"],
                "width_reduction_pct": (1 - ours["direct_width"] / official["treepir_width"]) * 100,
                "treepir_max_bucket": official["treepir_max_bucket"],
                "direct_max_bucket": ours["direct_max_bucket"],
                "max_bucket_reduction_x": official["treepir_max_bucket"] / ours["direct_max_bucket"],
                "direct_gap": ours["direct_gap"],
                "official_treepir_index_us": official["treepir_index_us"],
            }
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Official TreePIR perfectized baseline",
        "",
        "We downloaded the official TreePIR artifact from `PIR-PIXR/TreePIR` and ran",
        "`TreePIR-Indexing/src/SubCSA` with a portable JRE. The artifact accepts only",
        "a tree height `h` and a leaf index, so this experiment represents the natural",
        "baseline where an SMT is padded into a perfect binary tree before applying",
        "TreePIR's coloring and fast indexing.",
        "",
        "| h | occupied | active nodes | TreePIR records | record reduction | width h -> m | max bucket reduction | official indexing |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {height} | {occupied:.0f} | {direct_active_nodes:.0f} | {treepir_records:,} | "
            "{record_reduction_x:.1f}x | {treepir_width} -> {direct_width_m:.2f} "
            "({width_reduction_pct:.1f}%) | {max_bucket_reduction_x:.1f}x | "
            "{official_treepir_index_us:.0f} us |".format(**row)
        )
    lines.extend(
        [
            "",
            "Interpretation: TreePIR can be run after perfectizing the SMT, but the",
            "official code's database sizes and color sequence are functions of the",
            "complete tree size `2^(h+1)-2`. Our direct SMT organization keeps only",
            "active proof-bearing nodes and therefore reduces records, width, and largest",
            "color subdatabase on the same fixed-height SMT snapshots.",
        ]
    )
    args.note.parent.mkdir(parents=True, exist_ok=True)
    args.note.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.output)
    print(args.note)


if __name__ == "__main__":
    main()
