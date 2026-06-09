from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict


def load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Adapter entrypoint for running an external SimplePIR implementation "
            "on exported color subdatabases. This script validates the environment "
            "and leaves the actual SimplePIR command template explicit."
        )
    )
    parser.add_argument("--manifest", type=Path, default=Path("examples/simplepir_layout/manifest.json"))
    parser.add_argument(
        "--simplepir-dir",
        type=Path,
        default=None,
        help="Path to the checked-out ahenzinger/simplepir repository. Defaults to SIMPLEPIR_DIR.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the commands that would be executed.",
    )
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    simplepir_dir = args.simplepir_dir
    if simplepir_dir is None:
        import os

        raw = os.environ.get("SIMPLEPIR_DIR", "")
        simplepir_dir = Path(raw) if raw else None

    if simplepir_dir is None:
        raise SystemExit("Set --simplepir-dir or SIMPLEPIR_DIR to the official SimplePIR checkout.")
    if not simplepir_dir.exists():
        raise SystemExit(f"SimplePIR directory does not exist: {simplepir_dir}")
    if not args.dry_run and shutil.which("go") is None:
        raise SystemExit("Go is not installed or not on PATH; install Go before running the external SimplePIR backend.")

    base_dir = args.manifest.parent
    print(f"manifest={args.manifest}")
    print(f"simplepir_dir={simplepir_dir}")
    print(f"height={manifest['height']} active={manifest['active_nodes']} width={manifest['width']}")

    for subdb in manifest["subdatabases"]:
        db_file = base_dir / subdb["database_file"]
        if subdb["records"] == 0:
            continue
        # The official SimplePIR repository exposes benchmark binaries rather
        # than a stable cross-project CLI. We keep the command explicit so the
        # artifact can be wired to the checked-out version without hiding
        # version-specific flags inside the paper code.
        command = [
            "go",
            "test",
            "./...",
            "-run",
            "NONE",
            "-bench",
            ".",
        ]
        print(
            f"color={subdb['color']} records={subdb['records']} record_bytes={subdb['record_bytes']} "
            f"db={db_file}"
        )
        print("  command:", " ".join(command))
        if not args.dry_run:
            subprocess.run(command, cwd=simplepir_dir, check=True)


if __name__ == "__main__":
    main()
