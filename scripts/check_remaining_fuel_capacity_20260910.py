"""Bounded feasibility search; a returned coloring is verified with integers.

This is an offline optimum witness, not an ActiveBalance or PIR benchmark.
"""
from pathlib import Path
import hashlib, json, platform, struct, time
import numpy as np
import scipy
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

ROOT = Path(__file__).absolute().parents[1]
OUT = ROOT / 'examples/tifs_remaining_gap_20260910/fuel'
SOURCE = ROOT / 'examples/tifs_revision_20260910/verified_backend/fuel_h128/activebalance/layout_metadata.bin'

def load_records():
    raw = SOURCE.read_bytes()
    assert raw[:8] == b'TIFSMETA'
    h, n, m = struct.unpack_from('>HII', raw, 8)
    offset = 18
    records = []
    for _ in range(m):
        color, length = struct.unpack_from('>II', raw, offset)
        offset += 8
        for pos in range(length):
            left, right, level, flags, index = struct.unpack_from('>QQHHI', raw, offset)
            offset += 24
            records.append(dict(left=left, right=right, level=level,
                                original_color=color, original_position=pos))
    assert offset == len(raw)
    records.sort(key=lambda r: (r['left'], -r['right'], r['level']))
    stack = []
    for i, r in enumerate(records):
        while stack and not (records[stack[-1]]['left'] <= r['left'] and r['right'] <= records[stack[-1]]['right']):
            stack.pop()
        r['ancestors'] = list(stack)
        r['parent'] = stack[-1] if stack else -1
        stack.append(i)
    assert len(records) == 198 and m == 9 and n == 100
    return records, n, m, raw

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records, n, m, raw = load_records()
    N = len(records)
    cap = 22
    # Each variable x[v,c] says that record v uses color c.
    rr, cc, vv, lower, upper = [], [], [], [], []
    def constraint(columns, lo, hi):
        row = len(lower)
        for col in columns:
            rr.append(row); cc.append(col); vv.append(1.0)
        lower.append(lo); upper.append(hi)
    for v in range(N):
        constraint([v*m+c for c in range(m)], 1, 1)
    # Every occupied-rank proof must have distinct colors. Rank endpoints are
    # inclusive in TIFSMETA; this also avoids relying on the parent parser.
    for rank in range(n):
        vertices = [v for v,r in enumerate(records) if r['left'] <= rank <= r['right']]
        for c in range(m):
            constraint([v*m+c for v in vertices], 0, 1)
    for c in range(m):
        constraint([v*m+c for v in range(N)], 0, cap)
    lb, ub = np.zeros(N*m), np.ones(N*m)
    deepest = max(range(N), key=lambda v:len(records[v]['ancestors']))
    chain = records[deepest]['ancestors'] + [deepest]
    assert len(chain) == m
    # Global renaming can always map this chain to colors 0,...,m-1.
    for c, v in enumerate(chain):
        lb[v*m+c] = ub[v*m+c] = 1
    matrix = coo_matrix((vv, (rr, cc)), shape=(len(lower),N*m)).tocsc()
    start = time.monotonic()
    result = milp(c=np.zeros(N*m), integrality=np.ones(N*m),
                  bounds=Bounds(lb,ub),
                  constraints=LinearConstraint(matrix, np.array(lower), np.array(upper)),
                  options=dict(time_limit=120, mip_rel_gap=0, presolve=True))
    output = dict(source=str(SOURCE.relative_to(ROOT)), source_sha256=hashlib.sha256(raw).hexdigest(),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  N=N, n=n, m=m, capacity_tested=cap, time_limit_seconds=120,
                  elapsed_seconds=time.monotonic()-start, scipy=scipy.__version__,
                  python=platform.python_version(), status=int(result.status), message=result.message,
                  scope='Offline feasibility witness; not an AB algorithm or runtime improvement.',
                  integer_coloring_verified=False)
    if result.x is not None:
        x = np.rint(result.x).astype(int).reshape(N,m)
        assert np.max(np.abs(result.x - x.ravel())) < 1e-5
        assert np.all(x.sum(axis=1) == 1) and np.all((x==0)|(x==1))
        colors = x.argmax(axis=1).tolist()
        loads = [colors.count(c) for c in range(m)]
        assert max(loads) <= cap
        for v,r in enumerate(records):
            assert all(colors[v] != colors[a] for a in r['ancestors'])
            r['witness_color'] = colors[v]
        for rank in range(n):
            target = [colors[v] for v,r in enumerate(records) if r['left'] <= rank <= r['right']]
            assert len(target) == len(set(target))
        output.update(integer_coloring_verified=True, loads=loads, records=records,
                      verified_target_ranks=n, optimum=cap,
                      optimality_reason='Legal capacity22 witness matches ceil(198/9)=22.')
    (OUT/'capacity22_result.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in output.items() if k!='records'},indent=2),flush=True)

if __name__ == '__main__': main()
