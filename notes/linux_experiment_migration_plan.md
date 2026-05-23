# Linux experiment migration plan

## Recommendation

Use a hybrid workflow:

1. Put the reproducible experiment source in a private GitHub repository.
2. Clone the repository on Linux and rebuild backend toolchains there.
3. Transfer only large or frozen generated artifacts with `rsync`/`scp`, GitHub Releases, or DVC/Git LFS if needed.

Do not push the whole working directory as-is. The current tree contains Windows-specific Go/JRE downloads, cached dependencies, generated PDFs, and backend layout dumps. Those are either large, machine-specific, or easy to regenerate.

## Put in GitHub

- `scripts/`
- `datasets/`
- `examples/*.csv` final result summaries
- `figures/` source figures and final paper figures
- `manuscripts/`
- `notes/` experiment notes and migration notes
- `PROJECT_STRUCTURE.md`
- `requirements-experiments.txt`

The current datasets are small enough for normal Git. The largest CSV files are around 1 MB, so Git LFS is not necessary for them.

## Do not put in GitHub

- `.gocache/`
- `.gomodcache/`
- `.gopath/`
- `.pydeps/`
- `.tmp_pip/`
- `.tools/`
- `build/`
- `previews/`
- `external/go/`
- `external/jre21/`
- `external/TreePIR-main/`
- `external/*.zip`
- `examples/*_layouts/` unless you intentionally want to freeze generated SimplePIR layouts

These are covered by the new `.gitignore`.

## Linux setup

On the Linux machine, the shortest path is:

```bash
git clone <your-private-repo-url> sparsetreepir
cd sparsetreepir
bash scripts/setup_linux_experiment_deps.sh
source .venv/bin/activate
```

The setup script installs system packages on apt-based Linux, creates a Python venv, installs Python dependencies, clones SimplePIR and PIANO into `.tools/`, and copies the SparseTreePIR backend runners into those checkouts.

Manual setup is:

```bash
git clone <your-private-repo-url> sparsetreepir
cd sparsetreepir

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-experiments.txt

sudo apt update
sudo apt install -y git golang-go openjdk-21-jre texlive-latex-extra latexmk poppler-utils
```

If the distribution does not provide a new enough Go version for SimplePIR or PIANO, install Go from the official tarball on Linux instead of reusing the Windows `external/go` directory.

## Backend toolchains

Rebuild or fetch these on Linux:

- SimplePIR: `scripts/setup_linux_experiment_deps.sh` clones `https://github.com/ahenzinger/simplepir.git` into `.tools/simplepir/simplepir-main`, checks out `e9020b03bf2872c75b8954e749e32408b5db87ed`, and installs `backend/simplepir/smt_full_backend.go` into its `eval/` directory.
- PIANO: `scripts/setup_linux_experiment_deps.sh` clones `https://github.com/wuwuz/Piano-PIR-new.git` into `.tools/piano-pir-new`, checks out `f7107cfadc15a0ac3df20f0bc64f126bf359b702`, and installs `backend/piano/smt_layout_benchmark.go` into its `eval/` directory.
- TreePIR artifact: fetch on Linux if needed for the perfectized baseline. Do not commit the Windows JRE or downloaded zip.
- Fuel SMT test generation: the converted `datasets/fuel_smt_test_workload.csv` is enough for the paper run. Keep the upstream generator as a documented external source unless you need to regenerate it.

## First smoke runs on Linux

Run the structural suite first:

```bash
python scripts/run_real_smt_final_experiment_suite.py
```

Then run backend evidence after SimplePIR is installed:

```bash
python scripts/run_real_smt_final_experiment_suite.py --run-simplepir
python scripts/run_real_smt_multi_pir_pbc_battle.py
```

Then run PIANO after the PIANO artifact is installed:

```bash
python scripts/run_piano_wsl_backend_from_layouts.py --queries 5 --timeout 300
```

## Transfer alternatives

- Best for code and small datasets: GitHub private repository.
- Best for one-time full directory transfer: `rsync -av --exclude-from <exclude-file>`.
- Best for frozen large generated results: GitHub Releases, OSF, Zenodo, or a cloud drive.
- Best for versioned large data: DVC or Git LFS, but only if data grows beyond normal Git size.
- Best for exact reproducibility: Docker or Apptainer image with Go, Java, Python, and LaTeX preinstalled.

## Practical rule

Use GitHub for things a reviewer should read, audit, or rerun. Use transfer/storage tools for things that are large, binary, generated, or machine-specific.
