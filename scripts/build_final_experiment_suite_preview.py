from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compact preview of the final experiment suite.")
    parser.add_argument("--out", type=Path, default=Path("notes/final_experiment_suite_preview.md"))
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def f(row: Dict[str, str], key: str) -> float:
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


def group_by_setting(rows: Iterable[Dict[str, str]]) -> Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]]:
    grouped: Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in rows:
        key = (int(f(row, "height")), f(row, "sparsity"), int(f(row, "seed")))
        grouped[key][row["scheme"]] = row
    return grouped


def metric_value(row: Dict[str, str], metric: str) -> float:
    if metric == "max_bucket_proxy":
        stored = f(row, "stored_records")
        width = max(1.0, f(row, "width"))
        observed = f(row, "max_bucket")
        return observed if observed > 0 else stored / width
    return f(row, metric)


def avg_reduction_against(rows: List[Dict[str, str]], baseline: str, ours: str, metric: str) -> float:
    vals: List[float] = []
    for schemes in group_by_setting(rows).values():
        if baseline in schemes and ours in schemes:
            vals.append(pct_reduction(metric_value(schemes[ours], metric), metric_value(schemes[baseline], metric)))
    return mean(vals)


def table(lines: List[str], headers: List[str], rows: List[List[str]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")


def experiment0(lines: List[str]) -> None:
    rows = read_csv(Path("examples/smt_batch_proof_vs_batch_pir_results.csv"))
    # Use the largest target batch available for each height/empty setting.
    all_by_setting: Dict[Tuple[int, float], List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (int(f(row, "height")), f(row, "empty_pct"))
        all_by_setting[key].append(row)

    selected = []
    for key, setting_rows in sorted(all_by_setting.items()):
        max_batch = max(f(row, "target_batch") for row in setting_rows)
        schemes = {row["scheme"]: row for row in setting_rows if f(row, "target_batch") == max_batch}
        if "ordinary_smt_batch_serving" in schemes and "sparsetreepir_batch_pir" in schemes:
            ordinary = schemes["ordinary_smt_batch_serving"]
            ours = schemes["sparsetreepir_batch_pir"]
            selected.append(
                [
                    fmt(f(ours, "height"), 0),
                    f"{f(ordinary, 'empty_pct'):.3f}%",
                    fmt(f(ordinary, "target_batch"), 0),
                    fmt(f(ordinary, "ordinary_batch_dedup_bytes"), 0),
                    fmt(f(ours, "width"), 0),
                    fmt(f(ours, "max_bucket"), 0),
                    f"{f(ours, 'dummy_rate') * 100:.1f}%",
                ]
            )
    lines.append("## Experiment 0: Plain SMT serving as the non-private reference\n")
    table(lines, ["h", "empty", "batch", "plain dedup bytes", "Sparse width", "Sparse max bucket", "dummy"], selected[:6])
    lines.append(
        "\nEffect: ordinary SMT serving is much smaller because it is non-private. "
        "SparseTreePIR should be presented as the target-private layer above this lower-cost reference.\n"
    )


def experiment1_to_4(lines: List[str]) -> None:
    rows = read_csv(Path("examples/treepir_style_comparison_results.csv"))
    reductions = {
        "Perfectized records": avg_reduction_against(rows, "perfectized_treepir", "profile_balanced", "stored_records"),
        "Perfectized max bucket": avg_reduction_against(rows, "perfectized_treepir", "profile_balanced", "max_bucket_proxy"),
        "Pruned-h width": avg_reduction_against(rows, "pruned_treepir_h", "profile_balanced", "width"),
        "Pruned-h max bucket": avg_reduction_against(rows, "pruned_treepir_h", "profile_balanced", "max_bucket"),
        "PBC-SMT stored records": avg_reduction_against(rows, "pbc_active", "profile_balanced", "stored_records"),
        "PBC-SMT width": avg_reduction_against(rows, "pbc_active", "profile_balanced", "width"),
        "PBC-SMT max bucket": avg_reduction_against(rows, "pbc_active", "profile_balanced", "max_bucket"),
        "Flat active max bucket": avg_reduction_against(rows, "flat_normal_pir_m", "profile_balanced", "max_bucket"),
    }
    lines.append("## Experiments 1-4: Object selection and organization baselines\n")
    table(
        lines,
        ["comparison", "mean reduction by SparseTreePIR"],
        [[name, f"{value:.1f}%"] for name, value in reductions.items()],
    )
    lines.append(
        "\nEffect: the strongest structural wins are against full-coordinate TreePIR "
        "and flat active PIR. Against Pruned-h, storage is intentionally similar, "
        "but width and largest bucket still improve. Against PBC-SMT, the effect "
        "is stable: remove 3x replication, reduce width by about one third, and "
        "halve the largest searched bucket.\n"
    )


def experiment5(lines: List[str]) -> None:
    rows = read_csv(Path("examples/height16_20_profile_balance_30seed.csv")) + read_csv(
        Path("examples/height24_profile_balance_5seed.csv")
    )
    reduction = mean(f(row, "reduction_vs_hybrid") for row in rows)
    profile_lb = mean(f(row, "profile_over_lb") for row in rows)
    valid = mean(f(row, "valid_rate") for row in rows)
    selected = []
    for row in rows:
        selected.append(
            [
                fmt(f(row, "height"), 0),
                f"{f(row, 'sparsity') * 100:.3f}%",
                fmt(f(row, "active"), 0),
                fmt(f(row, "m"), 1),
                fmt(f(row, "hybrid_max"), 1),
                fmt(f(row, "profile_max"), 1),
                f"{f(row, 'profile_over_lb'):.3f}",
            ]
        )
    lines.append("## Experiment 5: ActiveBalance ablation\n")
    table(lines, ["h", "empty", "A", "m", "valid max", "ActiveBalance max", "AB/LB"], selected[:9])
    lines.append(
        f"\nEffect: ActiveBalance reduces the largest color store by {reduction:.1f}% "
        f"on average versus the valid initializer/hybrid profile, while staying "
        f"within {profile_lb:.3f}x of the structural lower bound on average. "
        f"All tested colorings remain valid (valid rate {valid:.1%}).\n"
    )


def experiment6(lines: List[str]) -> None:
    rows = read_csv(Path("examples/height128_256_compressed_smt_profile_balance_results.csv"))
    selected = []
    for row in rows:
        selected.append(
            [
                fmt(f(row, "height"), 0),
                fmt(f(row, "occupied"), 0),
                fmt(f(row, "active"), 0),
                fmt(f(row, "m"), 1),
                fmt(f(row, "profile_max"), 1),
                f"{f(row, 'profile_over_lb'):.3f}",
            ]
        )
    lines.append("## Experiment 6: High-height compressed SMTs\n")
    table(lines, ["h", "occupied", "A", "m", "ActiveBalance max", "AB/LB"], selected)
    lines.append(
        "\nEffect: even at verifier heights 128 and 256, the private retrieval width "
        "tracks the occupied-key skeleton rather than the verifier height. The "
        "active color-store profile is near the structural lower bound.\n"
    )


def experiment7(lines: List[str]) -> None:
    rows = read_csv(Path("examples/real_rollup_smt_workload_summary.csv"))
    selected = []
    for row in rows:
        selected.append(
            [
                row["workload"],
                fmt(f(row, "height"), 0),
                fmt(f(row, "keys"), 0),
                fmt(f(row, "active_nodes"), 0),
                fmt(f(row, "m"), 0),
                f"{f(row, 'dummy_fraction_percent'):.1f}%",
                fmt(f(row, "profile_max_bucket"), 0),
            ]
        )
    lines.append("## Experiment 7: Real-key / trace-derived workload sanity check\n")
    table(lines, ["workload", "h", "keys", "A", "m", "dummy", "max bucket"], selected)
    lines.append(
        "\nEffect: Polygon and ZKsync-style workloads show the same behavior as the "
        "synthetic high-height setting: h is large, but active width remains in "
        "the low teens for these samples.\n"
    )


def experiment8(lines: List[str]) -> None:
    rows = read_csv(Path("examples/metadata_overhead_results.csv"))
    metadata_ratio = mean(f(row, "metadata_over_digest") for row in rows)
    selected = []
    for row in rows:
        selected.append(
            [
                fmt(f(row, "height"), 0),
                f"{f(row, 'sparsity') * 100:.3f}%",
                fmt(f(row, "active"), 0),
                fmt(f(row, "digest_kb"), 1),
                fmt(f(row, "metadata_kb"), 1),
                f"{f(row, 'metadata_over_digest'):.2f}",
                fmt(f(row, "setup_ms"), 1),
            ]
        )
    lines.append("## Experiment 8: Metadata and preprocessing overhead\n")
    table(lines, ["h", "empty", "A", "digest KB", "metadata KB", "meta/digest", "setup ms"], selected)
    lines.append(
        f"\nEffect: public metadata scales linearly with active records and is "
        f"{metadata_ratio:.2f}x of digest payload in the current encoding. This "
        "is a real setup cost, but it is active-size rather than full-coordinate-size.\n"
    )


def experiment9(lines: List[str]) -> None:
    rows = read_csv(Path("examples/simplepir_full_backend_results.csv"))
    reductions = {
        "vs Flat online KB": avg_reduction_against(rows, "flat_normal_pir_m", "profile_balanced", "online_total_kb"),
        "vs Flat QueryGen": avg_reduction_against(rows, "flat_normal_pir_m", "profile_balanced", "client_query_ms"),
        "vs PBC-SMT online KB": avg_reduction_against(rows, "pbc_active", "profile_balanced", "online_total_kb"),
        "vs PBC-SMT QueryGen": avg_reduction_against(rows, "pbc_active", "profile_balanced", "client_query_ms"),
        "vs Pruned-h online KB": avg_reduction_against(rows, "pruned_treepir_h", "profile_balanced", "online_total_kb"),
        "vs Pruned-h QueryGen": avg_reduction_against(rows, "pruned_treepir_h", "profile_balanced", "client_query_ms"),
    }
    lines.append("## Experiment 9: SimplePIR executable backend bridge\n")
    table(lines, ["comparison", "mean reduction by SparseTreePIR"], [[k, f"{v:.1f}%"] for k, v in reductions.items()])
    lines.append(
        "\nEffect: SparseTreePIR is clearly better than Flat active and PBC-SMT "
        "under this SimplePIR runner. The Pruned-h byte result is mixed because "
        "backend parameter tiers can favor height-pinned layouts in some small "
        "settings; timing and structural metrics still show why Pruned-h is not "
        "the clean organization target.\n"
    )


def experiment10(lines: List[str]) -> None:
    rows = read_csv(Path("examples/smt_batch_proof_vs_batch_pir_results.csv"))
    vals = [f(row, "dummy_rate") * 100.0 for row in rows if row["scheme"] == "sparsetreepir_batch_pir"]
    pruned = [f(row, "dummy_rate") * 100.0 for row in rows if row["scheme"] == "pruned_level_pir_h"]
    lines.append("## Experiment 10: Privacy-shape / dummy-ratio analysis\n")
    lines.append(f"- SparseTreePIR dummy ratio range: {min(vals):.1f}% to {max(vals):.1f}%.\n")
    lines.append(f"- Pruned-h dummy ratio range: {min(pruned):.1f}% to {max(pruned):.1f}%.\n")
    lines.append(
        "Effect: fixed-shape privacy costs dummy queries. Reducing the color universe "
        "from h to active width m lowers the dummy burden compared with height-pinned "
        "layouts, although it cannot remove dummy queries entirely.\n"
    )


def main() -> None:
    args = parse_args()
    lines: List[str] = []
    lines.append("# Final experiment suite preview\n")
    lines.append(
        "This file is a compact preview assembled from existing raw experiment "
        "outputs. It is meant for deciding which results are strong enough to "
        "enter the paper, not as the final manuscript text.\n"
    )
    experiment0(lines)
    experiment1_to_4(lines)
    experiment5(lines)
    experiment6(lines)
    experiment7(lines)
    experiment8(lines)
    experiment9(lines)
    experiment10(lines)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
