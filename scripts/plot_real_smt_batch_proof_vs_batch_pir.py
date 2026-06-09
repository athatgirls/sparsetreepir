from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "examples" / "real_smt_batch_proof_vs_batch_pir_results.csv"
OUT_PDF = ROOT / "figures" / "real_smt_batch_proof_vs_batch_pir_figure.pdf"
OUT_PNG = ROOT / "figures" / "real_smt_batch_proof_vs_batch_pir_figure.png"


def read_rows():
    with IN_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def pick(rows, dataset: str, height: int, batch: int):
    selected = [
        row
        for row in rows
        if row["dataset"] == dataset
        and int(row["height"]) == height
        and int(row["target_batch"]) == batch
    ]
    if not selected:
        raise SystemExit(f"Setting not found: dataset={dataset}, h={height}, B={batch}")
    return {row["scheme"]: row for row in selected}


def main() -> None:
    dataset = "Polygon-zkEVM-broad"
    height = 128
    batch = 128
    rows = pick(read_rows(), dataset=dataset, height=height, batch=batch)

    schemes = ["perfectized_treepir", "sparsetreepir_batch_pir"]
    labels = ["Perfectized\nTreePIR", "SparseTreePIR\nbatch PIR"]
    colors = ["#c6ccd6", "#2f80d0"]
    width = [float(rows[scheme]["width"]) for scheme in schemes]
    # Use floats for plotting; 2^128 is representable as a floating point value
    # and the label remains symbolic in the chart.
    max_bucket = [float(rows[scheme]["max_bucket"]) for scheme in schemes]

    ordinary_kb = float(rows["ordinary_smt_batch_serving"]["ordinary_batch_dedup_bytes"]) / 1024.0
    active_n = int(float(rows["sparsetreepir_batch_pir"]["active_records"]))
    active_width = int(float(rows["sparsetreepir_batch_pir"]["active_width_m"]))
    sparse_bucket = int(float(rows["sparsetreepir_batch_pir"]["max_bucket"]))

    fig, axes = plt.subplots(1, 3, figsize=(7.25, 2.45))
    fig.suptitle(
        "Real Polygon zkEVM workload: ordinary SMT serving vs private proof retrieval",
        fontsize=10.0,
        fontweight="bold",
        y=1.02,
    )

    axes[0].bar(["Known-target\nSMT batch"], [ordinary_kb], color="#79b878", edgecolor="#205c2c")
    axes[0].set_title("Non-private payload\n(B=128)", fontsize=8)
    axes[0].set_ylabel("KB returned")
    axes[0].text(0, ordinary_kb * 1.05, f"{ordinary_kb:.1f} KB", ha="center", fontsize=7)
    axes[0].set_ylim(0, ordinary_kb * 1.35)

    axes[1].bar(labels, width, color=colors, edgecolor="#344054")
    axes[1].set_title("Private fixed width", fontsize=8)
    axes[1].set_ylabel("# PIR slots")
    for idx, value in enumerate(width):
        axes[1].text(idx, value + 4.0, f"{int(value)}", ha="center", fontsize=7)
    axes[1].set_ylim(0, max(width) * 1.25)

    axes[2].bar(labels, max_bucket, color=colors, edgecolor="#344054")
    axes[2].set_yscale("log")
    axes[2].set_title("Largest searched DB", fontsize=8)
    axes[2].set_ylabel("records (log)")
    bucket_labels = [rf"$\approx 2^{{{float(rows[schemes[0]]['max_bucket_log2']):.0f}}}$", f"{sparse_bucket:,}"]
    for idx, (value, label) in enumerate(zip(max_bucket, bucket_labels)):
        axes[2].text(idx, value * 1.4, label, ha="center", fontsize=7)

    for ax in axes:
        ax.grid(axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", labelsize=7)
        ax.tick_params(axis="y", labelsize=7)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.text(
        0.5,
        -0.035,
        f"{dataset}, h={height}, {active_n:,} active proof records, active width m={active_width}. "
        "Ordinary SMT serving is the non-private lower bound; TreePIR requires perfectizing the SMT first.",
        ha="center",
        fontsize=7.2,
        color="#475467",
    )
    fig.tight_layout()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight")
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
