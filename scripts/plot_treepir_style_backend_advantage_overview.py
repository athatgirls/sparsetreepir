from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path.cwd()
EXAMPLES = ROOT / "examples"
FIGURES = ROOT / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def pct(x: float) -> float:
    return 100.0 * x


def summarize_real_backend() -> list[dict[str, float | str]]:
    rows = read_csv(EXAMPLES / "real_smt_multi_pir_pbc_battle_summary.csv")
    piano_path = EXAMPLES / "piano_wsl_backend_summary.csv"
    if piano_path.exists():
        rows.extend(read_csv(piano_path))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["backend"]].append(row)

    out: list[dict[str, float | str]] = []
    for backend, backend_rows in sorted(grouped.items()):
        out.append(
            {
                "backend": backend,
                "datasets": float(len(backend_rows)),
                "online_reduction_pct": pct(mean(float(r["online_reduction"]) for r in backend_rows)),
                "query_reduction_pct": pct(mean(float(r["query_reduction"]) for r in backend_rows)),
                "parallel_reduction_pct": pct(mean(float(r["parallel_reduction"]) for r in backend_rows)),
            }
        )
    return out


def summarize_resource_shape() -> dict[str, float]:
    rows = read_csv(EXAMPLES / "real_smt_final_suite_layouts.csv")
    pairs: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        if row["height"] != "128":
            continue
        if row["scheme"] in {"pbc_smt_active", "flat_active_pir", "sparsetreepir_activebalance"}:
            key = (row["dataset"], row["height"], row["key_mode"])
            pairs[key][row["scheme"]] = row

    pbc_storage_reductions = []
    pbc_width_reductions = []
    pbc_bucket_reductions = []
    flat_bucket_reductions = []

    for schemes in pairs.values():
        if "sparsetreepir_activebalance" not in schemes:
            continue
        ours = schemes["sparsetreepir_activebalance"]
        if "pbc_smt_active" in schemes:
            pbc = schemes["pbc_smt_active"]
            pbc_storage_reductions.append(1.0 - float(ours["stored_records"]) / float(pbc["stored_records"]))
            pbc_width_reductions.append(1.0 - float(ours["width"]) / float(pbc["width"]))
            pbc_bucket_reductions.append(1.0 - float(ours["max_bucket"]) / float(pbc["max_bucket"]))
        if "flat_active_pir" in schemes:
            flat = schemes["flat_active_pir"]
            flat_bucket_reductions.append(1.0 - float(ours["max_bucket"]) / float(flat["max_bucket"]))

    return {
        "pbc_storage_reduction_pct": pct(mean(pbc_storage_reductions)),
        "pbc_width_reduction_pct": pct(mean(pbc_width_reductions)),
        "pbc_bucket_reduction_pct": pct(mean(pbc_bucket_reductions)),
        "flat_bucket_reduction_pct": pct(mean(flat_bucket_reductions)),
    }


def summarize_treepir_artifacts() -> dict[str, float]:
    vbpir_rows = {r["artifact"]: r for r in read_csv(EXAMPLES / "treepir_vbpir_artifact_summary.csv")}
    pbc = vbpir_rows["VBPIR_PBC"]
    treepir = vbpir_rows["VBPIR_TreePIR"]
    pbc_art = read_csv(EXAMPLES / "treepir_pbc_artifact_results.csv")
    return {
        "vbpir_width_reduction_pct": pct(1.0 - float(treepir["batch_size"]) / float(pbc["batch_size"])),
        "vbpir_bucket_reduction_pct": pct(1.0 - float(treepir["max_bucket_size"]) / float(pbc["max_bucket_size"])),
        "vbpir_query_time_reduction_pct": pct(1.0 - float(treepir["query_gen_us"]) / float(pbc["query_gen_us"])),
        "vbpir_answer_time_reduction_pct": pct(1.0 - float(treepir["response_gen_us"]) / float(pbc["response_gen_us"])),
        "pbc_map_db_ratio": mean(float(r["map_to_database_ratio"]) for r in pbc_art),
    }


def write_summary(
    real_backend: list[dict[str, float | str]],
    resource: dict[str, float],
    artifacts: dict[str, float],
) -> None:
    path = EXAMPLES / "treepir_style_backend_advantage_overview.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "metric", "value"])
        for row in real_backend:
            backend = str(row["backend"])
            writer.writerow([backend, "datasets", row["datasets"]])
            writer.writerow([backend, "avg_online_reduction_pct", row["online_reduction_pct"]])
            writer.writerow([backend, "avg_query_reduction_pct", row["query_reduction_pct"]])
            writer.writerow([backend, "avg_parallel_reduction_pct", row["parallel_reduction_pct"]])
        for key, value in resource.items():
            writer.writerow(["real_smt_resource_shape", key, value])
        for key, value in artifacts.items():
            writer.writerow(["treepir_artifact", key, value])
    print(f"summary={path}")


def plot(
    real_backend: list[dict[str, float | str]],
    resource: dict[str, float],
    artifacts: dict[str, float],
) -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "legend.fontsize": 7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )

    backend_order = [
        "2server-XOR-PIR-model",
        "LWE-PIR-prototype-d64",
        "SimplePIR-full-api",
        "PIANO-local-runner",
    ]
    backend_labels = {
        "2server-XOR-PIR-model": "2-server\nXOR",
        "LWE-PIR-prototype-d64": "LWE\nproto.",
        "SimplePIR-full-api": "SimplePIR\nAPI",
        "PIANO-local-runner": "PIANO\nrunner",
    }
    by_backend = {str(r["backend"]): r for r in real_backend}

    fig = plt.figure(figsize=(7.05, 4.65))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 1.0], width_ratios=[1.35, 1.0])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    x = np.arange(len(backend_order))
    width = 0.34
    online_vals = [float(by_backend[b]["online_reduction_pct"]) for b in backend_order]
    query_vals = [float(by_backend[b]["query_reduction_pct"]) for b in backend_order]
    ax1.bar(x - width / 2, online_vals, width, label="Online KB", color="#2f7ebc", edgecolor="#222", linewidth=0.4)
    ax1.bar(x + width / 2, query_vals, width, label="Query gen.", color="#f28e2b", edgecolor="#222", linewidth=0.4)
    ax1.set_title("A. SparseTreePIR vs PBC-active on real SMT workloads")
    ax1.set_ylabel("Average reduction (%)")
    ax1.set_xticks(x)
    ax1.set_xticklabels([backend_labels[b] for b in backend_order])
    ax1.set_ylim(0, 75)
    ax1.grid(axis="y", color="#dddddd", linewidth=0.5)
    ax1.legend(frameon=False, loc="upper left", ncol=2)
    for xpos, val in zip(x - width / 2, online_vals):
        ax1.text(xpos, val + 1.2, f"{val:.0f}", ha="center", va="bottom", fontsize=6.5)
    for xpos, val in zip(x + width / 2, query_vals):
        ax1.text(xpos, val + 1.2, f"{val:.0f}", ha="center", va="bottom", fontsize=6.5)

    res_names = ["Storage\nvs PBC", "Width\nvs PBC", "Max bucket\nvs PBC", "Max bucket\nvs Flat"]
    res_vals = [
        resource["pbc_storage_reduction_pct"],
        resource["pbc_width_reduction_pct"],
        resource["pbc_bucket_reduction_pct"],
        resource["flat_bucket_reduction_pct"],
    ]
    ax2.bar(np.arange(len(res_vals)), res_vals, color=["#59a14f", "#4e79a7", "#e15759", "#b07aa1"], edgecolor="#222", linewidth=0.4)
    ax2.set_title("B. Real-SMT resource shape")
    ax2.set_ylabel("Average reduction (%)")
    ax2.set_xticks(np.arange(len(res_vals)))
    ax2.set_xticklabels(res_names)
    ax2.set_ylim(0, 100)
    ax2.grid(axis="y", color="#dddddd", linewidth=0.5)
    for i, val in enumerate(res_vals):
        ax2.text(i, val + 1.5, f"{val:.0f}", ha="center", va="bottom", fontsize=6.5)

    art_names = ["VBPIR\nwidth", "VBPIR\nmax bucket", "VBPIR\nanswer time"]
    art_vals = [
        artifacts["vbpir_width_reduction_pct"],
        artifacts["vbpir_bucket_reduction_pct"],
        artifacts["vbpir_answer_time_reduction_pct"],
    ]
    ax3.bar(np.arange(len(art_vals)), art_vals, color=["#4e79a7", "#e15759", "#76b7b2"], edgecolor="#222", linewidth=0.4)
    ax3.axhline(0, color="#444", linewidth=0.6)
    ax3.set_title("C. TreePIR artifact check: VBPIR TreePIR route vs VBPIR PBC route")
    ax3.set_ylabel("Reduction (%)")
    ax3.set_xticks(np.arange(len(art_vals)))
    ax3.set_xticklabels(art_names)
    ax3.set_ylim(-8, 62)
    ax3.grid(axis="y", color="#dddddd", linewidth=0.5)
    for i, val in enumerate(art_vals):
        ax3.text(i, val + (1.5 if val >= 0 else -3.5), f"{val:.1f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=6.5)
    ax3.text(
        0.02,
        0.88,
        "TreePIR-format smoke test;\ncommunication equal in this artifact setting.",
        transform=ax3.transAxes,
        fontsize=6.4,
        color="#333333",
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#dddddd", "boxstyle": "round,pad=0.25", "alpha": 0.88},
    )

    map_ratio = artifacts["pbc_map_db_ratio"]
    ax4.bar([0], [map_ratio], width=0.48, color="#edc948", edgecolor="#222", linewidth=0.4)
    ax4.axhline(1.0, color="#444", linestyle="--", linewidth=0.6)
    ax4.set_title("D. TreePIR PBC artifact indexing state")
    ax4.set_ylabel("Map size / raw DB size")
    ax4.set_xticks([0])
    ax4.set_xticklabels(["PBC map"])
    ax4.set_ylim(0, max(5.2, map_ratio + 0.6))
    ax4.grid(axis="y", color="#dddddd", linewidth=0.5)
    ax4.text(0, map_ratio + 0.15, f"{map_ratio:.2f}x", ha="center", va="bottom", fontsize=7)
    ax4.text(
        0.5,
        0.08,
        "h=10/16/20\nofficial artifact runs",
        transform=ax4.transAxes,
        ha="center",
        fontsize=6.5,
        color="#333333",
    )

    for ax in [ax1, ax2, ax3, ax4]:
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.suptitle("TreePIR-style resource/backend evaluation", y=0.995, fontsize=9.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.955], pad=0.65, h_pad=1.05, w_pad=0.9)

    FIGURES.mkdir(parents=True, exist_ok=True)
    pdf = FIGURES / "treepir_style_backend_advantage_overview.pdf"
    png = FIGURES / "treepir_style_backend_advantage_overview.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    print(f"pdf={pdf}")
    print(f"png={png}")


def main() -> None:
    real_backend = summarize_real_backend()
    resource = summarize_resource_shape()
    artifacts = summarize_treepir_artifacts()
    write_summary(real_backend, resource, artifacts)
    plot(real_backend, resource, artifacts)


if __name__ == "__main__":
    main()
