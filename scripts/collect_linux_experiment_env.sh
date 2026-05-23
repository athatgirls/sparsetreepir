#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_TXT="${1:-$ROOT/examples/linux_experiment_environment.txt}"
OUT_CSV="${2:-$ROOT/examples/linux_experiment_environment.csv}"

mkdir -p "$(dirname "$OUT_TXT")" "$(dirname "$OUT_CSV")"

capture() {
  local label="$1"
  shift
  {
    echo "## $label"
    "$@" 2>&1 || true
    echo
  } >>"$OUT_TXT"
}

rm -f "$OUT_TXT"
{
  echo "# Linux Experiment Environment"
  echo "captured_at=$(date -Is)"
  echo "repo=$(git -C "$ROOT" rev-parse --show-toplevel 2>/dev/null || true)"
  echo "repo_head=$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
  echo
} >>"$OUT_TXT"

capture "uname" uname -a
capture "os-release" bash -lc 'cat /etc/os-release'
capture "cpu" lscpu
capture "memory" free -h
capture "disk" df -h "$ROOT"
capture "python" python --version
capture "go" go version
capture "gcc" gcc --version
capture "g++" g++ --version
capture "java" java -version
capture "cmake" cmake --version
capture "simplepir commit" bash -lc "git -C '$ROOT/.tools/simplepir/simplepir-main' rev-parse HEAD"
capture "piano commit" bash -lc "git -C '$ROOT/.tools/piano-pir-new' rev-parse HEAD"

{
  echo "key,value"
  echo "captured_at,$(date -Is)"
  echo "repo_head,$(git -C "$ROOT" rev-parse HEAD 2>/dev/null || true)"
  echo "kernel,\"$(uname -a | sed 's/"/""/g')\""
  echo "python,\"$(python --version 2>&1 | sed 's/"/""/g')\""
  echo "go,\"$(go version 2>&1 | sed 's/"/""/g')\""
  echo "gcc,\"$(gcc --version 2>&1 | head -n 1 | sed 's/"/""/g')\""
  echo "g++,\"$(g++ --version 2>&1 | head -n 1 | sed 's/"/""/g')\""
  echo "java,\"$(java -version 2>&1 | head -n 1 | sed 's/"/""/g')\""
  echo "cmake,\"$(cmake --version 2>&1 | head -n 1 | sed 's/"/""/g')\""
  echo "simplepir_commit,$(git -C "$ROOT/.tools/simplepir/simplepir-main" rev-parse HEAD 2>/dev/null || true)"
  echo "piano_commit,$(git -C "$ROOT/.tools/piano-pir-new" rev-parse HEAD 2>/dev/null || true)"
  echo "avx512_present,$(lscpu | grep -qi avx512 && echo yes || echo no)"
} >"$OUT_CSV"

echo "environment_text=$OUT_TXT"
echo "environment_csv=$OUT_CSV"
