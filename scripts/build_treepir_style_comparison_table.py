from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Tuple


RECORD_BYTES = 32
METADATA_BYTES_PER_ACTIVE_NODE = 24


SCHEME_LABELS = {
    "perfectized_treepir": "Perfectized-TreePIR",
    "pbc_active": "PBC-active",
    "flat_normal_pir_m": "Flat-normal-PIR-m",
    "pruned_treepir_h": "Pruned-TreePIR-h",
    "profile_balanced": "Profile-balanced",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a TreePIR-style comparison matrix from the full SimplePIR "
            "backend artifacts and layout manifests."
        )
    )
    parser.add_argument(
        "--backend-csv",
        type=Path,
        default=Path("examples/simplepir_full_backend_results.csv"),
        help="CSV produced by run_simplepir_full_backend_experiment.py.",
    )
    parser.add_argument(
        "--layout-dir",
        type=Path,
        default=Path("examples/simplepir_full_backend_layouts"),
        help="Directory containing per-scheme SimplePIR manifests.",
    )
    parser.add_argument(
        "--out-csv",
        type=Path,
        default=Path("examples/treepir_style_comparison_results.csv"),
        help="Output CSV for the unified comparison matrix.",
    )
    parser.add_argument(
        "--out-note",
        type=Path,
        default=Path("notes/treepir_style_comparison_note.md"),
        help="Markdown note summarizing the comparison.",
    )
    return parser.parse_args()


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def as_float(row: Dict[str, str], key: str, default: float = 0.0) -> float:
    raw = row.get(key, "")
    if raw == "":
        return default
    return float(raw)


def as_int(row: Dict[str, str], key: str, default: int = 0) -> int:
    raw = row.get(key, "")
    if raw == "":
        return default
    return int(float(raw))


def sparsity_token(value: float) -> str:
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def manifest_path(layout_dir: Path, h: int, sparsity: float, seed: int, scheme: str) -> Path:
    name = f"h{h}_s{sparsity_token(sparsity)}_seed{seed}_{scheme}"
    return layout_dir / name / "manifest.json"


def load_manifest(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def bucket_profile_from_manifest(manifest: Dict[str, Any]) -> Tuple[List[int], int, int]:
    sizes = [int(subdb.get("records", 0)) for subdb in manifest.get("subdatabases", [])]
    if not sizes:
        return [], 0, 0
    return sizes, max(sizes), max(sizes) - min(sizes)


def perfectized_record_count(h: int) -> int:
    return (1 << (h + 1)) - 2


def perfectized_max_bucket(records: int, width: int) -> int:
    return math.ceil(records / width) if width else 0


def scheme_digest_kb(stored_records: int) -> float:
    return stored_records * RECORD_BYTES / 1024.0


def active_metadata_kb(active_nodes: int, scheme: str) -> float:
    if scheme == "perfectized_treepir":
        return 0.0
    if scheme == "pbc_active":
        # Conservative indexing-map estimate: three replicated active records,
        # each needing one compact key and one subindex endpoint.
        return 3 * active_nodes * 16 / 1024.0
    return active_nodes * METADATA_BYTES_PER_ACTIVE_NODE / 1024.0


def empty_backend_fields() -> Dict[str, str]:
    keys = [
        "setup_ms",
        "client_query_ms",
        "server_total_ms",
        "server_parallel_ms",
        "client_decode_ms",
        "offline_kb",
        "online_upload_kb",
        "online_download_kb",
        "online_total_kb",
    ]
    return {key: "" for key in keys}


def backend_fields(row: Dict[str, str]) -> Dict[str, str]:
    keys = [
        "setup_ms",
        "client_query_ms",
        "server_total_ms",
        "server_parallel_ms",
        "client_decode_ms",
        "offline_kb",
        "online_upload_kb",
        "online_download_kb",
        "online_total_kb",
    ]
    return {key: row.get(key, "") for key in keys}


def build_rows(backend_rows: List[Dict[str, str]], layout_dir: Path) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[int, float, int], Dict[str, Dict[str, str]]] = defaultdict(dict)
    for row in backend_rows:
        key = (as_int(row, "height"), as_float(row, "sparsity"), as_int(row, "seed"))
        grouped[key][row["scheme"]] = row

    out: List[Dict[str, Any]] = []
    for (h, sparsity, seed), schemes in sorted(grouped.items()):
        profile = schemes.get("profile_balanced")
        if profile is None:
            continue
        occupied = as_int(profile, "occupied")
        active_nodes = as_int(profile, "active_nodes")
        exact_width = as_int(profile, "exact_width")
        empty_ratio_pct = sparsity * 100.0

        perfect_records = perfectized_record_count(h)
        perfect_width = h
        out.append(
            {
                "height": h,
                "sparsity": sparsity,
                "empty_ratio_pct": empty_ratio_pct,
                "seed": seed,
                "occupied": occupied,
                "active_nodes": active_nodes,
                "scheme": "perfectized_treepir",
                "scheme_label": SCHEME_LABELS["perfectized_treepir"],
                "stored_records": perfect_records,
                "digest_storage_kb": scheme_digest_kb(perfect_records),
                "metadata_kb": active_metadata_kb(active_nodes, "perfectized_treepir"),
                "width": perfect_width,
                "exact_width": exact_width,
                "max_bucket": "",
                "bucket_gap": "",
                "max_bucket_over_ideal": "",
                "backend_status": "structural-only",
                **empty_backend_fields(),
            }
        )

        # TreePIR's main experimental foil is PBC.  This row adapts the same
        # generic-batch-code accounting to our active proof objects: retrieve a
        # batch of at most m active proof nodes from N active records, using
        # about 1.5m buckets, three replicas per record, and bucket size about
        # 2N/m.  It is a formula baseline rather than a full backend run.
        pbc_width = math.ceil(1.5 * exact_width)
        pbc_stored = 3 * active_nodes
        pbc_max_bucket = math.ceil(2 * active_nodes / exact_width) if exact_width else 0
        pbc_ideal = math.ceil(pbc_stored / pbc_width) if pbc_width else 0
        out.append(
            {
                "height": h,
                "sparsity": sparsity,
                "empty_ratio_pct": empty_ratio_pct,
                "seed": seed,
                "occupied": occupied,
                "active_nodes": active_nodes,
                "scheme": "pbc_active",
                "scheme_label": SCHEME_LABELS["pbc_active"],
                "stored_records": pbc_stored,
                "digest_storage_kb": scheme_digest_kb(pbc_stored),
                "metadata_kb": active_metadata_kb(active_nodes, "pbc_active"),
                "width": pbc_width,
                "exact_width": exact_width,
                "max_bucket": pbc_max_bucket,
                "bucket_gap": "",
                "max_bucket_over_ideal": (pbc_max_bucket / pbc_ideal)
                if pbc_ideal
                else "",
                "backend_status": "PBC formula",
                **empty_backend_fields(),
            }
        )

        for scheme in ["flat_normal_pir_m", "pruned_treepir_h", "profile_balanced"]:
            row = schemes.get(scheme)
            if row is None:
                continue
            manifest = load_manifest(
                manifest_path(layout_dir, h, sparsity, seed, scheme)
            )
            bucket_sizes, max_bucket, bucket_gap = bucket_profile_from_manifest(manifest)
            width = as_int(row, "width")
            stored = as_int(row, "stored_records_padded")
            ideal = math.ceil(active_nodes / width) if width else 0
            if scheme == "flat_normal_pir_m":
                max_bucket = active_nodes
                bucket_gap = 0
                ideal = active_nodes
            out.append(
                {
                    "height": h,
                    "sparsity": sparsity,
                    "empty_ratio_pct": empty_ratio_pct,
                    "seed": seed,
                    "occupied": occupied,
                    "active_nodes": active_nodes,
                    "scheme": scheme,
                    "scheme_label": SCHEME_LABELS[scheme],
                    "stored_records": stored,
                    "digest_storage_kb": scheme_digest_kb(stored),
                    "metadata_kb": active_metadata_kb(active_nodes, scheme),
                    "width": width,
                    "exact_width": exact_width,
                    "max_bucket": max_bucket,
                    "bucket_gap": bucket_gap,
                    "max_bucket_over_ideal": (max_bucket / ideal) if ideal else "",
                    "backend_status": "full-simplepir-api",
                    **backend_fields(row),
                }
            )
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "height",
        "sparsity",
        "empty_ratio_pct",
        "seed",
        "occupied",
        "active_nodes",
        "scheme",
        "scheme_label",
        "stored_records",
        "digest_storage_kb",
        "metadata_kb",
        "width",
        "exact_width",
        "max_bucket",
        "bucket_gap",
        "max_bucket_over_ideal",
        "backend_status",
        "setup_ms",
        "client_query_ms",
        "server_total_ms",
        "server_parallel_ms",
        "client_decode_ms",
        "offline_kb",
        "online_upload_kb",
        "online_download_kb",
        "online_total_kb",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def fmt_num(value: Any, digits: int = 2) -> str:
    if value == "" or value is None:
        return "-"
    if isinstance(value, str):
        if value == "":
            return "-"
        try:
            value = float(value)
        except ValueError:
            return value
    if isinstance(value, int):
        return f"{value:,}"
    if abs(float(value) - round(float(value))) < 1e-9:
        return f"{int(round(float(value))):,}"
    return f"{float(value):,.{digits}f}"


def rows_for_setting(
    rows: Iterable[Dict[str, Any]], h: int, sparsity: float
) -> List[Dict[str, Any]]:
    wanted = []
    for row in rows:
        if int(row["height"]) == h and abs(float(row["sparsity"]) - sparsity) < 1e-12:
            wanted.append(row)
    order = {
        "perfectized_treepir": 0,
        "pbc_active": 1,
        "flat_normal_pir_m": 2,
        "pruned_treepir_h": 3,
        "profile_balanced": 4,
    }
    return sorted(wanted, key=lambda r: order[r["scheme"]])


def pct_reduction(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return (old - new) / old * 100.0


def profile_pairs(rows: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
    by_setting: Dict[Tuple[int, float, int], Dict[str, Dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        key = (int(row["height"]), float(row["sparsity"]), int(row["seed"]))
        by_setting[key][row["scheme"]] = row
    triples = []
    for schemes in by_setting.values():
        if {
            "flat_normal_pir_m",
            "pruned_treepir_h",
            "profile_balanced",
        }.issubset(schemes):
            triples.append(
                (
                    schemes["flat_normal_pir_m"],
                    schemes["pruned_treepir_h"],
                    schemes["profile_balanced"],
                )
            )
    return triples


def write_note(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    representative = rows_for_setting(rows, h=24, sparsity=0.9995)
    triples = profile_pairs(rows)
    flat_reductions = [
        pct_reduction(
            float(profile["online_total_kb"]),
            float(flat["online_total_kb"]),
        )
        for flat, _, profile in triples
    ]
    pruned_width_reductions = [
        pct_reduction(float(profile["width"]), float(pruned["width"]))
        for _, pruned, profile in triples
    ]
    pruned_online_changes = [
        pct_reduction(float(profile["online_total_kb"]), float(pruned["online_total_kb"]))
        for _, pruned, profile in triples
    ]
    profile_balance_ratios = [
        float(profile["max_bucket_over_ideal"])
        for _, _, profile in triples
        if profile["max_bucket_over_ideal"] != ""
    ]

    lines: List[str] = []
    lines.append("# TreePIR-style comparison matrix\n")
    lines.append(
        "This note reorganizes the current experiments in the same spirit as TreePIR's "
        "evaluation section: separate the structural organization cost, the client-side "
        "batch width, the color-store balance, and the concrete PIR API measurements.\n"
    )
    lines.append("## Representative setting: h=24, 99.95% empty leaves\n")
    lines.append(
        "| Scheme | Stored records | Digest KB | Public index/metadata KB | Width | Max bucket | Gap | Full SimplePIR online KB | Backend status |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in representative:
        lines.append(
            "| {scheme} | {stored} | {digest} | {metadata} | {width} | {maxb} | {gap} | {online} | {status} |".format(
                scheme=row["scheme_label"],
                stored=fmt_num(row["stored_records"]),
                digest=fmt_num(row["digest_storage_kb"]),
                metadata=fmt_num(row["metadata_kb"]),
                width=fmt_num(row["width"]),
                maxb=fmt_num(row["max_bucket"]),
                gap=fmt_num(row["bucket_gap"]),
                online=fmt_num(row["online_total_kb"]),
                status=row["backend_status"],
            )
        )
    lines.append("")
    lines.append("## Aggregate observations over the full SimplePIR settings\n")
    lines.append(
        f"- Profile-balanced reduces full SimplePIR online communication versus flat normal PIR by "
        f"{fmt_num(min(flat_reductions))}% to {fmt_num(max(flat_reductions))}% "
        f"(mean {fmt_num(mean(flat_reductions))}%)."
    )
    lines.append(
        f"- Profile-balanced reduces the query width versus Pruned-TreePIR-h by "
        f"{fmt_num(min(pruned_width_reductions))}% to {fmt_num(max(pruned_width_reductions))}% "
        f"(mean {fmt_num(mean(pruned_width_reductions))}%)."
    )
    lines.append(
        f"- Its online communication compared with Pruned-TreePIR-h ranges from "
        f"{fmt_num(min(pruned_online_changes))}% reduction to {fmt_num(max(pruned_online_changes))}% reduction "
        f"(mean {fmt_num(mean(pruned_online_changes))}%). Negative values mean a parameter-tiering loss."
    )
    lines.append(
        f"- The profile-balanced maximum bucket is within a factor "
        f"{fmt_num(min(profile_balance_ratios), 3)}--{fmt_num(max(profile_balance_ratios), 3)} "
        f"of the equal-split ideal N/m on these settings."
    )
    lines.append("")
    lines.append("## How this mirrors TreePIR's evaluation logic\n")
    lines.append(
        "- Perfectized-TreePIR is kept as a structural baseline because materializing a full h-level SMT is too large for a fair full API run."
    )
    lines.append(
        "- PBC-active adapts TreePIR's PBC baseline to the active proof-object database: three replicated records, about 1.5m buckets, and bucket size about 2N/m. It is formula-only here; the separate PBC runner performs concrete bucket placement and Cuckoo assignment."
    )
    lines.append(
        "- Flat-normal-PIR-m is the ordinary PIR baseline: it keeps one active-node database and pays for m independent proof positions."
    )
    lines.append(
        "- Pruned-TreePIR-h is not an original TreePIR baseline. It is an adversarial pruning-only ablation designed to answer the reviewer question, 'is this just TreePIR after deleting empty nodes?'"
    )
    lines.append(
        "- Profile-balanced is our final organization: active-node storage, exact active width m, served-interval lookup, and balanced color stores."
    )
    lines.append("")
    lines.append(
        "The most defensible claim is therefore not that profile-balanced always has the smallest SimplePIR byte count under every parameter tier. "
        "The stronger and more stable claim is that it turns SMT proof retrieval into a compact exact-width interface, "
        "keeps the bucket profile close to the ideal split, and substantially reduces the cost of a flat normal-PIR proof retrieval."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    backend_rows = load_csv(args.backend_csv)
    rows = build_rows(backend_rows, args.layout_dir)
    write_csv(args.out_csv, rows)
    write_note(args.out_note, rows)
    print(f"Wrote {args.out_csv} ({len(rows)} rows)")
    print(f"Wrote {args.out_note}")


if __name__ == "__main__":
    main()
