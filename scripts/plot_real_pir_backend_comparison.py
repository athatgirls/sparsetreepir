#!/usr/bin/env python3
"""Plot executable PIR backend results for SparseTreePIR.

This figure intentionally excludes analytical/surrogate backends.  It only
uses results produced by concrete backend runners:

* SimplePIR full API bridge over exported SMT layouts.
* PIANO Go runner over the same backend-facing bucket profiles.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SIMPLEPIR_CSV = ROOT / "examples" / "real_smt_final_suite_simplepir.csv"
PIANO_CSV = ROOT / "examples" / "piano_wsl_backend_results.csv"
OUT_CSV = ROOT / "examples" / "real_pir_backend_comparison_summary.csv"
OUT_PNG = ROOT / "figures" / "real_pir_backend_comparison.png"
OUT_PDF = ROOT / "figures" / "real_pir_backend_comparison.pdf"
OUT_NOTE = ROOT / "notes" / "real_pir_backend_comparison_note.md"


@dataclass(frozen=True)
class Pair:
    backend: str
    dataset: str
    height: int
    pbc_online_kb: float
    ours_online_kb: float
    pbc_query_ms: float
    ours_query_ms: float
    pbc_setup_ms: float
    ours_setup_ms: float
    pbc_width: int
    ours_width: int

    @property
    def online_reduction(self) -> float:
        return 1.0 - self.ours_online_kb / self.pbc_online_kb

    @property
    def query_reduction(self) -> float:
        return 1.0 - self.ours_query_ms / self.pbc_query_ms

    @property
    def setup_reduction(self) -> float:
        return 1.0 - self.ours_setup_ms / self.pbc_setup_ms

    @property
    def width_reduction(self) -> float:
        return 1.0 - self.ours_width / self.pbc_width


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def make_pairs(
    backend: str,
    rows: Iterable[Dict[str, str]],
    pbc_scheme: str,
    ours_scheme: str,
) -> List[Pair]:
    grouped: Dict[Tuple[str, int], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in rows:
        grouped[(row["dataset"], int(row["height"]))][row["scheme"]] = row

    pairs: List[Pair] = []
    for (dataset, height), schemes in sorted(grouped.items()):
        if pbc_scheme not in schemes or ours_scheme not in schemes:
            continue
        pbc = schemes[pbc_scheme]
        ours = schemes[ours_scheme]
        pairs.append(
            Pair(
                backend=backend,
                dataset=dataset,
                height=height,
                pbc_online_kb=float(pbc["online_total_kb"]),
                ours_online_kb=float(ours["online_total_kb"]),
                pbc_query_ms=float(pbc["client_query_ms"]),
                ours_query_ms=float(ours["client_query_ms"]),
                pbc_setup_ms=float(pbc["setup_ms"]),
                ours_setup_ms=float(ours["setup_ms"]),
                pbc_width=int(float(pbc["width"])),
                ours_width=int(float(ours["width"])),
            )
        )
    return pairs


def write_summary(pairs: List[Pair]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for backend in sorted({p.backend for p in pairs}):
        sub = [p for p in pairs if p.backend == backend]
        rows.append(
            {
                "backend": backend,
                "workloads": len(sub),
                "avg_pbc_online_kb": mean(p.pbc_online_kb for p in sub),
                "avg_ours_online_kb": mean(p.ours_online_kb for p in sub),
                "avg_online_reduction_pct": 100.0 * mean(p.online_reduction for p in sub),
                "avg_pbc_query_ms": mean(p.pbc_query_ms for p in sub),
                "avg_ours_query_ms": mean(p.ours_query_ms for p in sub),
                "avg_query_reduction_pct": 100.0 * mean(p.query_reduction for p in sub),
                "avg_pbc_setup_ms": mean(p.pbc_setup_ms for p in sub),
                "avg_ours_setup_ms": mean(p.ours_setup_ms for p in sub),
                "avg_setup_reduction_pct": 100.0 * mean(p.setup_reduction for p in sub),
                "avg_width_reduction_pct": 100.0 * mean(p.width_reduction for p in sub),
            }
        )
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def pct(values: Iterable[float]) -> List[float]:
    return [100.0 * value for value in values]


def plot(pairs: List[Pair], summary_rows: List[Dict[str, object]]) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "legend.fontsize": 8,
            "figure.dpi": 180,
        }
    )

    backends = [str(row["backend"]) for row in summary_rows]
    pbc_online = [float(row["avg_pbc_online_kb"]) for row in summary_rows]
    ours_online = [float(row["avg_ours_online_kb"]) for row in summary_rows]
    pbc_query = [float(row["avg_pbc_query_ms"]) for row in summary_rows]
    ours_query = [float(row["avg_ours_query_ms"]) for row in summary_rows]

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65), constrained_layout=True)

    colors = {
        "pbc": "#c76f33",
        "ours": "#2f6fb0",
        "simplepir": "#6a8f2a",
        "piano": "#8a5fbf",
    }
    x = np.arange(len(backends))
    width = 0.34

    ax = axes[0]
    ax.bar(x - width / 2, pbc_online, width, label="PBC-SMT", color=colors["pbc"], edgecolor="#3c2a1d")
    ax.bar(x + width / 2, ours_online, width, label="SparseTreePIR", color=colors["ours"], edgecolor="#17375f")
    ax.set_title("(a) Online traffic")
    ax.set_ylabel("KB per proof")
    ax.set_xticks(x)
    ax.set_xticklabels(["SimplePIR", "PIANO"])
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(0, max(pbc_online + ours_online) * 1.28)
    for idx, row in enumerate(summary_rows):
        red = float(row["avg_online_reduction_pct"])
        ax.text(idx, max(pbc_online[idx], ours_online[idx]) * 1.07, f"{red:.1f}%", ha="center", va="bottom", fontsize=8)
    ax.legend(frameon=False, loc="upper left")

    ax = axes[1]
    offsets = {"SimplePIR-full-API": -0.08, "PIANO-local-runner": 0.08}
    markers = {"SimplePIR-full-API": "o", "PIANO-local-runner": "s"}
    backend_label = {"SimplePIR-full-API": "SimplePIR", "PIANO-local-runner": "PIANO"}
    for backend in backends:
        sub = [p for p in pairs if p.backend == backend]
        bx = backends.index(backend)
        jitter = np.linspace(-0.055, 0.055, len(sub)) if len(sub) > 1 else [0.0]
        y = pct(p.online_reduction for p in sub)
        ax.scatter(
            np.full(len(sub), bx + offsets.get(backend, 0.0)) + jitter,
            y,
            label=backend_label.get(backend, backend),
            marker=markers.get(backend, "o"),
            color=colors["simplepir"] if backend == "SimplePIR-full-API" else colors["piano"],
            s=34,
            edgecolor="white",
            linewidth=0.6,
        )
        ax.hlines(mean(y), bx - 0.25, bx + 0.25, colors="#1f1f1f", linewidth=1.4)
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set_title("(b) Per-workload traffic gain")
    ax.set_ylabel("reduction vs PBC-SMT (%)")
    ax.set_xticks(x)
    ax.set_xticklabels(["SimplePIR", "PIANO"])
    ax.set_ylim(35, 60)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[2]
    ax.bar(x - width / 2, pbc_query, width, label="PBC-SMT", color=colors["pbc"], edgecolor="#3c2a1d")
    ax.bar(x + width / 2, ours_query, width, label="SparseTreePIR", color=colors["ours"], edgecolor="#17375f")
    ax.set_title("(c) Client query generation")
    ax.set_ylabel("ms per batch")
    ax.set_xticks(x)
    ax.set_xticklabels(["SimplePIR", "PIANO"])
    ax.grid(axis="y", alpha=0.25)
    ax.set_ylim(0, max(pbc_query + ours_query) * 1.28)
    for idx, row in enumerate(summary_rows):
        red = float(row["avg_query_reduction_pct"])
        ax.text(idx, max(pbc_query[idx], ours_query[idx]) * 1.07, f"{red:.1f}%", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Executable PIR backends on real SMT workloads", fontsize=12, fontweight="bold")
    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, bbox_inches="tight")
    fig.savefig(OUT_PDF, bbox_inches="tight")
    plt.close(fig)


def write_note(summary_rows: List[Dict[str, object]]) -> None:
    lines = [
        "# Real executable PIR backend comparison",
        "",
        "This note summarizes only concrete backend runs: SimplePIR full API and the PIANO Go runner. "
        "It intentionally excludes XOR, LWE cost-model, and TreePIR-format smoke-test data.",
        "",
        "| Backend | Workloads | Online KB reduction | Query-generation reduction | Setup reduction | Width reduction |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            "| {backend} | {workloads} | {online:.1f}% | {query:.1f}% | {setup:.1f}% | {width:.1f}% |".format(
                backend=row["backend"],
                workloads=int(row["workloads"]),
                online=float(row["avg_online_reduction_pct"]),
                query=float(row["avg_query_reduction_pct"]),
                setup=float(row["avg_setup_reduction_pct"]),
                width=float(row["avg_width_reduction_pct"]),
            )
        )
    lines.extend(
        [
            "",
            "Interpretation: SparseTreePIR does not change the PIR primitive. It changes the backend-facing "
            "database shape: fewer batch slots than PBC-SMT and smaller active color stores. The plotted "
            "numbers are therefore an executable sanity check that this resource shape translates to real "
            "PIR API/runner gains on the current workloads.",
            "",
            f"Figure: `{OUT_PNG.relative_to(ROOT)}`",
            f"Summary CSV: `{OUT_CSV.relative_to(ROOT)}`",
        ]
    )
    OUT_NOTE.parent.mkdir(parents=True, exist_ok=True)
    OUT_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    simplepir_pairs = make_pairs(
        "SimplePIR-full-API",
        read_rows(SIMPLEPIR_CSV),
        pbc_scheme="pbc_smt_active",
        ours_scheme="sparsetreepir_activebalance",
    )
    piano_pairs = make_pairs(
        "PIANO-local-runner",
        read_rows(PIANO_CSV),
        pbc_scheme="PBC-SMT",
        ours_scheme="SparseTreePIR",
    )
    pairs = simplepir_pairs + piano_pairs
    if not pairs:
        raise SystemExit("No paired backend rows found.")
    summary_rows = write_summary(pairs)
    plot(pairs, summary_rows)
    write_note(summary_rows)
    print(f"Wrote {OUT_CSV}")
    print(f"Wrote {OUT_PNG}")
    print(f"Wrote {OUT_PDF}")
    print(f"Wrote {OUT_NOTE}")


if __name__ == "__main__":
    main()
