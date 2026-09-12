"""Frozen structural-result presentation; new count-only holdout FF, no timers.

Run from repository root. Refuses to overwrite generated output by default.
For reproduction use --out pointing to a new directory.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUT = Path(__file__).resolve().parent
ALLOW_REFRESH = False
SOURCES = {
    "base_construction": "examples/tifs_sufficiency_20260910/construction/base_construction_results.json",
    "holdout_construction": "examples/tifs_sufficiency_20260910/construction/holdout_construction_results.json",
    "base_older_algorithm": "examples/tifs_remaining_gap_20260910/algorithm/small_shape_algorithm_results.json",
    "holdout_exact": "examples/tifs_remaining_gap_20260910/theory/expanded_exact_results.json",
    "frozen_summary": "examples/tifs_sufficiency_20260910/construction/summary.json",
    "first_fit_definition": "scripts/run_height_sparsity_profile_balance_experiment.py",
}
METHODS = ["First-fit", "AB", "AB + pair", "AB + 3", "AB + 3→4", "Exact OPT"]
FIELDS = {"AB": ("original_AB", "initial_colors"), "AB + pair": ("pair_union", "pair_colors"),
          "AB + 3": ("three_color", "three_colors"), "AB + 3→4": ("three_then_four", "final_colors")}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def shape_depth_loads(shape):
    counts = Counter()
    def visit(t, depth):
        counts[depth] += 1
        assert len(t) in (0, 2)
        for child in t:
            visit(child, depth + 1)
    assert len(shape) == 2
    for child in shape:
        visit(child, 1)
    return [counts[c] for c in range(1, max(counts) + 1)]


def record_depth_colors(records):
    by_id = {r["heap_node"]: r for r in records}
    assert len(by_id) == len(records)
    depths = {}
    def depth(v, seen=frozenset()):
        assert v not in seen
        if v not in depths:
            parent = by_id[v]["parent"]
            depths[v] = 1 if parent is None else 1 + depth(parent, seen | {v})
        return depths[v]
    return [depth(r["heap_node"]) for r in records]


def validate_colors(records, colors, m, expected_U):
    assert len(records) == len(colors)
    counts = Counter(colors)
    assert set(counts) == set(range(1, m + 1))
    assert max(counts.values()) == expected_U
    for i, a in enumerate(records):
        for j in range(i):
            b = records[j]
            if colors[i] == colors[j]:
                assert a["right"] < b["left"] or b["right"] < a["left"]
    return [counts[c] for c in range(1, m + 1)]


def save_text(out, name, text):
    p = out / name
    if p.exists() and not ALLOW_REFRESH:
        raise FileExistsError(f"Refusing to overwrite {p}")
    p.write_text(text, encoding="utf-8")


def save_json(out, name, data):
    save_text(out, name, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def save_csv(out, name, rows):
    p = out / name
    if p.exists() and not ALLOW_REFRESH:
        raise FileExistsError(f"Refusing to overwrite {p}")
    with p.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main():
    global ALLOW_REFRESH
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--refresh-current-draft", action="store_true", help="Only refresh this task's own newly generated artifacts")
    args = parser.parse_args()
    out = args.out.resolve()
    ALLOW_REFRESH = args.refresh_current_draft
    if ALLOW_REFRESH:
        assert out == DEFAULT_OUT, "Refresh is restricted to this script's own new artifact directory."
    out.mkdir(parents=True, exist_ok=True)
    # Fail before producing partial output if this is a previous result directory.
    names = ["per_shape_metrics.csv", "method_summary.csv", "remaining_five.csv", "summary.json",
             "first_fit_validation.json", "README.md", "structural_comparison.tex",
             "absolute_gap_distribution.pdf", "absolute_gap_distribution.png",
             "relative_gap_ecdf.pdf", "relative_gap_ecdf.png"]
    assert ALLOW_REFRESH or not any((out / n).exists() for n in names), "Use a fresh --out directory."
    loaded = {k: json.loads((ROOT / p).read_text(encoding="utf-8"))
              for k, p in SOURCES.items() if p.endswith(".json")}
    old_base = {r["id"]: r for r in loaded["base_older_algorithm"]}
    cohorts = {c: loaded[c + "_construction"] for c in ("base", "holdout")}
    rows, summaries, ff_checks, remaining = [], [], [], []
    for cohort, data in cohorts.items():
        for index, r in enumerate(data):
            assert r["source_index"] == index
            N, m, opt = r["N"], r["m"], r["OPT"]
            assert N == 2 * r["n"] - 2 == len(r["records"])
            canonical_loads = shape_depth_loads(r["shape"])
            derived_colors = record_depth_colors(r["records"])
            ff_U = max(canonical_loads)
            assert len(canonical_loads) == m
            derived_loads = validate_colors(r["records"], derived_colors, m, ff_U)
            assert canonical_loads == derived_loads
            if cohort == "base":
                old = old_base[r["id"]]
                assert old["shape"] == r["shape"] and old["optimum"] == opt
                assert old["first_fit"]["max_bucket"] == ff_U
                assert old["first_fit"]["loads"] == canonical_loads
                old_ff = {v["heap_node"]: v["color"] for v in old["first_fit"]["records"]}
                assert [old_ff[v["heap_node"]] for v in r["records"]] == derived_colors
                assert old["activebalance"]["max_bucket"] == r["original_AB"]
                ff_source = "frozen base First-fit; independently depth-checked"
            else:
                exact = loaded["holdout_exact"][index]
                assert exact["shape"] == r["shape"] and exact["exact_optimum"] == opt
                ff_source = "new count-only canonical depth coloring; no timing"
            ff_checks.append({"cohort": cohort, "id": r["id"], "shape": r["shape"], "N": N, "m": m,
                              "loads": canonical_loads, "max_bucket": ff_U,
                              "record_heap_ids": [v["heap_node"] for v in r["records"]],
                              "depth_colors": derived_colors, "source": ff_source,
                              "shape_record_depth_agreement": True, "same_color_intervals_disjoint": True})
            values = {"First-fit": ff_U, "Exact OPT": opt}
            for method, (value_field, color_field) in FIELDS.items():
                values[method] = r[value_field]
                validate_colors(r["records"], r[color_field], m, values[method])
            for method in METHODS:
                U = values[method]; delta = U - opt
                assert delta >= 0
                rows.append({"cohort": cohort, "id": r["id"], "source_index": index,
                             "n": r["n"], "N": N, "m": m, "method": method, "U": U, "OPT": opt,
                             "absolute_gap": delta, "relative_gap": delta / opt,
                             "relative_gap_exact": f"{delta}/{opt}", "ALG_over_OPT": U / opt,
                             "OPT_attained": int(delta == 0),
                             "measurement_source": ff_source if method == "First-fit" else "frozen result"})
            if values["AB + 3→4"] > opt:
                remaining.append({"cohort": cohort, "id": r["id"], "n": r["n"], "N": N, "m": m,
                                  "U": values["AB + 3→4"], "OPT": opt,
                                  "absolute_gap": values["AB + 3→4"] - opt,
                                  "relative_gap": (values["AB + 3→4"] - opt) / opt,
                                  "relative_gap_exact": f"{values['AB + 3→4'] - opt}/{opt}",
                                  "stop_reason": r["final_stop"]})
        for method in METHODS:
            sub = [x for x in rows if x["cohort"] == cohort and x["method"] == method]
            abs_gaps = [x["absolute_gap"] for x in sub]
            rel_gaps = [x["relative_gap"] for x in sub]
            hits = sum(x["OPT_attained"] for x in sub)
            summaries.append({"cohort": cohort, "method": method, "shapes": len(sub),
                              "OPT_attained": hits, "failures": len(sub) - hits,
                              "hit_fraction": hits / len(sub), "mean_absolute_gap": statistics.mean(abs_gaps),
                              "max_absolute_gap": max(abs_gaps), "mean_relative_gap": statistics.mean(rel_gaps),
                              "max_relative_gap": max(rel_gaps),
                              "absolute_gap_counts": dict(sorted(Counter(abs_gaps).items()))})
    assert len(remaining) == 5 and all(r["absolute_gap"] == 1 for r in remaining)
    assert {r["id"] for r in remaining} == {"S0606", "S0710", "H1199", "H1265", "H1285"}
    save_csv(out, "per_shape_metrics.csv", rows)
    save_csv(out, "method_summary.csv", [{**r, "absolute_gap_counts": json.dumps(r["absolute_gap_counts"])} for r in summaries])
    save_csv(out, "remaining_five.csv", remaining)
    save_json(out, "first_fit_validation.json", {"status": "pass", "base_frozen_reproduced": 1323,
              "holdout_count_only_computed": 2115, "new_PIR_or_hash_proof_runs": 0, "new_timing_claims": 0,
              "checks": ff_checks})
    summary = {"status": "pass", "scope": {"base": "All 1323 unlabeled unordered full-binary skeletons, 2–14 leaves, m≤6",
               "holdout": "All 2115 further skeletons, 15–16 leaves, m≤6", "orientation": "One frozen source-canonical orientation per shape",
               "weighting": "Each shape has weight one; cohorts remain separate"},
               "definitions": {"absolute_gap": "U−OPT, integer records", "relative_gap": "(U−OPT)/OPT",
                               "ALG_over_OPT": "U/OPT", "hit": "U=OPT"},
               "methods": summaries, "remaining_five": remaining,
               "no_constant_additive_guarantee": "Observed five final failures all have gap one; this is not a universal bound.",
               "timing": "No new timing measured. Historical timing fields were deliberately not merged or plotted.",
               "validation": "All 3438 FF layouts cross-checked by independent shape and record-parent depths and pairwise interval disjointness. Base reproduces frozen FF node colors. All frozen algorithm assignments checked for capacity and properness.",
               "sources": {k: {"path": p, "sha256": digest(ROOT / p)} for k, p in SOURCES.items()},
               "presentation_script_sha256": digest(Path(__file__))}
    save_json(out, "summary.json", summary)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                         "axes.spines.right": False, "pdf.fonttype": 42, "ps.fonttype": 42})
    max_delta = max(r["max_absolute_gap"] for r in summaries)
    colors = ["#238b45", "#fdae61", "#f46d43", "#d73027", "#a50026", "#67001f"]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.25), sharey=True)
    for ax, cohort in zip(axes, cohorts):
        ss = [r for r in summaries if r["cohort"] == cohort]
        y = np.arange(len(METHODS)); left = np.zeros(len(METHODS))
        for delta in range(6):
            pct = np.array([sum(v for k, v in r["absolute_gap_counts"].items() if k == delta or (delta == 5 and k > 5)) / r["shapes"] * 100 for r in ss])
            ax.barh(y, pct, left=left, height=.64, color=colors[min(delta, len(colors)-1)], edgecolor="white",
                    linewidth=.6, label=f"Δ = {delta}" if delta < 5 else "Δ ≥ 5")
            left += pct
        for yi, r in enumerate(ss):
            ax.text(102, yi, f"{r['OPT_attained']}/{r['shapes']}", va="center", ha="left", fontsize=8)
        ax.set_xlim(0, 127); ax.set_xticks([0, 25, 50, 75, 100]); ax.set_xticklabels(["0", "25", "50", "75", "100"])
        ax.set_yticks(y); ax.set_yticklabels(METHODS); ax.set_ylim(5.65, -1.1)
        ax.set_title(f"{cohort.capitalize()} · {ss[0]['shapes']:,} shapes", weight="bold", pad=24)
        ax.text(102, -.78, "OPT hits", fontsize=8, weight="bold")
        ax.set_xlabel("Share of shapes (%)"); ax.grid(axis="x", alpha=.18); ax.set_axisbelow(True)
        ax.spines["right"].set_visible(False)
    axes[1].tick_params(labelleft=True)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(.5, -.005))
    fig.suptitle("Exact maximum-bucket gap: Δ = U − OPT", weight="bold", y=1.015)
    fig.tight_layout(rect=(0, .07, 1, 1))
    fig.savefig(out / "absolute_gap_distribution.pdf", bbox_inches="tight")
    fig.savefig(out / "absolute_gap_distribution.png", dpi=220, bbox_inches="tight"); plt.close(fig)
    line_colors = ["#555555", "#c33d3d", "#d99024", "#276fbf", "#14856a", "#111111"]
    styles = ["-", "--", ":", "-.", "-", ":"]
    fig, axes = plt.subplots(1, 2, figsize=(10.1, 3.8), sharey=True)
    for ax, cohort in zip(axes, cohorts):
        cohort_max = max(x["ALG_over_OPT"] for x in rows if x["cohort"] == cohort)
        for method, color, ls in zip(METHODS, line_colors, styles):
            vals = sorted(x["ALG_over_OPT"] for x in rows if x["cohort"] == cohort and x["method"] == method)
            unique = sorted(set(vals)); ys = [sum(v <= u for v in vals) / len(vals) for u in unique]
            ax.step([1] + unique + [cohort_max+.02], [0] + ys + [1], where="post", label=method, color=color, ls=ls,
                    linewidth=1.7 if method == "AB + 3→4" else 1.2)
        ax.set_title(f"{cohort.capitalize()} · {len(cohorts[cohort]):,} shapes", weight="bold")
        ax.set_xlabel("U / OPT"); ax.set_ylim(0, 1.025); ax.set_xlim(.99, max(x["ALG_over_OPT"] for x in rows if x["cohort"] == cohort)+.035)
        ax.grid(alpha=.2); ax.set_axisbelow(True)
    axes[0].set_ylabel("Fraction with ratio ≤ x")
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=6, frameon=False)
    fig.tight_layout(rect=(0, .09, 1, 1)); fig.savefig(out / "relative_gap_ecdf.pdf", bbox_inches="tight")
    fig.savefig(out / "relative_gap_ecdf.png", dpi=220, bbox_inches="tight"); plt.close(fig)
    tex = [r"% Generated from frozen structural results. Requires booktabs and graphicx.",
           r"\begin{table}[t]", r"\centering\small",
           r"\caption{Exact structural gaps. Each cell is base / holdout; cohorts contain 1323 / 2115 shapes. $\Delta=U-\mathrm{OPT}$ is an integer record count and $r=\Delta/\mathrm{OPT}$. Every shape has equal weight.}",
           r"\label{tab:structural-exact-gaps}", r"\begin{tabular}{lrrrr}", r"\toprule",
           r"Method & OPT hits & Mean $\Delta$ & Max $\Delta$ & Max $r$ (\%)\\", r"\midrule"]
    for method in METHODS:
        a, b = [next(r for r in summaries if r["cohort"] == c and r["method"] == method) for c in cohorts]
        label = method.replace("→", r"$\to$")
        tex.append(f"{label} & {a['OPT_attained']} / {b['OPT_attained']} & {a['mean_absolute_gap']:.3f} / {b['mean_absolute_gap']:.3f} & {a['max_absolute_gap']} / {b['max_absolute_gap']} & {100*a['max_relative_gap']:.1f} / {100*b['max_relative_gap']:.1f}" + r"\\")
    tex += [r"\bottomrule\end{tabular}\end{table}",
            "First-fit is the original smallest-available ancestor color, hence depth coloring. Base values reproduce frozen assignments; holdout values are new count-only evaluations independently checked against the canonical skeleton and record-parent forest. No new timing or PIR experiment is included.",
            "The final five failures are S0606, S0710, H1199, H1265, and H1285. Each has $U-\\mathrm{OPT}=1$; their exact relative gaps are $1/4$, $1/4$, $1/5$, $1/5$, and $1/6$, respectively. This finite observation does not imply a constant additive approximation guarantee.",
            r"\begin{figure}[t]\centering",
            r"\includegraphics[width=\linewidth]{figures/absolute_gap_distribution.pdf}",
            r"\caption{Exact integer gap distribution on the two frozen censuses; gaps of five or more are grouped. Green denotes an attained optimum; labels give exact hit counts. The final five positive gaps are all one record, but the worst relative gaps remain 25\% and 20\%. These are structural counts, not PIR costs or deployment success rates.}",
            r"\label{fig:structural-gap-distribution}\end{figure}"]
    save_text(out, "structural_comparison.tex", "\n".join(tex) + "\n")
    md = ["# Frozen structural comparison", "", "This directory adds presentation artifacts only. No earlier result, manuscript, algorithm, or timing was overwritten.", "",
          "Base: 1323 shapes with 2–14 leaves and m≤6. Holdout: 2115 shapes with 15–16 leaves and m≤6. Each source-canonical shape has equal weight; cohorts are never pooled for the headline figures.", "",
          "## Definitions and results", "", "Absolute gap Δ=U−OPT counts records. Relative gap is Δ/OPT, not excess over a lower bound. Exact OPT is a reference value from frozen complete search, not a newly timed construction.", "",
          "| Method | Base hits | Holdout hits | Mean Δ, base / holdout | Max Δ, base / holdout | Max relative gap, base / holdout |", "|---|---:|---:|---:|---:|---:|"]
    for method in METHODS:
        a, b = [next(r for r in summaries if r["cohort"] == c and r["method"] == method) for c in cohorts]
        md.append(f"| {method} | {a['OPT_attained']}/1323 | {b['OPT_attained']}/2115 | {a['mean_absolute_gap']:.6f} / {b['mean_absolute_gap']:.6f} | {a['max_absolute_gap']} / {b['max_absolute_gap']} | {a['max_relative_gap']:.2%} / {b['max_relative_gap']:.2%} |")
    md += ["", "`per_shape_metrics.csv` contains all six methods with exact integer numerator/denominator alongside decimal relative gaps. `method_summary.csv` and `summary.json` additionally contain mean relative gaps and each integer-gap count. `remaining_five.csv` lists every final failure, exact gap, and stored stop reason.", "",
           "## First-fit provenance and validation", "",
           "The original first_fit_coloring chooses the smallest color absent from the ancestor path, so a node at forest depth d receives color d. Base First-fit values and all heap-node colors exactly reproduce the frozen older artifact. Holdout First-fit was absent there and is newly computed by a count-only traversal. For every one of the 3438 structures, a second traversal of the saved record-parent relation agrees with the canonical binary shape's depth loads; every same-color pair has disjoint target-rank intervals. No SMT hashes, PIR queries, or timing experiments were run for this addition. All four saved algorithm variants also pass independent capacity and interval-properness checks. See first_fit_validation.json. Historical timing fields are deliberately excluded.", "",
           "## Five remaining failures", "",
           "S0606, S0710, H1199, H1265, H1285 all have absolute gap one. Their relative gaps are 1/4, 1/4, 1/5, 1/5, 1/6. This finite observation does not establish U≤OPT+1 for arbitrary structures. The original AB and refined variants retain the stated small-instance scope; these graphs do not measure PIR performance.", "",
           "## Two logical limits for the surrounding discussion", "",
           "1. A polynomial capacity-decision algorithm, if available for a stated graph class, decides whether the proposed cap is feasible. It need not answer yes at a merely necessary lower bound. Equality OPT=LB requires a separate sufficiency theorem or a valid witness at LB. The known Bonomo–Mattia–Oriolo fixed-color algorithm is polynomial only for fixed m: [author manuscript, Theorems 11–12](https://staff.dc.uba.ar/fbonomo/docs/papers/BMO11.pdf). The current finite binary census is evidence, not a proof of universal LB feasibility.", "",
           "2. Maximum bucket size U alone does not determine PIR cost. The number of buckets, complete bucket-size vector, record packing, backend matrix dimensions, preprocessing/hint state, query count and amortization matter. Even under a conditional sum-of-square-roots proxy, same N=10, m=4, U=4 profiles (4,4,1,1) and (4,3,2,1) have different costs (6 versus 2+sqrt(3)+sqrt(2)+1). This illustrates why a scalar balance optimum cannot, without a backend-specific cost analysis, be called a communication optimum. No new numeric PIR cost is inferred here.", "",
           "## Files and reproduction", "", "`absolute_gap_distribution.pdf/.png` is the primary comparison, with integer-gap categories and exact hit labels. `relative_gap_ecdf.pdf/.png` plots the full unweighted ECDF of U/OPT; closely overlapping curves are expected when most shapes attain OPT. `structural_comparison.tex` is a standalone insert requiring booktabs/graphicx; copy the PDF to the manuscript figures directory when integrating. This script does not edit a manuscript.", "",
           "Run from repository root with a fresh output directory:", "", "```powershell", "python examples/tifs_layout_transfer_20260910/structural/build_structural_comparison.py --out NEW_OUTPUT_DIRECTORY", "```", "",
           "All source paths and SHA-256 hashes are in summary.json. The script refuses to overwrite generated files. All figures are derived only from the saved capacities and the documented count-only First-fit addition."]
    save_text(out, "README.md", "\n".join(md) + "\n")
    print(json.dumps({"output": str(out), "rows": len(rows), "methods": summaries, "remaining": remaining}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
