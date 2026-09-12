"""Evaluate the existing joint necessary bound in O(N*m), without old code.

This validates only the frozen 1,323 + 2,115 shapes. It creates no new census,
does not invoke an exact solver, and does not change any frozen artifact.
The nested shape in a frozen row is the excluded skeleton root: its children
are the components of the actual record forest.
"""
from pathlib import Path
import hashlib
import json
import platform

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ceildiv(a, b):
    assert b > 0
    return -((-a) // b)


def prepare(forest, palette=None):
    # Index zero is a virtual root, not a record and not an anchor.
    child, parent, depth = [[]], [-1], [0]

    def visit(tree, p):
        v = len(child)
        child.append([])
        parent.append(p)
        depth.append(depth[p] + 1)
        child[p].append(v)
        for subtree in tree:
            visit(subtree, v)

    for component in forest:
        visit(component, 0)
    count = len(child) - 1
    height = max(depth)
    m = height if palette is None else palette
    assert m >= height
    if count:
        assert m > 0
    size = [1] * (count + 1)
    beta = [[0] * (m + 1) for _ in child]
    sums = [[0] * (m + 1) for _ in child]
    for v in range(count, -1, -1):
        size[v] += sum(size[w] for w in child[v])
        for t in range(1, m + 1):
            sums[v][t] = sum(beta[w][t] for w in child[v])
            if v:
                beta[v][t] = max(sums[v][t], 1 + sums[v][t - 1])
    # Context zero has all records; context v has strict descendants of v.
    context_count = [count] + [size[v] - 1 for v in range(1, count + 1)]
    return child, parent, depth, context_count, beta, sums, m


def evaluate(forest, palette=None):
    child, parent, depth, context_count, beta, sums, m = prepare(forest, palette)
    N = len(parent) - 1
    if not N:
        return {"N": 0, "m": m, "bound": 0, "witness": None}
    best, witness = 0, None
    for x in range(N + 1):
        q = m - depth[x]
        if q > 0:
            candidate = ceildiv(context_count[x], q)
            if candidate > best:
                best = candidate
                witness = {"kind": "context_average", "context": x,
                           "context_records": context_count[x], "q": q}

    endpoints = 0
    for d in range(1, m):
        Q = [0] * (N + 1)
        inclusive_max = [0] * (N + 1)
        argmax = [0] * (N + 1)
        inclusive_max[0] = N
        for v in range(1, N + 1):
            if depth[v] > d:
                continue
            p = parent[v]
            t = d - depth[p]
            Q[v] = Q[p] + 1 + sums[p][t] - beta[v][t]
            if depth[v] == d:
                endpoints += 1
                x = argmax[p]
                candidate = ceildiv(inclusive_max[p] - Q[v], m - d)
                if candidate > best:
                    best = candidate
                    witness = {"kind": "joint_anchor", "context": x,
                               "terminal": v, "terminal_depth": d,
                               "anchor_count": d - depth[x],
                               "context_records": context_count[x],
                               "joint_capacity": Q[v] - Q[x],
                               "denominator": m - d}
            own = context_count[v] + Q[v]
            if own > inclusive_max[p]:
                inclusive_max[v], argmax[v] = own, v
            else:
                inclusive_max[v], argmax[v] = inclusive_max[p], argmax[p]
    return {"N": N, "m": m, "bound": best, "witness": witness,
            "depth_sweeps": max(0, m - 1), "evaluated_endpoints": endpoints}


def direct_path_bound(forest, palette=None):
    """Literal path sums for a few explicit boundary tests, not a fast DP."""
    child, parent, depth, nc, beta, sums, m = prepare(forest, palette)
    N = len(parent) - 1
    answer = max((ceildiv(nc[x], m - depth[x]) for x in range(N + 1)
                  if m > depth[x]), default=0)
    for v in range(1, N + 1):
        if depth[v] >= m:
            continue
        path = []
        w = v
        while w:
            path.append(w)
            x = parent[w]
            anchor_path = list(reversed(path))
            k = len(anchor_path)
            J = k
            previous = x
            for i, a in enumerate(anchor_path):
                J += sum(beta[z][k-i] for z in child[previous] if z != a)
                previous = a
            answer = max(answer, ceildiv(nc[x] - J, m - depth[v]))
            w = x
    return answer


def main():
    inputs = [
        ROOT / "examples/tifs_remaining_gap_20260910/theory/all_1323_joint_bounds.json",
        ROOT / "examples/tifs_remaining_gap_20260910/theory/expanded_exact_results.json",
    ]
    checks, input_manifest = [], []
    for source in inputs:
        source_rows = json.loads(source.read_text(encoding="utf8"))
        input_manifest.append({"path": str(source.relative_to(ROOT)),
                               "sha256": sha(source), "rows": len(source_rows)})
        for i, row in enumerate(source_rows):
            # The evaluator receives only the shape, never a saved bound/optimum.
            actual = evaluate(row["shape"])
            assert actual["bound"] == row["B_joint"], (source.name, i, actual, row)
            assert (actual["N"], actual["m"]) == (row["N"], row["m"])
            checks.append({"source": source.name, "index": i,
                           "saved_B_joint": row["B_joint"], **actual})
    assert len(checks) == 3438
    # Fixed small tests exercise empty/single/unary, nonbinary, >height palettes.
    boundary_forests = [[], [[]], [[[]]], [[], []], [[[], []], []],
                        [[[], [], []]] * 3, [[[[], []], []], [[], []]]]
    boundaries = []
    for f in boundary_forests:
        height = prepare(f)[-1]
        for m in sorted({height, height + 1, height + 3}):
            fast, slow = evaluate(f, m), direct_path_bound(f, m)
            assert fast["bound"] == slow
            boundaries.append({"forest": f, "palette": m, "direct": slow, **fast})
    output = {"status": "pass", "scope": "existing bound only; no new exact census",
              "frozen_rows_checked": len(checks), "mismatches": 0,
              "boundary_cases": boundaries, "inputs": input_manifest,
              "script_sha256": sha(Path(__file__)), "python": platform.python_version(),
              "complexity": "O(N*m) word operations and O(N*m) words",
              "checks": checks}
    destination = OUT / "frozen_3438_consistency.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in output.items() if k not in ("checks", "boundary_cases")}, indent=2))
    print("Boundary cases:", len(boundaries))


if __name__ == "__main__":
    main()
