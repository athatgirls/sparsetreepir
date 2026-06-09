#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/.tools"
EXTERNAL="$ROOT/external"

TREEPIR_REPO="${TREEPIR_REPO:-https://github.com/PIR-PIXR/TreePIR.git}"
SPIRAL_REPO="${SPIRAL_REPO:-https://github.com/menonsamir/spiral.git}"
YPIR_REPO="${YPIR_REPO:-https://github.com/menonsamir/ypir.git}"
VBPIR_REPO="${VBPIR_REPO:-https://github.com/mhmughees/vectorized_batchpir.git}"
SEALPIR_REPO="${SEALPIR_REPO:-https://github.com/microsoft/SealPIR.git}"

TREEPIR_COMMIT="${TREEPIR_COMMIT:-930063c5aefc441244abb4890fdf35383f3aa956}"
SPIRAL_COMMIT="${SPIRAL_COMMIT:-361ee47f92214d4fcd03c4205c9c2729e8369afb}"
YPIR_COMMIT="${YPIR_COMMIT:-a73e550a469605c2fa23945a4d96c20fb2f4a839}"
VBPIR_COMMIT="${VBPIR_COMMIT:-1a81869e28ca2258f07e32feef063413633e3bae}"
SEALPIR_COMMIT="${SEALPIR_COMMIT:-cf55f10be7bffba4e78d5ba32764284ac828d6cd}"

mkdir -p "$TOOLS" "$EXTERNAL"

if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y \
    git curl unzip python3 python3-venv python3-pip \
    build-essential cmake ninja-build pkg-config clang \
    libssl-dev libgmp-dev default-jdk
  if [ "${INSTALL_DOCKER:-0}" = "1" ]; then
    sudo apt-get install -y docker.io
  fi
fi

clone_or_update() {
  local repo="$1"
  local dest="$2"
  local commit="$3"
  if [ ! -d "$dest/.git" ]; then
    rm -rf "$dest"
    git clone "$repo" "$dest"
  else
    git -C "$dest" fetch --all --tags
  fi
  if [ -n "$commit" ]; then
    git -C "$dest" checkout "$commit"
  fi
}

clone_or_update "$TREEPIR_REPO" "$EXTERNAL/TreePIR-main" "$TREEPIR_COMMIT"
clone_or_update "$SPIRAL_REPO" "$TOOLS/spiral" "$SPIRAL_COMMIT"
clone_or_update "$YPIR_REPO" "$TOOLS/ypir" "$YPIR_COMMIT"
clone_or_update "$VBPIR_REPO" "$TOOLS/vectorized_batchpir" "$VBPIR_COMMIT"
clone_or_update "$SEALPIR_REPO" "$TOOLS/SealPIR" "$SEALPIR_COMMIT"

echo
echo "Extra backend sources are ready."
echo "TreePIR artifact: $EXTERNAL/TreePIR-main"
echo "Spiral:          $TOOLS/spiral"
echo "YPIR:            $TOOLS/ypir"
echo "VBPIR:           $TOOLS/vectorized_batchpir"
echo "SealPIR:         $TOOLS/SealPIR"
echo
echo "Next checks:"
echo "  python scripts/check_linux_backend_readiness.py"
echo "  python scripts/run_official_treepir_perfectized_baseline.py"
echo
echo "Heavy builds are not run automatically. Spiral, VBPIR, and SealPIRplus"
echo "need backend-specific build steps and may require Docker, SEAL, vcpkg,"
echo "gRPC/Protobuf, or AVX-512 hardware."
