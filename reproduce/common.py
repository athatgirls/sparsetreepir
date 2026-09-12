"""Shared helpers for the portable artifact entry points (Python standard library)."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL = "tifs_external_extension_20260911"
SIMPLE = "tifs_simplepir_extension_20260911"
CASES = ["uniform_n1000", "uniform_n10000", "uniform_n100000",
         "prefix64_n10000", "cluster90_n10000", "complete_h10", "complete_h14"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_output(path, fresh=True):
    path = Path(path).expanduser().resolve()
    for protected in (ROOT / "examples", ROOT / "scripts", ROOT / "paper-results",
                      ROOT / "reproduce", ROOT / "docs"):
        if path == protected or protected in path.parents:
            raise ValueError(f"Output must be outside the checked-in evidence/source directories: {path}")
    if path == ROOT or path in ROOT.parents:
        raise ValueError("Output must be a dedicated directory")
    path.mkdir(parents=True, exist_ok=not fresh)
    return path


def module(name):
    path = ROOT / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location("artifact_" + name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def invoke(name, args):
    command = [sys.executable, str(ROOT / "scripts" / (name + ".py")), *map(str, args)]
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def linux_required():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("Native builds and benchmark runners require Linux; frozen verification is portable.")


def thread_environment():
    return dict(os.environ, GOMAXPROCS="1", OMP_NUM_THREADS="1",
                OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", CGO_ENABLED="1")
