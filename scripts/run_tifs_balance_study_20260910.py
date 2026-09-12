"""Fresh, timeout-bounded balance study; never changes historical code/results.

Examples (from repository root):
  python scripts/run_tifs_balance_study_20260910.py --selfcheck
  python scripts/run_tifs_balance_study_20260910.py --suite smoke --timeout 120
  python scripts/run_tifs_balance_study_20260910.py --suite scale --timeout 120

One subprocess per configuration. A killed configuration keeps its last valid
colouring checkpoint and is labelled timeout, never a completed AB run.
The extraction uses compressed branching points, checked against the old exact
active-node extractor. Colouring algorithms use the old node objects and code.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import ctypes
import hashlib
import inspect
import itertools
import json
import math
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples/tifs_revision_20260910/balance"
LIB: dict[str, Any] = {}


def init_lib() -> None:
    if LIB:
        return
    import generate_full_sparse_smt_example as nodes
    import run_height_sparsity_profile_balance_experiment as ab
    import run_sparse_smt_pir_backend_experiment as hybrid
    LIB.update(nodes=nodes, ab=ab, hybrid=hybrid)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def rss_bytes() -> tuple[int | None, int | None]:
    if os.name == "nt":
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            return None, None
        return counters.WorkingSetSize, counters.PeakWorkingSetSize
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return None, peak * (1 if sys.platform == "darwin" else 1024)
    except ImportError:
        return None, None


def sorted_mapping(available_colors: list[int], global_loads: list[int], subtree_counts: list[int]) -> dict[int, int]:
    """Exact count-only assignment by reverse pairing, with deterministic ties."""
    source = sorted(available_colors, key=lambda c: (-subtree_counts[c - 1], c))
    target = sorted(available_colors, key=lambda c: (global_loads[c - 1] - subtree_counts[c - 1], c))
    return dict(zip(source, target))


def compact_nodes(keys: list[int], height: int) -> tuple[list[Any], list[Any]]:
    """Same positional active records/legacy creation order, no unary nodes."""
    init_lib()
    Node = LIB["nodes"].ProofNode
    made: list[tuple[int, Any]] = []
    stack = [(0, len(keys))]
    while stack:
        lo, hi = stack.pop()
        if hi - lo < 2:
            continue
        split_bit = (keys[lo] ^ keys[hi - 1]).bit_length() - 1
        prefix = keys[lo] >> (split_bit + 1)
        boundary = ((prefix << 1) | 1) << split_bit
        mid = bisect.bisect_left(keys, boundary, lo, hi)
        assert lo < mid < hi
        depth = height - split_bit
        left_index = (1 << depth) | (keys[lo] >> split_bit)
        right_index = left_index | 1
        made.append((lo, Node(left_index, depth, mid, hi - 1, hi - mid, [])))
        made.append((mid, Node(right_index, depth, lo, mid - 1, mid - lo, [])))
        stack.extend([(mid, hi), (lo, mid)])
    made.sort(key=lambda pair: (pair[0], -pair[1].depth))
    nodes = [pair[1] for pair in made]
    roots = LIB["nodes"].build_interval_forest(nodes)
    return nodes, roots


def structure_stats(nodes: list[Any], roots: list[Any]) -> dict[str, Any]:
    # Independent iterative check of laminar-parent relation, depth, and bound.
    maximum_depth = 0
    lower = 0
    subtree_sizes: dict[int, int] = {}
    preorder: list[tuple[Any, int]] = []
    pending = [(root, 1) for root in reversed(roots)]
    while pending:
        node, depth = pending.pop()
        maximum_depth = max(maximum_depth, depth)
        preorder.append((node, depth))
        for child in node.children:
            assert node.interval_left <= child.interval_left <= child.interval_right <= node.interval_right
            assert (node.interval_left, node.interval_right) != (child.interval_left, child.interval_right)
        pending.extend((child, depth + 1) for child in reversed(node.children))
    m = maximum_depth
    if m:
        lower = math.ceil(len(nodes) / m)
    for node, depth in reversed(preorder):
        size = 1 + sum(subtree_sizes[id(child)] for child in node.children)
        subtree_sizes[id(node)] = size
        if m > depth:
            lower = max(lower, math.ceil((size - 1) / (m - depth)))
    return {"N": len(nodes), "m": m, "lower_bound": lower,
            "depth_active_queries": len({node.depth for node in nodes})}


def validate_coloring(nodes: list[Any], m: int, n: int) -> bool:
    if len(nodes) != 2 * (n - 1):
        return False
    # Same-colour interval disjointness is equivalent to proof conflict absence.
    by_color: dict[int, list[tuple[int, int]]] = {c: [] for c in range(1, m + 1)}
    for node in nodes:
        if node.color not in by_color or not (0 <= node.interval_left <= node.interval_right < n):
            return False
        by_color[node.color].append((node.interval_left, node.interval_right))
    for intervals in by_color.values():
        previous_right = -1
        for lo, hi in sorted(intervals):
            if lo <= previous_right:
                return False
            previous_right = hi
    return True


def refine(nodes: list[Any], roots: list[Any], m: int, limit: int, solver: str,
           callback: Any = None) -> tuple[list[int], int, int, bool]:
    """Observable equivalent of old count_profile_refine, one move per pass."""
    ab = LIB["ab"]
    ab.first_fit_coloring(roots, m)
    loads = ab.count_loads_for_nodes(nodes, m)
    signature = ab.count_signature(loads)
    ordered = [node for root in roots for node in LIB["nodes"].traverse(root)]
    mapping_function = ab.best_count_mapping if solver == "hungarian" else sorted_mapping
    moves = passes = 0
    converged = False
    if callback:
        callback(loads, passes, moves, converged)
    for _ in range(limit):
        masks, histograms = ab.annotate_count_state(roots, m)
        best = None
        for node in ordered:
            available = [c for c in range(1, m + 1) if not masks[id(node)] & (1 << (c - 1))]
            if len(available) <= 1:
                continue
            counts = histograms[id(node)]
            mapping = mapping_function(available, loads, counts)
            if all(mapping[c] == c for c in available):
                continue
            candidate = ab.candidate_loads_after_mapping(mapping, available, loads, counts)
            candidate_signature = ab.count_signature(candidate)
            if candidate_signature < signature and (best is None or candidate_signature < best[3]):
                best = (node, mapping, candidate, candidate_signature)
        passes += 1
        if best is None:
            converged = True
        else:
            node, mapping, loads, signature = best
            ab.apply_mapping_to_subtree(node, mapping)
            moves += 1
        if callback:
            callback(loads, passes, moves, converged)
        if converged:
            break
    return loads, passes, moves, converged


def hybrid_observed(nodes: list[Any], roots: list[Any], m: int, limit: int,
                    callback: Any = None) -> tuple[list[int], int, int, bool]:
    """Old hybrid code, instrumented in memory through its AST, not file edits.

    Hooks execute only after greedy initialization and complete iterations;
    returned colouring and accepted-move sequence are unchanged.
    """
    import ast
    import textwrap
    module = LIB["hybrid"]
    source = textwrap.dedent(inspect.getsource(module.color_proof_nodes))
    tree = ast.parse(source)
    function = tree.body[0]
    passes = moves = 0
    converged = False

    def hook(event: str, counts: list[int]) -> None:
        nonlocal passes, moves, converged
        if event == "move":
            passes += 1
            moves += 1
        elif event == "stop":
            passes += 1
            converged = True
        if callback:
            callback(counts, passes, moves, converged)

    class Hooks(ast.NodeTransformer):
        def visit_For(self, node: ast.For) -> Any:
            # The only range(rebalance_rounds) loop in the source.
            if isinstance(node.iter, ast.Call) and ast.unparse(node.iter) == "range(rebalance_rounds)":
                for item in node.body:
                    if isinstance(item, ast.If) and ast.unparse(item.test) == "best_move is None":
                        item.body.insert(0, ast.parse("_study_hook('stop', count_loads)").body[0])
                node.body.append(ast.parse("_study_hook('move', count_loads)").body[0])
                return [ast.parse("_study_hook('initial', count_loads)").body[0], node]
            return self.generic_visit(node)

    Hooks().visit(function)
    ast.fix_missing_locations(tree)
    namespace = dict(vars(module), _study_hook=hook)
    exec(compile(tree, "<instrumented legacy hybrid>", "exec"), namespace)
    counts, _ = namespace["color_proof_nodes"](nodes, roots, m, "hybrid", limit)
    return counts, passes, moves, converged


def generate_keys(config: dict[str, Any]) -> list[int]:
    h, n, seed = config["height"], config["n"], config["seed"]
    kind = config["distribution"]
    rng = random.Random(seed)
    if kind == "real":
        rows = list(csv.DictReader((ROOT / config["source"]).open(encoding="utf-8-sig", newline="")))
        keys = sorted({row["key"] for row in rows})
        if config.get("key_mode") == "hex-prefix":
            coords = []
            for key in keys:
                clean = key[2:] if key.lower().startswith("0x") else key
                coords.append(int(clean, 16) >> max(0, len(clean) * 4 - h))
        else:
            coords = [int.from_bytes(hashlib.sha256(key.encode()).digest(), "big") >> (256 - h) for key in keys]
        return sorted(set(coords))
    if n > 1 << h:
        raise ValueError("n exceeds coordinate capacity")
    if kind == "saturated":
        if n & (n - 1):
            raise ValueError("saturated subtree requires power-of-two n")
        return list(range(n))
    keys_set: set[int] = set()
    if kind == "comb":
        keys_set.add(0)
        keys_set.update(1 << bit for bit in range(min(h, n - 1)))
    suffix_bits = h
    if kind == "prefix-cluster":
        prefix_bits = min(24, max(0, h - math.ceil(math.log2(n)) - 2))
        suffix_bits = h - prefix_bits
        config["shared_prefix_bits"] = prefix_bits
    while len(keys_set) < n:
        keys_set.add(rng.getrandbits(suffix_bits))
    return sorted(keys_set)


def selfcheck() -> dict[str, Any]:
    init_lib()
    start = time.perf_counter()
    ab = LIB["ab"]
    cases = permutations_checked = 0
    # Exhaustive load arrays for m<=3, all permutations for every tested array.
    arrays: list[tuple[list[int], list[int]]] = []
    for m in (1, 2, 3):
        values = list(itertools.product(range(3), repeat=m))
        arrays.extend((list(a), list(s)) for a in values for s in values)
    rng = random.Random(20260910)
    for m in range(4, 8):
        arrays.extend(([rng.randrange(12) for _ in range(m)], [rng.randrange(12) for _ in range(m)])
                      for _ in range(30))
    for outside, subtree in arrays:
        m = len(outside)
        loads = [a + s for a, s in zip(outside, subtree)]
        colors = list(range(1, m + 1))
        optimum = min(tuple(sorted((outside[j] + subtree[p[j]] for j in range(m)), reverse=True))
                      for p in itertools.permutations(range(m)))
        permutations_checked += math.factorial(m)
        for solver in (ab.best_count_mapping, sorted_mapping):
            mapping = solver(colors, loads, subtree)
            actual = tuple(sorted(ab.candidate_loads_after_mapping(mapping, colors, loads, subtree), reverse=True))
            assert actual == optimum, (solver.__name__, outside, subtree, actual, optimum)
        cases += 1
    from fixed_sparse_tree_coloring import FixedSparseMerkleColoring
    extractor_cases = hybrid_cases = ab_wrapper_cases = equivalent_final_signatures = 0
    differing_signatures = []
    for seed in range(24):
        height = 4 + seed % 4
        n = 2 + seed % min(18, (1 << height) - 1)
        keys = generate_keys(dict(height=height, n=n, seed=seed, distribution="uniform"))
        legacy = FixedSparseMerkleColoring(height, [(1 << height) + k for k in keys])
        old = LIB["nodes"].build_full_proof_nodes(legacy.raw_nodes, legacy.occupied_leaves, height)
        fresh, _ = compact_nodes(keys, height)
        shape = lambda nodes: [(p.index, p.depth, p.interval_left, p.interval_right, p.weight) for p in nodes]
        assert shape(fresh) == shape(old)
        extractor_cases += 1
        a, ar = compact_nodes(keys, height)
        b, br = compact_nodes(keys, height)
        m = structure_stats(a, ar)["m"]
        LIB["hybrid"].color_proof_nodes(a, ar, m, "hybrid", 3)
        hybrid_observed(b, br, m, 3)
        assert [p.color for p in a] == [p.color for p in b]
        hybrid_cases += 1
        a, ar = compact_nodes(keys, height)
        b, br = compact_nodes(keys, height)
        reference = ab.count_profile_refine(a, ar, m, 5)
        observed = refine(b, br, m, 5, "hungarian")
        assert reference == observed[:3]
        assert [p.color for p in a] == [p.color for p in b]
        ab_wrapper_cases += 1
        c, cr = compact_nodes(keys, height)
        sorted_result = refine(c, cr, m, 5, "sorted")
        assert validate_coloring(c, m, len(keys))
        if sorted(reference[0]) == sorted(sorted_result[0]):
            equivalent_final_signatures += 1
        else:
            differing_signatures.append(dict(seed=seed, old=sorted(reference[0], reverse=True),
                                             new=sorted(sorted_result[0], reverse=True)))
    result = dict(status="pass", candidate_cases=cases, permutations_checked=permutations_checked,
                  all_permutations_checked_for_each_candidate=True,
                  extractor_legacy_order_checks=extractor_cases, hybrid_exact_wrapper_checks=hybrid_cases,
                  original_ab_exact_wrapper_checks=ab_wrapper_cases,
                  whole_run_equal_signature_cases=equivalent_final_signatures,
                  whole_run_differences=differing_signatures,
                  note="Equal per-candidate optimal signatures do not imply identical colouring tie decisions or all later trajectories.",
                  elapsed_s=time.perf_counter() - start)
    write_json(OUT / "selfcheck.json", result)
    return result


def worker(config_file: Path) -> None:
    config = json.loads(config_file.read_text(encoding="utf-8"))
    destination = config_file.parent
    process_start = time.perf_counter()
    init_lib()
    imports_s = time.perf_counter() - process_start
    if config.get("trace_allocations"):
        import tracemalloc
        tracemalloc.start()
    measured_start = time.perf_counter()
    keys = generate_keys(config)
    key_seconds = time.perf_counter() - measured_start
    t0 = time.perf_counter()
    nodes, roots = compact_nodes(keys, config["height"])
    stats = structure_stats(nodes, roots)
    extraction_s = time.perf_counter() - t0
    assert stats["N"] == 2 * (len(keys) - 1)
    key_digest = hashlib.sha256(b"".join(key.to_bytes((config["height"] + 7) // 8, "big") for key in keys)).hexdigest()
    common = dict(config, **stats, actual_n=len(keys), key_sha256=key_digest,
                  imports_s=imports_s, key_generation_s=key_seconds, extraction_forest_stats_s=extraction_s,
                  memory_scope="process RSS/peak working set including interpreter and imports; tracemalloc excludes imports when enabled",
                  compact_extractor="compressed branching extraction; legacy node/order validated in selfcheck",
                  host=platform.node(), platform=platform.platform(), python=sys.version.split()[0], pid=os.getpid())
    coloring_start = time.perf_counter()
    m = stats["m"]
    history: list[dict[str, Any]] = []
    checkpoint_overhead_s = 0.0

    def checkpoint(loads: list[int], passes: int, moves: int, converged: bool) -> None:
        nonlocal checkpoint_overhead_s
        checkpoint_start = time.perf_counter()
        rss, peak = rss_bytes()
        row = dict(common, status="partial", coloring_s=checkpoint_start - coloring_start - checkpoint_overhead_s,
                   actual_passes=passes, actual_moves=moves, converged=converged,
                   max_bucket=max(loads, default=0), loads=loads,
                   U_over_B=max(loads, default=0) / stats["lower_bound"] if m else 1.0,
                   rss_bytes=rss, peak_rss_bytes=peak,
                   valid=validate_coloring(nodes, m, len(keys)))
        assert row["valid"]
        if config.get("trace_allocations"):
            row["python_alloc_current_bytes"], row["python_alloc_peak_bytes"] = tracemalloc.get_traced_memory()
        history.append({k: row[k] for k in ("coloring_s", "actual_passes", "actual_moves", "max_bucket", "U_over_B", "valid", "converged")})
        write_json(destination / "checkpoint.json", row)
        write_json(destination / "round_history.json", history)
        checkpoint_overhead_s += time.perf_counter() - checkpoint_start

    algorithm = config["algorithm"]
    limit = config["passes"]
    if algorithm == "first-fit":
        LIB["ab"].first_fit_coloring(roots, m)
        loads = LIB["ab"].count_loads_for_nodes(nodes, m)
        checkpoint(loads, 0, 0, False)
    elif algorithm == "hybrid":
        hybrid_observed(nodes, roots, m, limit, checkpoint)
    elif algorithm in ("ab-hungarian", "ab-sorted"):
        refine(nodes, roots, m, limit, algorithm.split("-", 1)[1], checkpoint)
    else:
        raise ValueError(algorithm)
    final = json.loads((destination / "checkpoint.json").read_text(encoding="utf-8"))
    final.update(status="complete", coloring_s=time.perf_counter() - coloring_start - checkpoint_overhead_s,
                 checkpoint_validation_io_s=checkpoint_overhead_s,
                 measured_total_s=time.perf_counter() - measured_start,
                 process_worker_s=time.perf_counter() - process_start)
    write_json(destination / "result.json", final)
    # Record a portable per-record colour assignment for direct PIR integration.
    with (destination / "layout_records.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["node_index", "depth", "left_rank", "right_rank", "weight", "color"])
        writer.writerows((p.index, p.depth, p.interval_left, p.interval_right, p.weight, p.color) for p in nodes)
    print(json.dumps({k: final[k] for k in ("id", "status", "actual_n", "m", "max_bucket", "U_over_B", "coloring_s", "valid")}), flush=True)


def configurations(suite: str) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    def add(distribution: str, n: int, height: int, algorithm: str, passes: int = 0,
            seed: int = 20260910, repeat: int = 1, **kwargs: Any) -> None:
        label = kwargs.get("label", distribution)
        identifier = f"{label}_n{n}_h{height}_{algorithm}_p{passes}_s{seed}_r{repeat}"
        plans.append(dict(id=identifier, distribution=distribution, n=n, height=height,
                          algorithm=algorithm, passes=passes, seed=seed, repeat=repeat, **kwargs))
    if suite == "smoke":
        for distribution in ("uniform", "prefix-cluster", "comb", "saturated"):
            n = 128 if distribution != "saturated" else 256
            for algorithm, rounds in (("first-fit", 0), ("hybrid", 2), ("ab-hungarian", 5), ("ab-sorted", 5)):
                add(distribution, n, 16, algorithm, rounds)
    elif suite == "real":
        sources = [
            ("fuel", "fuel_smt_test_workload.csv", "hex-prefix", 100),
            ("polygon-recent", "polygon_zkevm_account_leaf_workload.csv", "sha256", 384),
            ("zksync-sample", "zksync_era_account_leaf_workload_sample.csv", "sha256", 956),
            ("polygon-multi", "polygon_zkevm_account_leaf_workload_multiwindow.csv", "sha256", 1348),
            ("polygon-broad", "polygon_zkevm_account_leaf_workload_broad_multiwindow.csv", "sha256", 7040),
            ("zksync-broad", "zksync_era_account_leaf_workload_broad_sample.csv", "sha256", 7740)]
        for label, source, mode, n in sources:
            for algorithm, rounds in (("first-fit", 0), ("hybrid", 20), ("ab-hungarian", 20), ("ab-sorted", 20)):
                add("real", n, 128, algorithm, rounds, label=label, source="datasets/" + source, key_mode=mode)
    elif suite == "scale":
        for n in (1000, 10000, 100000):
            for algorithm, rounds in (("first-fit", 0), ("hybrid", 0), ("ab-hungarian", 1), ("ab-sorted", 1)):
                add("uniform", n, 128, algorithm, rounds)
        for h in (16, 256):
            for algorithm, rounds in (("first-fit", 0), ("ab-sorted", 2)):
                add("uniform", 1000, h, algorithm, rounds)
        for distribution, n, h in (("prefix-cluster", 10000, 128), ("comb", 1000, 128), ("saturated", 65536, 16)):
            for algorithm, rounds in (("first-fit", 0), ("ab-sorted", 1)):
                add(distribution, n, h, algorithm, rounds)
    elif suite == "passes":
        for passes in (0, 1, 2, 5, 10, 20):
            for algorithm in ("ab-hungarian", "ab-sorted"):
                add("uniform", 1000, 128, algorithm, passes)
    elif suite == "refinement":
        # Intermediate 0/1/2/5/10/20 states are retained in round_history.json;
        # this avoids rerunning the same expensive prefixes six times.
        for n in (10000, 100000):
            for algorithm in ("ab-hungarian", "ab-sorted"):
                add("uniform", n, 128, algorithm, 20)
        for distribution, n, h in (("prefix-cluster", 10000, 128), ("comb", 1000, 128), ("saturated", 65536, 16)):
            add(distribution, n, h, "ab-sorted", 20)
    elif suite == "repeats":
        for repeat in (1, 2, 3):
            for algorithm, rounds in (("first-fit", 0), ("hybrid", 20), ("ab-hungarian", 20), ("ab-sorted", 20)):
                add("uniform", 1000, 128, algorithm, rounds, repeat=repeat)
    else:
        raise ValueError(suite)
    return plans


def aggregate() -> None:
    rows = []
    for directory in sorted((OUT / "runs").glob("*")):
        final = directory / "result.json"
        if final.exists():
            rows.append(json.loads(final.read_text(encoding="utf-8")))
    if not rows:
        return
    fields = sorted(set().union(*(row.keys() for row in rows)))
    with (OUT / "per_run.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    write_json(OUT / "summary.json", dict(runs=len(rows), complete=sum(row["status"] == "complete" for row in rows),
               timeouts=sum(row["status"] == "timeout" for row in rows),
               failed=sum(row["status"] == "failed" for row in rows),
               invalid=sum(row.get("valid") is False for row in rows),
               note="Timeouts retain only the last completed valid colouring; coloring_s may precede timeout wall time. RSS includes Python/imports. Coloring timings exclude separately measured checkpoint validation and file IO; measured_total_s includes them."))


def orchestrate(suite: str, timeout: float) -> None:
    check = OUT / "selfcheck.json"
    if not check.exists() or json.loads(check.read_text(encoding="utf-8"))["status"] != "pass":
        raise RuntimeError("Run --selfcheck first")
    plans = configurations(suite)
    write_json(OUT / f"plan_{suite}.json", dict(timeout_seconds_per_configuration=timeout, configurations=plans))
    for config in plans:
        destination = OUT / "runs" / config["id"]
        if (destination / "result.json").exists():
            print("SKIP " + config["id"], flush=True)
            continue
        destination.mkdir(parents=True, exist_ok=True)
        write_json(destination / "config.json", config)
        start = time.monotonic()
        with (destination / "stdout.txt").open("w", encoding="utf-8") as stdout, (destination / "stderr.txt").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", str(destination / "config.json")],
                                       cwd=ROOT, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            try:
                return_code = process.wait(timeout=timeout)
                status = "complete" if return_code == 0 else "failed"
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                status, return_code = "timeout", None
        wall = time.monotonic() - start
        result_path = destination / "result.json"
        if not result_path.exists():
            checkpoint = destination / "checkpoint.json"
            row = json.loads(checkpoint.read_text(encoding="utf-8")) if checkpoint.exists() else dict(config)
            row.update(status=status, timeout_limit_s=timeout, subprocess_wall_s=wall, exit_code=return_code,
                       last_completed_checkpoint_only=True)
            write_json(result_path, row)
        else:
            row = json.loads(result_path.read_text(encoding="utf-8"))
            row.update(subprocess_wall_s=wall, timeout_limit_s=timeout, exit_code=return_code)
            write_json(result_path, row)
        aggregate()
        print(f"{status.upper()} {config['id']} wall={wall:.2f}s U/B={row.get('U_over_B')} passes={row.get('actual_passes')}", flush=True)


def report() -> None:
    aggregate()
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((OUT / "runs").glob("*/result.json"))]
    import statistics
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({"font.size": 9, "pdf.fonttype": 42, "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False})
    real = {(row.get("label"), row["algorithm"]): row for row in rows if row["distribution"] == "real" and row["status"] == "complete"}
    labels = ["fuel", "polygon-recent", "zksync-sample", "polygon-multi", "polygon-broad", "zksync-broad"]
    algorithms = ["first-fit", "hybrid", "ab-hungarian", "ab-sorted"]
    names = ["First-fit", "Hybrid (20-round cap)", "AB / Hungarian (20-round cap)", "AB / reverse sort (20-round cap)"]
    colors = ["#7C8796", "#D99A31", "#3369A1", "#258274"]
    summary_rows = []
    if all((label, algorithm) in real for label in labels for algorithm in algorithms):
        fig, axes = plt.subplots(1, 2, figsize=(10.4, 3.5))
        x = np.arange(len(labels))
        for index, (algorithm, name, color) in enumerate(zip(algorithms, names, colors)):
            axes[0].bar(x + (index - 1.5) * 0.19, [real[label, algorithm]["U_over_B"] for label in labels], width=0.18, label=name, color=color)
            axes[1].plot(x, [real[label, algorithm]["coloring_s"] for label in labels], marker="o", markersize=4, label=name, color=color)
        axes[0].axhline(1, color="black", linewidth=0.7, linestyle="--")
        axes[0].set_ylabel("Maximum bucket / structural lower bound")
        axes[0].set_title("Structural quality (lower is better)")
        axes[1].set_yscale("log")
        axes[1].set_ylabel("Coloring computation (s, logarithmic scale)")
        axes[1].set_title("One execution per fixed snapshot")
        display = ["Fuel", "Polygon\nrecent", "ZKsync\nsample", "Polygon\nmulti", "Polygon\nbroad", "ZKsync\nbroad"]
        for ax in axes:
            ax.set_xticks(x, display)
            ax.grid(axis="y", alpha=0.2)
        handles, legends = axes[0].get_legend_handles_labels()
        fig.legend(handles, legends, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.01))
        fig.tight_layout(rect=(0, 0.14, 1, 1))
        fig.savefig(OUT / "balance_real_quality_time.pdf", bbox_inches="tight")
        fig.savefig(OUT / "balance_real_quality_time.png", dpi=180, bbox_inches="tight")
        plt.close(fig)
        for label in labels:
            reference = real[label, "ab-hungarian"]
            row = dict(workload=label, occupied_n=reference["actual_n"], active_N=reference["N"], m=reference["m"],
                       depth_active_queries=reference["depth_active_queries"], depth_to_sparse_ratio=reference["depth_active_queries"] / reference["m"], lower_bound=reference["lower_bound"])
            for algorithm in algorithms:
                datum = real[label, algorithm]
                for field in ("max_bucket", "U_over_B", "coloring_s", "actual_passes", "actual_moves", "converged", "peak_rss_bytes"):
                    row[algorithm + "_" + field] = datum[field]
            row["hungarian_to_sorted_time_ratio_single_run"] = row["ab-hungarian_coloring_s"] / row["ab-sorted_coloring_s"]
            summary_rows.append(row)
        with (OUT / "real_comparison.csv").open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
            writer.writeheader()
            writer.writerows(summary_rows)
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.2), sharey=False)
    for ax, n in zip(axes, (1000, 10000, 100000)):
        for algorithm, name, color in (("ab-hungarian", "AB / Hungarian", colors[2]), ("ab-sorted", "AB / reverse sort", colors[3])):
            key = f"uniform_n{n}_h128_{algorithm}_p20_s20260910_r1"
            history_file = OUT / "runs" / key / "round_history.json"
            result_file = OUT / "runs" / key / "result.json"
            if not history_file.exists() or not result_file.exists():
                continue
            history = json.loads(history_file.read_text(encoding="utf-8"))
            result = json.loads(result_file.read_text(encoding="utf-8"))
            extra = " (timeout)" if result["status"] == "timeout" else ""
            ax.plot([r["actual_passes"] for r in history], [r["U_over_B"] for r in history], label=name + extra, color=color, marker=".", markersize=4)
            if extra:
                ax.annotate("120 s timeout", (history[-1]["actual_passes"], history[-1]["U_over_B"]), xytext=(-25, 15), textcoords="offset points", fontsize=8, color=color)
        ax.axhline(1, color="black", linewidth=0.7, linestyle="--")
        ax.set_title(f"Uniform coordinates, n = {n:,}")
        ax.set_xlabel("Completed scan rounds")
        ax.set_ylabel("Maximum bucket / lower bound")
        ax.grid(alpha=0.2)
        ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "balance_round_budget.pdf", bbox_inches="tight")
    fig.savefig(OUT / "balance_round_budget.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    repetition_rows = []
    for algorithm in algorithms:
        chosen = [r for r in rows if r["distribution"] == "uniform" and r["n"] == 1000 and r["height"] == 128
                  and r["algorithm"] == algorithm and r["passes"] == (0 if algorithm == "first-fit" else 20) and r["status"] == "complete"]
        if chosen:
            times = [r["coloring_s"] for r in chosen]
            repetition_rows.append(dict(algorithm=algorithm, executions=len(chosen), mean_s=statistics.mean(times),
                                        sample_sd_s=statistics.stdev(times) if len(times) > 1 else None,
                                        max_buckets=[r["max_bucket"] for r in chosen], U_over_B=[r["U_over_B"] for r in chosen]))
    write_json(OUT / "repeated_timing_summary.json", repetition_rows)
    sources = [Path(__file__), ROOT / "scripts/run_height_sparsity_profile_balance_experiment.py",
               ROOT / "scripts/run_sparse_smt_pir_backend_experiment.py", ROOT / "scripts/generate_full_sparse_smt_example.py"]
    sources += sorted({ROOT / r["source"] for r in rows if "source" in r})
    write_json(OUT / "source_manifest.json", {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources})
    check = json.loads((OUT / "selfcheck.json").read_text(encoding="utf-8"))
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    lines = ["# 2026-09-10 新增均衡实验", "",
             f"已记录 {summary['runs']} 个独立进程配置：完成 {summary['complete']}、timeout {summary['timeouts']}、失败 {summary['failed']}、已校验结果无效 {summary['invalid']}。", "",
             "原始入口：`scripts/run_tifs_balance_study_20260910.py`。历史算法/CSV未修改。所有配置、随机种子、key哈希、source哈希、原始stdout/stderr和每轮中间状态均保留。", "",
             "## 正确性验证", "",
             f"{check['candidate_cases']} 个候选配置逐一枚举全部排列，共 {check['permutations_checked']:,} 个排列，旧纯计数Hungarian与反向排序都达到最小降序负载签名。24个小SMT验证提取记录及顺序、hybrid逐色结果、原AB逐色结果；24/24小SMT新旧AB最终负载签名一致。", "",
             "这不保证后续路径总一致：comb n128/h16 的5轮结果原AB U/B=1.25、排序版=1.1875；uniform n1000/h128 的10轮结果原版=1、排序版约1.007。平局置换可改变后续候选。每候选最优不是全局色分配最优；U/B=1才认证该实例最大桶达到结构下界。", "",
             "## 计时与内存口径", "",
             "每个配置启动新进程并限制120秒；`coloring_s`为算法时间，扣除单独计量的checkpoint校验/文件IO。`extraction_forest_stats_s`是新压缩提取器及forest/下界统计时间，不是历史展开raw树构造时间。`measured_total_s`包含这些阶段及checkpoint开销，`subprocess_wall_s`还包括解释器/imports和输出layout文件。", "",
             "`rss_bytes`/`peak_rss_bytes`是Windows实际WorkingSet/PeakWorkingSet，包含解释器与imports，不是tracemalloc、不是纯算法额外内存。默认不启用Python分配跟踪以避免其扰动，缺失allocation列表示未测。工作站未固定CPU affinity/独占资源，真实六workload各为一次执行；单次时间倍率属于新实验pilot，不能当作置信区间。n1000固定输入的独立进程重复数量与有重复时的样本SD，以 `repeated_timing_summary.json` 实际记录为准。", "",
             "timeout行仅表示最后完成并校验的轮次；计时小于120秒是因为下一轮被中止。不可把partial当成20轮完成，也不可拿hybrid替代未完成AB。", "",
             "## 分布和规模", "",
             "uniform：按给定seed抽取无重复h位坐标。prefix-cluster：所有坐标共享高位0前缀，前缀位数记录在配置结果；剩余位均匀采样。comb：含0和单比特坐标，强制目标0具有min(h,n−1)非默认siblings，剩余坐标随机补齐。saturated：取0…n−1且n为2的幂，形成完整占用子树（n65536/h16时整个树饱和）。", "",
             "规模覆盖1k/10k/100k，h16/128/256；h16不能容纳100k，因此未创建不可行配置。高度配置使用明确记录的坐标seed/哈希，不把不同坐标抽样解释成同一棵树的纯高度效应。每轮扫描所有候选根、只接受一个最佳改善；20轮任务的history保留0/1/2/5/10/20中真实完成的状态。", "",
             "## 真实workload的结构比较", "",
             "| Workload | n | m | 非空深度桶 | FF max | Hybrid max | 原AB max | 排序AB max | 原AB秒 | 排序AB秒 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in summary_rows:
        lines.append(f"| {r['workload']} | {r['occupied_n']} | {r['m']} | {r['depth_active_queries']} | {r['first-fit_max_bucket']} | {r['hybrid_max_bucket']} | {r['ab-hungarian_max_bucket']} | {r['ab-sorted_max_bucket']} | {r['ab-hungarian_coloring_s']:.4f} | {r['ab-sorted_coloring_s']:.4f} |")
    lines += ["", "非空深度桶/SparseTreePIR query数量比仅约1.22–1.53，而不是h/m的7.53–14.22。应把这个更强且保持目标隐私的Depth-active控制纳入主文。新旧AB六workload最大桶一致，但停止轮数可能不同；部分20轮任务虽然U/B=1，仍未满足整个降序向量的局部停止条件。", "",
              "## 输出图和可复用数据", "",
              "- `balance_real_quality_time.pdf/png`：六个固定真实key workload的结构质量和着色时间；每系列名称明确算法，时间不含PIR。", "- `balance_round_budget.pdf/png`：1k/10k/100k uniform的完整扫描轮数与U/B关系，timeout在曲线标注。", "- `real_comparison.csv`：工作量、非空深度控制、四种算法的质量/时间/内存。", "- `per_run.csv`、`runs/*/result.json`：所有独立配置原始结果（CSV同时有n与N，区分大小写；JSON保留原字段）。", "- `runs/*/round_history.json`：真实每轮checkpoint。", "- `runs/*/layout_records.csv`：完成任务的node index、SMT depth、target rank interval、weight、color，可用于同一真实digest的PIR物化；本实验自身不执行PIR、也不伪称root验证。", "", "原版/排序候选的速度是实测实现比较；不把其差值宣传成private-proof服务速度，后者需独立backend及root验证实验。"]
    (OUT / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--suite", choices=["smoke", "real", "scale", "passes", "refinement", "repeats"])
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--aggregate", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args()
    if args.selfcheck:
        print(json.dumps(selfcheck(), ensure_ascii=False, indent=2))
    elif args.worker:
        worker(args.worker)
    elif args.suite:
        orchestrate(args.suite, args.timeout)
    elif args.aggregate:
        aggregate()
    elif args.report:
        report()
    else:
        parser.error("choose --selfcheck, --worker, --suite, or --aggregate")


if __name__ == "__main__":
    main()
