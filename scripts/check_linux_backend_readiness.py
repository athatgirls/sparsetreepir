from __future__ import annotations

import csv
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
OUT_CSV = ROOT / "examples" / "linux_extra_backend_readiness.csv"
OUT_NOTE = ROOT / "notes" / "linux_extra_backend_readiness_note.md"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def cpu_flags() -> str:
    if platform.system().lower() != "linux":
        return ""
    try:
        out = subprocess.check_output(["bash", "-lc", "lscpu | grep -i '^Flags' || true"], text=True)
    except Exception:
        return ""
    return out.lower()


def yes(value: bool) -> str:
    return "yes" if value else "no"


def main() -> None:
    flags = cpu_flags()
    paths = {
        "TreePIR artifact": ROOT / "external" / "TreePIR-main",
        "TreePIR indexing": ROOT / "external" / "TreePIR-main" / "TreePIR-Indexing",
        "Spiral checkout": ROOT / ".tools" / "spiral",
        "YPIR checkout": ROOT / ".tools" / "ypir",
        "VBPIR checkout": ROOT / ".tools" / "vectorized_batchpir",
        "SealPIR checkout": ROOT / ".tools" / "SealPIR",
    }
    commands = ["git", "python3", "java", "javac", "cmake", "g++", "clang++", "docker", "go"]

    rows: List[Dict[str, str]] = []
    for name, path in paths.items():
        rows.append({"category": "path", "item": name, "ready": yes(path.exists()), "detail": str(path)})
    for cmd in commands:
        rows.append({"category": "command", "item": cmd, "ready": yes(command_exists(cmd)), "detail": shutil.which(cmd) or ""})
    rows.append(
        {
            "category": "hardware",
            "item": "AVX-512 for YPIR",
            "ready": yes("avx512" in flags),
            "detail": "required for the current YPIR route; check lscpu flags",
        }
    )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["category", "item", "ready", "detail"])
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Linux extra backend readiness",
        "",
        "| category | item | ready | detail |",
        "|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(f"| {row['category']} | {row['item']} | {row['ready']} | `{row['detail']}` |")
    lines.extend(
        [
            "",
            "Interpretation:",
            "",
            "- TreePIR indexing is the lightest extra artifact check and should work once Java and `external/TreePIR-main` are present.",
            "- Spiral and VBPIR need backend-specific build steps from the TreePIR/Spiral/VBPIR artifacts.",
            "- YPIR should only be attempted on a machine with AVX-512 support.",
            "- SealPIRplus is a service/orchestrator route and requires heavier SEAL/gRPC/Protobuf setup.",
        ]
    )
    OUT_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_CSV)
    print(OUT_NOTE)


if __name__ == "__main__":
    main()
