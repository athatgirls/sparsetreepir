#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"

SIMPLEPIR_REPO="${SIMPLEPIR_REPO:-https://github.com/ahenzinger/simplepir.git}"
PIANO_REPO="${PIANO_REPO:-https://github.com/wuwuz/Piano-PIR-new.git}"
SIMPLEPIR_COMMIT="${SIMPLEPIR_COMMIT:-e9020b03bf2872c75b8954e749e32408b5db87ed}"
PIANO_COMMIT="${PIANO_COMMIT:-f7107cfadc15a0ac3df20f0bc64f126bf359b702}"

mkdir -p "$TOOLS/simplepir" "$TOOLS"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y git python3 python3-venv python3-pip golang-go gcc g++ openjdk-21-jre \
    texlive-latex-extra latexmk poppler-utils
fi

if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT/requirements-experiments.txt"

if [ ! -d "$TOOLS/simplepir/simplepir-main/.git" ]; then
  rm -rf "$TOOLS/simplepir/simplepir-main"
  git clone "$SIMPLEPIR_REPO" "$TOOLS/simplepir/simplepir-main"
else
  git -C "$TOOLS/simplepir/simplepir-main" fetch --all --tags
fi
if [ -n "$SIMPLEPIR_COMMIT" ]; then
  git -C "$TOOLS/simplepir/simplepir-main" checkout "$SIMPLEPIR_COMMIT"
fi
mkdir -p "$TOOLS/simplepir/simplepir-main/eval"
cp "$ROOT/backend/simplepir/smt_full_backend.go" "$TOOLS/simplepir/simplepir-main/eval/smt_full_backend.go"

if [ ! -d "$TOOLS/piano-pir-new/.git" ]; then
  rm -rf "$TOOLS/piano-pir-new"
  git clone "$PIANO_REPO" "$TOOLS/piano-pir-new"
else
  git -C "$TOOLS/piano-pir-new" fetch --all --tags
fi
if [ -n "$PIANO_COMMIT" ]; then
  git -C "$TOOLS/piano-pir-new" checkout "$PIANO_COMMIT"
fi
mkdir -p "$TOOLS/piano-pir-new/eval"
cp "$ROOT/backend/piano/smt_layout_benchmark.go" "$TOOLS/piano-pir-new/eval/smt_layout_benchmark.go"

echo "Linux experiment dependencies are ready."
echo "Activate Python with: source .venv/bin/activate"
