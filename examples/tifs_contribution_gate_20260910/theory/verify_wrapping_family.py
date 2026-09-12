"""Six fixed witnesses for a proved infinite family; no exact search.

The SMT builder/checker and proof-support interval forest are implemented here
using only Python's standard library. No measured or legacy algorithm is run.
"""
from pathlib import Path
import hashlib
import json

from verify_joint_linear import prepare, evaluate, ceildiv, sha

OUT = Path(__file__).resolve().parent
L = []
C = [L, [L, L]]
P = [[L, L], [L, L]]
SEED = [C, [L, [C, P]]]
SEED_COLORS = [2, 4, 3, 4, 4, 2, 3, 4, 0, 1, 3, 1, 1, 3, 1, 0, 0, 1, 0, 0]


def old_bounds_and_slacks(forest, capacity=4):
    ch, pa, dep, nc, _, _, m = prepare(forest)
    N = len(pa) - 1
    leaves = [0] * (N + 1)
    for v in range(N, -1, -1):
        leaves[v] = sum(leaves[w] for w in ch[v]) if ch[v] else 1
    B = H = 0
    contexts = []
    for x in range(N + 1):
        q = m - dep[x]
        if not q:
            continue
        average = ceildiv(nc[x], q)
        B = max(B, average)
        local_slacks = [q * capacity - nc[x]]
        tests = 0
        for v in range(1, N + 1):
            if dep[v] >= m or v == x:
                continue
            path, w = [], v
            while w != x and w:
                path.append(w)
                w = pa[w]
            if w != x:
                continue
            k = len(path)
            S = sum(1 + leaves[x] - leaves[a] for a in path)
            denominator = q - k
            assert denominator > 0
            H = max(H, ceildiv(nc[x] - S, denominator))
            local_slacks.append(S + denominator * capacity - nc[x])
            tests += 1
        if nc[x]:
            contexts.append({"context": x, "depth": dep[x], "records": nc[x],
                             "leaves": leaves[x], "available_colors": q,
                             "individual_anchor_tests": tests,
                             "minimum_slack_at_capacity_4": min(local_slacks)})
    return B, max(B, H), contexts


def abstract_coloring(forest, colors):
    ch, pa, dep, nc, _, _, m = prepare(forest)
    assert len(colors) == len(pa) - 1
    loads = [0] * m
    for v in range(1, len(pa)):
        c = colors[v - 1]
        assert 0 <= c < m
        loads[c] += 1
        p = pa[v]
        while p:
            assert colors[p - 1] != c
            p = pa[p]
    return loads


def H(data):
    return hashlib.sha256(data).digest()


def actual_smt(forest, colors):
    _, _, _, _, _, _, height = prepare(forest)
    slots = []

    def positions(t, prefix, depth):
        if not t:
            slots.append(prefix << (height - depth))
            return
        assert len(t) == 2
        for bit, child in enumerate(t):
            positions(child, (prefix << 1) | bit, depth + 1)

    positions(forest, 0, 0)  # excluded skeleton root; two forest roots below it
    assert slots == sorted(set(slots))
    defaults = [H(b"\x02")]
    for _ in range(height):
        defaults.append(H(b"\x01" + defaults[-1] + defaults[-1]))
    width = max(1, (height + 7) // 8)
    values = {s: H(b"wrapper-audit" + s.to_bytes(width, "big")) for s in slots}
    current = {(1 << height) + s: H(b"\x00" + values[s]) for s in slots}
    digests = dict(current)
    for level in range(height):
        parents = {v // 2 for v in current}
        current = {p: H(b"\x01" + current.get(2*p, defaults[level])
                         + current.get(2*p+1, defaults[level])) for p in parents}
        digests.update(current)
    root = digests[1]
    support = {}
    needs = []
    for rank, slot in enumerate(slots):
        node, wanted = (1 << height) + slot, {}
        for level in range(height):
            sibling = node ^ 1
            if sibling in digests:
                support.setdefault(sibling, []).append(rank)
                wanted[level] = sibling
            node //= 2
        needs.append(wanted)
    records = sorted(support, key=lambda v: (support[v][0], -support[v][-1]))
    assert len(records) == len(colors)
    nodes, roots, stack = [], [], []
    for node, color in zip(records, colors):
        ranks = support[node]
        assert ranks == list(range(ranks[0], ranks[-1] + 1))
        left, right = ranks[0], ranks[-1]
        while stack and not (nodes[stack[-1]]["interval"][0] <= left and
                             right <= nodes[stack[-1]]["interval"][1]):
            stack.pop()
        i = len(nodes)
        entry = {"heap_index_hex": hex(node), "interval": [left, right],
                 "color": color, "digest_hex": digests[node].hex(), "children": []}
        nodes.append(entry)
        if stack:
            nodes[stack[-1]]["children"].append(i)
        else:
            roots.append(i)
        stack.append(i)

    def shape(i):
        return [shape(j) for j in nodes[i]["children"]]

    assert [shape(i) for i in roots] == forest
    label = dict(zip(records, colors))
    proofs = []
    for slot, wanted in zip(slots, needs):
        assert len({label[v] for v in wanted.values()}) == len(wanted)
        siblings = [digests[wanted[l]] if l in wanted else defaults[l] for l in range(height)]
        current_hash = H(b"\x00" + values[slot])
        mutated = H(b"\x00" + bytes([values[slot][0] ^ 1]) + values[slot][1:])
        for level, sibling in enumerate(siblings):
            if (slot >> level) & 1:
                current_hash = H(b"\x01" + sibling + current_hash)
                mutated = H(b"\x01" + sibling + mutated)
            else:
                current_hash = H(b"\x01" + current_hash + sibling)
                mutated = H(b"\x01" + mutated + sibling)
        assert current_hash == root and mutated != root
        proofs.append({"slot": slot, "value_hex": values[slot].hex(),
                       "siblings_hex": [v.hex() for v in siblings],
                       "real_levels": sorted(wanted), "root_verified": True,
                       "mutated_value_rejected": True})
    return {"height": height, "root_hex": root.hex(), "slots": slots,
            "support_forest_equals_abstract_forest": True, "records": nodes,
            "proofs": proofs}


def main():
    selected = [0, 1, 2, 5, 10, 25]
    forest, colors = SEED, list(SEED_COLORS)
    certificates = []
    for t in range(max(selected) + 1):
        if t in selected:
            loads = abstract_coloring(forest, colors)
            assert max(loads) == 5
            B, hierarchical, slacks = old_bounds_and_slacks(forest)
            joint = evaluate(forest)
            assert (B, hierarchical, joint["bound"]) == (4, 4, 5)
            assert all(v["minimum_slack_at_capacity_4"] >= 0 for v in slacks)
            smt = actual_smt(forest, colors)
            certificates.append({"wrappers": t, "N": 20 + 2*t, "n": 11 + t,
                                 "m": 5 + t, "B": B, "B_hier": hierarchical,
                                 "B_joint": joint["bound"], "loads": loads,
                                 "preorder_colors": colors, "shape": forest,
                                 "old_bound_context_slacks": slacks, **smt})
        new_color = 5 + t
        forest, colors = [forest, []], [new_color] + colors + [new_color]
    result = {"status": "pass", "selected_wrapper_counts": selected,
              "method": "explicit construction and hashing; no exact search",
              "scope": "infinite family proved separately; six fixed checks only",
              "actual_smt_proofs": sum(len(c["proofs"]) for c in certificates),
              "script_sha256": sha(Path(__file__)),
              "bound_helper_sha256": sha(OUT / "verify_joint_linear.py"),
              "certificates": certificates}
    (OUT / "wrapping_family_verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k != "certificates"}, indent=2))
    print("Seed context slacks:")
    for row in certificates[0]["old_bound_context_slacks"]:
        print(row)


if __name__ == "__main__":
    main()
