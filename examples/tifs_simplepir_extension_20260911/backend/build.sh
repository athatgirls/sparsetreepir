#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
export CGO_ENABLED=1
export GOMAXPROCS=1
export OMP_NUM_THREADS=1
go build -trimpath -o build/simplepir_proof_bench .
go version > build/toolchain.txt
gcc --version >> build/toolchain.txt
sha256sum build/simplepir_proof_bench > build/binary.sha256
