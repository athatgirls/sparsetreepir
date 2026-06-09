from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "examples" / "smt_batch_proof_vs_batch_pir_results.csv"
OUT_PDF = ROOT / "figures" / "smt_batch_proof_vs_batch_pir_figure.pdf"
OUT_PNG = ROOT / "figures" / "smt_batch_proof_vs_batch_pir_figure.png"


def read_rows():
    with IN_CSV.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def pick_setting(rows):
    candidates = [
        row
        for row in rows
        if int(row["height"]) == 24
        and abs(float(row["empty_pct"]) - 99.95) < 1e-9
        and int(row["target_batch"]) == 32
    ]
    if not candidates:
        raise SystemExit("Expected h=24, empty=99.95, B=32 setting not found.")
    return {row["scheme"]: row for row in candidates}


def main():
    rows = pick_setting(read_rows())
    schemes = ["full_coordinate_level_pir", "pruned_level_pir_h", "sparsetreepir_batch_pir"]
    labels = ["Full-coordinate\nlevel PIR", "Pruned level\nPIR-h", "SparseTreePIR\nbatch PIR"]
    colors = ["#b8c0cc", "#f4a261", "#2f80d0"]

    width = [float(rows[s]["width"]) for s in schemes]
    max_bucket = [float(rows[s]["max_bucket"]) for s in schemes]

    plain_bytes = float(rows["ordinary_smt_batch_serving"]["ordinary_batch_dedup_bytes"])
    active_n = int(float(rows["sparsetreepir_batch_pir"]["active_records"]))
    m = int(float(rows["sparsetreepir_batch_pir"]["active_width_m"]))

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.35))
    fig.suptitle(
        "From ordinary SMT proof serving to target-private batch PIR",
        fontsize=10.5,
        fontweight="bold",
        y=1.03,
    )

    axes[0].bar(["Ordinary\nSMT batch"], [plain_bytes / 1024], color="#7dbb7d", edgecolor="#1f6b2a")
    axes[0].set_ylabel("KB returned")
    axes[0].set_title("Non-private payload\n(B=32)", fontsize=8)
    axes[0].text(0, plain_bytes / 1024 * 1.04, f"{plain_bytes/1024:.1f} KB", ha="center", fontsize=7)
    axes[0].set_ylim(0, max(1, plain_bytes / 1024 * 1.35))

    axes[1].bar(labels, width, color=colors, edgecolor="#344054")
    axes[1].set_title("Private batch width", fontsize=8)
    axes[1].set_ylabel("# PIR slots")
    for idx, val in enumerate(width):
        axes[1].text(idx, val + 0.45, f"{int(val)}", ha="center", fontsize=7)
    axes[1].set_ylim(0, max(width) * 1.25)

    axes[2].bar(labels, max_bucket, color=colors, edgecolor="#344054")
    axes[2].set_yscale("log")
    axes[2].set_title("Largest searched DB", fontsize=8)
    axes[2].set_ylabel("records (log)")
    for idx, val in enumerate(max_bucket):
        axes[2].text(idx, val * 1.20, f"{int(val):,}", ha="center", fontsize=7)

    for ax in axes:
        ax.grid(axis="y", color="#e5e7eb", linewidth=0.7)
        ax.tick_params(axis="x", labelsize=7)
        ax.tick_params(axis="y", labelsize=7)
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)

    fig.text(
        0.5,
        -0.02,
        f"h=24, 99.95% empty, active records N={active_n:,}, active width m={m}. "
        "Ordinary serving is the non-private lower bound; the PIR baselines add target privacy.",
        ha="center",
        fontsize=7.2,
        color="#475467",
    )
    fig.tight_layout()
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=220, bbox_inches="tight")
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
