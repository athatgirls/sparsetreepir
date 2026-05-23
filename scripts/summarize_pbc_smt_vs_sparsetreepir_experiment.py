from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PBC = "pbc_active"
OURS = "profile_balanced"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize the direct PBC-on-SMT-proof-records baseline against "
            "SparseTreePIR. The input CSVs are existing experiment outputs; this "
            "script only filters, renames, and computes reduction metrics."
        )
    )
    parser.add_argument(
        "--resource-csv",
        type=Path,
        default=Path("examples/treepir_style_comparison_results.csv"),
        help="Resource-model comparison CSV containing pbc_active and profile_balanced.",
    )
    parser.add_argument(
        "--backend-csv",
        type=Path,
        default=Path("examples/simplepir_full_backend_results.csv"),
        help="SimplePIR backend CSV containing pbc_active and profile_balanced.",
    )
    parser.add_argument(
        "--resource-out",
        type=Path,
        default=Path("examples/pbc_smt_vs_sparsetreepir_resource_summary.csv"),
    )
    parser.add_argument(
        "--backend-out",
        type=Path,
        default=Path("examples/pbc_smt_vs_sparsetreepir_backend_summary.csv"),
    )
    parser.add_argument(
        "--note",
        type=Path,
        default=Path("notes/pbc_smt_vs_sparsetreepir_experiment_note.md"),
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("figures/pbc_smt_vs_sparsetreepir_experiment_figure.pdf"),
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=Path("figures/pbc_smt_vs_sparsetreepir_experiment_figure.png"),
    )
    return parser.parse_args()


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def num(row: Dict[str, str], key: str) -> float:
    raw = row.get(key, "")
    return float(raw) if raw != "" else 0.0


def pct_reduction(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def fmt(value: float, digits: int = 1) -> str:
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value)):,}"
    return f"{value:,.{digits}f}"


def grouped_by_instance(
    rows: Iterable[Dict[str, str]],
) -> Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]]:
    grouped: Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]] = {}
    for row in rows:
        if row.get("scheme") not in {PBC, OURS}:
            continue
        key = (
            int(float(row["height"])),
            float(row["sparsity"]),
            int(float(row.get("seed", "0"))),
        )
        grouped.setdefault(key, {})[row["scheme"]] = row
    return grouped


def build_resource_summary(rows: List[Dict[str, str]]) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for (height, sparsity, seed), schemes in sorted(grouped_by_instance(rows).items()):
        if PBC not in schemes or OURS not in schemes:
            continue
        pbc = schemes[PBC]
        ours = schemes[OURS]
        out.append(
            {
                "height": height,
                "empty_pct": sparsity * 100.0,
                "seed": seed,
                "active_nodes": num(ours, "active_nodes"),
                "active_width_m": num(ours, "exact_width"),
                "pbc_width": num(pbc, "width"),
                "ours_width": num(ours, "width"),
                "width_reduction_pct": pct_reduction(num(ours, "width"), num(pbc, "width")),
                "pbc_stored_records": num(pbc, "stored_records"),
                "ours_stored_records": num(ours, "stored_records"),
                "storage_reduction_pct": pct_reduction(
                    num(ours, "stored_records"), num(pbc, "stored_records")
                ),
                "pbc_max_bucket": num(pbc, "max_bucket"),
                "ours_max_bucket": num(ours, "max_bucket"),
                "max_bucket_reduction_pct": pct_reduction(
                    num(ours, "max_bucket"), num(pbc, "max_bucket")
                ),
            }
        )
    return out


def build_backend_summary(rows: List[Dict[str, str]]) -> List[Dict[str, float]]:
    out: List[Dict[str, float]] = []
    for (height, sparsity, seed), schemes in sorted(grouped_by_instance(rows).items()):
        if PBC not in schemes or OURS not in schemes:
            continue
        pbc = schemes[PBC]
        ours = schemes[OURS]
        out.append(
            {
                "height": height,
                "empty_pct": sparsity * 100.0,
                "seed": seed,
                "active_nodes": num(ours, "active_nodes"),
                "active_width_m": num(ours, "exact_width"),
                "pbc_width": num(pbc, "width"),
                "ours_width": num(ours, "width"),
                "pbc_online_kb": num(pbc, "online_total_kb"),
                "ours_online_kb": num(ours, "online_total_kb"),
                "online_reduction_pct": pct_reduction(
                    num(ours, "online_total_kb"), num(pbc, "online_total_kb")
                ),
                "pbc_setup_ms": num(pbc, "setup_ms"),
                "ours_setup_ms": num(ours, "setup_ms"),
                "setup_reduction_pct": pct_reduction(num(ours, "setup_ms"), num(pbc, "setup_ms")),
                "pbc_query_ms": num(pbc, "client_query_ms"),
                "ours_query_ms": num(ours, "client_query_ms"),
                "query_reduction_pct": pct_reduction(
                    num(ours, "client_query_ms"), num(pbc, "client_query_ms")
                ),
                "pbc_answer_ms": num(pbc, "server_parallel_ms"),
                "ours_answer_ms": num(ours, "server_parallel_ms"),
                "answer_reduction_pct": pct_reduction(
                    num(ours, "server_parallel_ms"), num(pbc, "server_parallel_ms")
                ),
                "pbc_recover_ms": num(pbc, "client_decode_ms"),
                "ours_recover_ms": num(ours, "client_decode_ms"),
                "recover_reduction_pct": pct_reduction(
                    num(ours, "client_decode_ms"), num(pbc, "client_decode_ms")
                ),
            }
        )
    return out


def write_csv(path: Path, rows: List[Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError("no rows to write")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def mean_of(rows: List[Dict[str, float]], key: str) -> float:
    return mean(float(row[key]) for row in rows)


def write_note(path: Path, resource: List[Dict[str, float]], backend: List[Dict[str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# PBC-SMT vs SparseTreePIR experiment\n")
    lines.append(
        "This note isolates the experiment requested here: apply the generic "
        "probabilistic-batch-code route directly to SMT active proof records, "
        "then compare it with SparseTreePIR on the same SMT instances. We call "
        "this baseline **PBC-SMT**: it stores three replicated copies of each "
        "active proof record and uses about `1.5m` buckets, following the same "
        "resource-model foil used by TreePIR for generic batch retrieval. "
        "SparseTreePIR stores each active proof record once, uses active width "
        "`m`, and balances color stores with ActiveBalance.\n"
    )

    lines.append("## Resource-model results\n")
    lines.append(
        "| h | Empty | Active N | m | PBC-SMT width | Ours width | PBC-SMT stored | Ours stored | PBC-SMT max bucket | Ours max bucket |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in resource:
        lines.append(
            "| {h} | {empty:.3f}% | {active} | {m} | {pbc_w} | {ours_w} | {pbc_s} | {ours_s} | {pbc_b} | {ours_b} |".format(
                h=int(row["height"]),
                empty=row["empty_pct"],
                active=fmt(row["active_nodes"], 0),
                m=fmt(row["active_width_m"], 0),
                pbc_w=fmt(row["pbc_width"], 0),
                ours_w=fmt(row["ours_width"], 0),
                pbc_s=fmt(row["pbc_stored_records"], 0),
                ours_s=fmt(row["ours_stored_records"], 0),
                pbc_b=fmt(row["pbc_max_bucket"], 0),
                ours_b=fmt(row["ours_max_bucket"], 0),
            )
        )
    lines.append("")
    lines.append(
        "- Mean storage reduction: "
        f"{mean_of(resource, 'storage_reduction_pct'):.1f}%."
    )
    lines.append(
        "- Mean width reduction: "
        f"{mean_of(resource, 'width_reduction_pct'):.1f}%."
    )
    lines.append(
        "- Mean largest-bucket reduction: "
        f"{mean_of(resource, 'max_bucket_reduction_pct'):.1f}%."
    )

    lines.append("\n## SimplePIR backend results\n")
    lines.append(
        "| h | Empty | PBC-SMT KB | Ours KB | KB red. | PBC-SMT Query ms | Ours Query ms | PBC-SMT Answer ms | Ours Answer ms |"
    )
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in backend:
        lines.append(
            "| {h} | {empty:.3f}% | {pbc_kb:.2f} | {ours_kb:.2f} | {kb_red:.1f}% | {pbc_q:.2f} | {ours_q:.2f} | {pbc_a:.3f} | {ours_a:.3f} |".format(
                h=int(row["height"]),
                empty=row["empty_pct"],
                pbc_kb=row["pbc_online_kb"],
                ours_kb=row["ours_online_kb"],
                kb_red=row["online_reduction_pct"],
                pbc_q=row["pbc_query_ms"],
                ours_q=row["ours_query_ms"],
                pbc_a=row["pbc_answer_ms"],
                ours_a=row["ours_answer_ms"],
            )
        )
    lines.append("")
    lines.append(
        "- Mean online communication reduction: "
        f"{mean_of(backend, 'online_reduction_pct'):.1f}%."
    )
    lines.append(
        "- Mean client query-generation reduction: "
        f"{mean_of(backend, 'query_reduction_pct'):.1f}%."
    )
    lines.append(
        "- Mean server-answer bottleneck reduction: "
        f"{mean_of(backend, 'answer_reduction_pct'):.1f}%."
    )
    lines.append(
        "- Mean client recovery reduction: "
        f"{mean_of(backend, 'recover_reduction_pct'):.1f}%."
    )

    lines.append("\n## Interpretation\n")
    lines.append(
        "PBC-SMT is a reasonable generic-batch baseline once the SMT proof "
        "records have been identified: it treats the active sibling digests as "
        "an arbitrary batch-retrieval workload. The experiment shows why this "
        "still leaves structure on the table. Compared with PBC-SMT, "
        "SparseTreePIR removes the three-copy replication, lowers the fixed "
        "batch width from roughly `1.5m` to `m`, and cuts the largest searched "
        "bucket by about half. Under the same SimplePIR runner, those resource "
        "changes translate into about a half reduction in online bytes and a "
        "clear reduction in client-side query generation and answer bottleneck "
        "for the tested settings."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def plot_figure(path_pdf: Path, path_png: Path, resource: List[Dict[str, float]], backend: List[Dict[str, float]]) -> None:
    labels = [f"h={int(r['height'])}\n{r['empty_pct']:.3f}%" for r in resource]
    x = np.arange(len(labels))
    width = 0.36

    pbc_max = [r["pbc_max_bucket"] for r in resource]
    ours_max = [r["ours_max_bucket"] for r in resource]
    pbc_kb = [r["pbc_online_kb"] for r in backend]
    ours_kb = [r["ours_online_kb"] for r in backend]

    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7,
            "xtick.labelsize": 6,
            "ytick.labelsize": 6,
            "legend.fontsize": 6.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(6.95, 2.35))
    pbc_color = "#8d6bb3"
    ours_color = "#2f8477"
    specs = [
        (axes[0], pbc_max, ours_max, "Largest searched bucket"),
        (axes[1], pbc_kb, ours_kb, "SimplePIR online KB"),
    ]
    for ax, pbc_values, ours_values, title in specs:
        ax.bar(
            x - width / 2,
            pbc_values,
            width,
            label="PBC-SMT",
            color=pbc_color,
            edgecolor="#222222",
            linewidth=0.35,
        )
        ax.bar(
            x + width / 2,
            ours_values,
            width,
            label="SparseTreePIR",
            color=ours_color,
            edgecolor="#222222",
            linewidth=0.35,
        )
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=0)
        ax.set_yscale("log")
        ax.grid(axis="y", which="major", color="#d9d9d9", linewidth=0.5)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
    axes[0].set_ylabel("log scale")
    axes[0].legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.4, w_pad=1.2)

    path_pdf.parent.mkdir(parents=True, exist_ok=True)
    path_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path_pdf, bbox_inches="tight")
    fig.savefig(path_png, bbox_inches="tight", dpi=300)


def main() -> None:
    args = parse_args()
    resource = build_resource_summary(read_rows(args.resource_csv))
    backend = build_backend_summary(read_rows(args.backend_csv))
    write_csv(args.resource_out, resource)
    write_csv(args.backend_out, backend)
    write_note(args.note, resource, backend)
    plot_figure(args.pdf, args.png, resource, backend)
    print(f"resource_csv={args.resource_out} rows={len(resource)}")
    print(f"backend_csv={args.backend_out} rows={len(backend)}")
    print(f"note={args.note}")
    print(f"pdf={args.pdf}")
    print(f"png={args.png}")


if __name__ == "__main__":
    main()
