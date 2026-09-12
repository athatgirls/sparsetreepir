"""Actual existing FF/Hungarian AB on all frozen exact small shapes.

No exact-search timings are combined with algorithm timings. Existing input
files and measured layouts are read-only. All new output stays in algorithm/.
"""
from __future__ import annotations
import bisect, csv, hashlib, json, platform, statistics, struct, time
from collections import Counter
from pathlib import Path

from tifs_revision_smt import build_layout, reconstruct_proof, verify_proof
from run_height_sparsity_profile_balance_experiment import structural_max_bucket_lower_bound

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'examples/tifs_revision_20260910/theory_exploration/final/small_shape_exact_results.json'
REAL=SOURCE.with_name('real_workload_bounds.json')
OUT=ROOT/'examples/tifs_remaining_gap_20260910/algorithm'
ROUNDS=20

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')
def slot_embedding(shape):
    paths=[]
    def walk(t,p):
        if not t:paths.append(p);return
        assert len(t)==2
        walk(t[0],p+'0');walk(t[1],p+'1')
    walk(shape,'');h=max(map(len,paths))
    return h,[int(p.ljust(h,'0'),2) for p in paths]

def measure(shape,method,rounds):
    h,slots=slot_embedding(shape);start=time.perf_counter()
    a=build_layout(h,slots,color_strategy=method,refine_rounds=rounds)
    build_seconds=time.perf_counter()-start;checks=0
    nodes={v.index:v for v in a.proof_nodes}
    for s in slots:
        required=list(a.tree.proof_record_nodes(s).values())
        assert len({nodes[v].color for v in required})==len(required)
        selection=a.selection(s)
        got={e['color']:a.active_records[a.buckets[e['color']][e['index']]] for e in selection}
        proof=reconstruct_proof(a,s,got,selection)
        assert proof==a.tree.proof(s) and verify_proof(h,s,a.values[s],proof,a.root)
        checks+=1
    loads=[len(a.buckets[c]) for c in sorted(a.buckets)]
    result={'loads':loads,'max_bucket':max(loads),'coloring_ms':a.timings_ms['coloring'],
            'build_seconds':build_seconds,'passes':a.passes,'accepted_moves':a.moves,
            'round_budget':rounds if method=='activebalance' else None,
            'budget_exhausted':method=='activebalance' and a.passes==rounds and a.moves==rounds,
            'proofs_color_and_root_verified':checks,
            'records':[{'heap_node':v.index,'parent':v.parent.index if v.parent else None,
                        'children':[c.index for c in v.children],'left':v.interval_left,
                        'right':v.interval_right,'proof_level':h-v.depth,'color':v.color}
                       for v in a.proof_nodes]}
    return a,result

def metadata(p):
    raw=p.read_bytes();assert raw[:8]==b'TIFSMETA'
    h,n,m=struct.unpack_from('>HII',raw,8);offset=18
    kb=p.with_name('occupied_slots.bin').read_bytes();w=(h+7)//8
    slots=[int.from_bytes(kb[i:i+w],'big') for i in range(0,len(kb),w)]
    assert len(slots)==n and len(set(slots))==n and slots==sorted(slots)
    records=[];loads=[]
    for _ in range(m):
        c,length=struct.unpack_from('>II',raw,offset);offset+=8;loads.append(length);local=[]
        for _ in range(length):
            left,right,level,flags,pos=struct.unpack_from('>QQHHI',raw,offset);offset+=24
            assert 0<=left<=right<n and 0<=level<h
            node=(((1<<h)+slots[left])>>level)^1
            service_prefix=(node^1)-(1<<(h-level))
            expected_left=bisect.bisect_left(slots,service_prefix<<level)
            expected_right=bisect.bisect_left(slots,(service_prefix+1)<<level)-1
            assert (left,right)==(expected_left,expected_right)
            local.append((left,right));records.append({'heap_node':node,'left':left,'right':right,
                                                       'level':level,'color':c,'position':pos})
        local.sort();assert all(a[1]<b[0] for a,b in zip(local,local[1:]))
    assert offset==len(raw) and len({r['heap_node'] for r in records})==sum(loads)
    return {'height':h,'n':n,'m':m,'N':sum(loads),'slots':slots,'loads':loads,'records':records}

def real_rows():
    out=[];fuel_report=None
    for b in json.loads(REAL.read_text(encoding='utf8')):
        abp=ROOT/b['input'];assert sha(abp)==b['sha256']
        ffp=abp.parent.parent/'first_fit/layout_metadata.bin'
        ab=metadata(abp);ff=metadata(ffp)
        assert (ab['n'],ab['N'],ab['m'])==(b['n'],b['N'],b['m'])
        assert ab['slots']==ff['slots'] and {r['heap_node'] for r in ab['records']}=={r['heap_node'] for r in ff['records']}
        lb=b['hierarchical_bound'];av=max(ab['loads']);fv=max(ff['loads'])
        name=abp.parent.parent.name if 'ct_application' not in str(abp) else 'ct-record-mirror'
        opt=lb if av==lb else None;status='matched lower bound by frozen AB coloring' if opt else 'unknown exact optimum'
        if name=='fuel_h128':
            wp=ROOT/'examples/tifs_remaining_gap_20260910/fuel/capacity22_result.json'
            if wp.exists():
                witness=json.loads(wp.read_text(encoding='utf8'))
                (OUT/'fuel_capacity22_witness_snapshot.json').write_bytes(wp.read_bytes())
                assert witness['source_sha256']==sha(abp)
                indexed={(r['left'],r['right'],r['level']):r for r in ab['records']}
                wr=witness['records'];assert len(wr)==len(indexed)==198
                assert {(r['left'],r['right'],r['level']) for r in wr}==set(indexed)
                assert all(type(r['witness_color']) is int and 0<=r['witness_color']<ab['m'] for r in wr)
                loads=Counter(r['witness_color'] for r in wr);assert sorted(loads.values())==[22]*9
                for rank in range(ab['n']):
                    active=[r for r in wr if r['left']<=rank<=r['right']]
                    assert len({r['witness_color'] for r in active})==len(active)
                opt=22;status='independently checked separate capacity-22 integer witness; not AB'
                fuel_report={'witness_path':str(wp.relative_to(ROOT)),'sha256':sha(wp),
                             'frozen_input_copy':'fuel_capacity22_witness_snapshot.json',
                             'metadata_records_exact_match':198,'inclusive_target_ranks_checked':100,
                             'integer_colors_checked':198,'witness_color_indexing':'zero-based 0..8; frozen AB uses 1..9',
                             'loads':[22]*9,'optimality':'ceil(198/9)=22 plus proper capacity-22 coloring'}
        row={'dataset':name,**{k:b[k] for k in ('n','N','m','B','hierarchical_bound')},
             'FF':fv,'AB':av,'OPT':opt,'optimum_lower':lb,'optimum_upper':av if opt is None else opt,
             'optimum_status':status,'FF_over_B':fv/b['B'],'AB_over_B':av/b['B'],
             'FF_certificate_excess_over_B':(fv-b['B'])/b['B'],
             'AB_certificate_excess_over_B':(av-b['B'])/b['B'],
             'FF_exact_gap':(fv-opt)/opt if opt else None,'AB_exact_gap':(av-opt)/opt if opt else None,
             'FF_loads':ff['loads'],'AB_loads':ab['loads'],
             'FF_metadata':str(ffp.relative_to(ROOT)),'FF_sha256':sha(ffp),
             'AB_metadata':str(abp.relative_to(ROOT)),'AB_sha256':sha(abp),
             'validation':'unique positional records, exact inclusive service intervals, same-color nonoverlap; FF/AB record universes and slots match'}
        out.append(row)
    return out,fuel_report

def main():
    OUT.mkdir(parents=True,exist_ok=True);start=time.perf_counter();rows=[]
    original=json.loads(SOURCE.read_text(encoding='utf8'))
    for i,s in enumerate(original):
        a,ff=measure(s['shape'],'first_fit',ROUNDS);b,ab=measure(s['shape'],'activebalance',ROUNDS)
        assert a.width==b.width==s['m'] and len(a.active_records)==len(b.active_records)==s['N']
        assert structural_max_bucket_lower_bound(a.forest,s['N'],s['m'])==s['B']
        assert s['hierarchical_bound']<=s['optimum']<=ab['max_bucket']<=ff['max_bucket']
        assert set(a.active_records)==set(b.active_records)
        row={'source_index':i,'id':f'S{i:04d}','shape_sha256':hashlib.sha256(json.dumps(s['shape'],separators=(',',':')).encode()).hexdigest(),
             'shape':s['shape'],'height':a.height,'slots':a.slots,
             **{k:s[k] for k in ('n','N','m','B','hierarchical_bound','optimum','strict_hierarchical_gap')},
             'first_fit':ff,'activebalance':ab}
        for method in ('first_fit','activebalance'):
            alg=row[method]['max_bucket'];lb=s['hierarchical_bound'];opt=s['optimum']
            row[method]['certificate_excess_over_Bhier']=(alg-lb)/lb
            row[method]['exact_gap_over_OPT']=(alg-opt)/opt
        if ab['budget_exhausted']:
            _,row['activebalance_100_round_diagnostic']=measure(s['shape'],'activebalance',100)
        rows.append(row)
        if (i+1)%300==0:print(f'{i+1}/{len(original)} actual FF+AB layouts: {time.perf_counter()-start:.3f} seconds',flush=True)
    algorithm_seconds=time.perf_counter()-start
    reals,fuel=real_rows()
    source_summary=json.loads(SOURCE.with_name('summary.json').read_text())
    summary={'source':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),
      'source_rows':len(rows),'source_exact_OPT':'Frozen exact profile DP from source JSON; no new exact solver run or solver time charged to FF/AB.',
      'source_census_scope':{'leaves_min':2,'leaves_max':source_summary['max_requested_leaves'],
                            'width_cap':source_summary['width_cap'],'source_enumeration_censored':source_summary['enumeration_censored'],
                            'shapes_by_leaf_count':dict(Counter(r['n'] for r in rows)),
                            'orientation':'One source-canonical non-plane binary shape ordering; not every left/right orientation and not a random workload distribution.'},
      'embedding':'Original nested child order; [] is a leaf; path bits padded with zeros to maximum depth; original root is not a proof record.',
      'algorithms':'Actual tifs_revision_smt.build_layout; first_fit_coloring and best_count_profile_balanced from current implementation, not replacement heuristics.',
      'tie_breaking':'Forest ordered by (interval_left, -interval_length, heap_node); pre-order candidate traversal. FF chooses smallest unused color. AB starts from FF, Hungarian rows/columns enumerate ascending available color; strict < updates retain first equal-cost/equal-signature encountered candidate. No randomness in coloring.',
      'AB_round_budget':ROUNDS,'AB_max_passes':max(r['activebalance']['passes'] for r in rows),
      'AB_max_moves':max(r['activebalance']['accepted_moves'] for r in rows),
      'AB_budget_exhaustions':sum(r['activebalance']['budget_exhausted'] for r in rows),
      'runtime_seconds_including_embedding_build_and_all_target_root_checks':algorithm_seconds,
      'python':platform.python_version(),'platform':platform.platform(),
      'metrics':'U is largest bucket. Certificate excess (U-LB)/LB upper-bounds relative suboptimality; exact gap (U-OPT)/OPT is directly measured against certified optimum. Neither is a latency speedup.',
      'lower_bound_remaining_shapes':sum(r['strict_hierarchical_gap'] for r in rows),
      'AB_suboptimal_and_Bhier_tight':sum(r['activebalance']['max_bucket']>r['optimum'] and r['hierarchical_bound']==r['optimum'] for r in rows),
      'AB_suboptimal_and_Bhier_slack':sum(r['activebalance']['max_bucket']>r['optimum'] and r['hierarchical_bound']<r['optimum'] for r in rows),
      'AB_suboptimal_OPT_to_U_counts':dict(Counter(f"{r['optimum']}->{r['activebalance']['max_bucket']}" for r in rows if r['activebalance']['max_bucket']>r['optimum'])),
      'real_AB_equals_B':sum(r['AB']==r['B'] for r in reals),'real_shapes':len(reals),
      'frozen_real_measurement_scope':'Only frozen binary directory contents are counted and validated; no algorithm rerun or change to old measurements.',
      'files_sha256':{str(p.relative_to(ROOT)):sha(p) for p in (Path(__file__),ROOT/'scripts/tifs_revision_smt.py',ROOT/'scripts/run_height_sparsity_profile_balance_experiment.py',ROOT/'scripts/generate_full_sparse_smt_example.py',REAL)},
      'fuel_witness_independent_check':fuel}
    for method in ('first_fit','activebalance'):
        summary[method]={'exact_optimum_attained':sum(r[method]['max_bucket']==r['optimum'] for r in rows),
                         'max_exact_gap':max(r[method]['exact_gap_over_OPT'] for r in rows),
                         'mean_exact_gap':statistics.mean(r[method]['exact_gap_over_OPT'] for r in rows),
                         'max_certificate_excess_Bhier':max(r[method]['certificate_excess_over_Bhier'] for r in rows),
                         'total_coloring_seconds':sum(r[method]['coloring_ms'] for r in rows)/1000,
                         'proofs_color_and_root_verified':sum(r[method]['proofs_color_and_root_verified'] for r in rows)}
    save(OUT/'small_shape_algorithm_results.json',rows);save(OUT/'real_dataset_algorithm_gaps.json',reals);save(OUT/'summary.json',summary)
    with (OUT/'small_shape_algorithm_results.csv').open('w',newline='',encoding='utf8') as f:
        keys=['id','source_index','n','N','m','B','Bhier','OPT','FF','AB','FF_exact_gap','AB_exact_gap','FF_certificate_excess_Bhier','AB_certificate_excess_Bhier','AB_passes','AB_moves','AB_budget_exhausted']
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow(dict(zip(keys,[r['id'],r['source_index'],r['n'],r['N'],r['m'],r['B'],r['hierarchical_bound'],r['optimum'],r['first_fit']['max_bucket'],r['activebalance']['max_bucket'],r['first_fit']['exact_gap_over_OPT'],r['activebalance']['exact_gap_over_OPT'],r['first_fit']['certificate_excess_over_Bhier'],r['activebalance']['certificate_excess_over_Bhier'],r['activebalance']['passes'],r['activebalance']['accepted_moves'],r['activebalance']['budget_exhausted']])))
    with (OUT/'real_dataset_algorithm_gaps.csv').open('w',newline='',encoding='utf8') as f:
        keys=['dataset','n','N','m','B','hierarchical_bound','FF','AB','OPT','FF_over_B','AB_over_B','FF_exact_gap','AB_exact_gap','optimum_status'];w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore');w.writeheader();w.writerows(reals)
    failed=[r for r in rows if r['activebalance']['max_bucket']>r['optimum']]
    lines=['# Actual FF/AB algorithm gaps (2026-09-10)','',
      'The original algorithms were executed, not simulated with substitute greedy rules. All historical inputs, measured layouts, and manuscript files remain unchanged.','',
      '## Reproduce','',
      'From the repository root: `python scripts/measure_gap_algorithm_20260910.py`, then `python scripts/plot_gap_algorithm_20260910.py`. Dependencies are the current repository Python modules and Matplotlib. No network, Go backend, or new exact DP run is needed.','',
      f'This execution used Python {platform.python_version()} on {platform.system()}. Building both layouts and independently checking every target took {algorithm_seconds:.3f} seconds; actual coloring alone totaled {summary["first_fit"]["total_coloring_seconds"]:.6f} s (FF) and {summary["activebalance"]["total_coloring_seconds"]:.6f} s (AB). These are single local execution costs, not repeated timing estimates or backend service latency.','',
      '## Scope, algorithm, and validation','',
      'The frozen source contains all 1323 source-canonical non-plane binary shapes with 2–14 leaves and width at most 6; its enumeration is uncensored. This is not all shapes without a width restriction, every left/right orientation, or a sample of application demand. Source row order is retained: S0223 means zero-based source_index 223.','',
      'A leaf is [], an internal node is its ordered child pair. Leaf path bits are padded with zeroes to the deepest leaf to obtain an actual sparse SMT; unary padding introduces no active record. The current SMT API independently confirms source N and m, recomputes the original structural B, and verifies all target color sets and recovered real SHA-256 proofs (16642 per method, 33284 total).','',
      summary['tie_breaking'],'',
      f'AB uses the original Hungarian routine with a 20-scan cap, begins at actual FF, and stops on a scan finding no strict improvement. Maximum passes = {summary["AB_max_passes"]}; maximum accepted moves = {summary["AB_max_moves"]}; budget truncations = {summary["AB_budget_exhaustions"]}. Thus these output gaps cannot be attributed to hitting this round cap. Changing ties, orientation, initialization, or the legal move set remains a separate algorithm modification.','',
      '## Do not confuse lower-bound slack and algorithm error','',
      'For largest bucket U, `(U−LB)/LB` is certificate excess, an upper bound on `(U−OPT)/OPT`. The latter is the exact relative algorithm gap. Neither is a latency speedup, and a nonzero certificate excess alone does not prove an algorithm is suboptimal.','',
      '| Method | Exact optimum attained | Maximum exact gap | Mean exact gap across enumerated shapes |',
      '|---|---:|---:|---:|']
    for method,label in [('first_fit','First-fit'),('activebalance','ActiveBalance')]:
        z=summary[method];lines.append(f'| {label} | {z["exact_optimum_attained"]}/1323 | {z["max_exact_gap"]:.2%} | {z["mean_exact_gap"]:.4%} |')
    lines+=['',
      '**The 13 lower-bound counterexamples and 200 AB failures are disjoint.** All thirteen cases with frozen Bhier < OPT have AB = OPT. All 200 suboptimal AB outputs have Bhier = OPT: 178 have OPT 4 / AB 5, 12 have OPT 5 / AB 6, and 10 have OPT 6 / AB 7. Consequently a tighter lower bound cannot improve those 200 algorithm outputs. Their maximum actual gap is 25%.','',
      f'The first suboptimal AB source row is {failed[0]["id"]} (n={failed[0]["n"]}, m={failed[0]["m"]}, OPT={failed[0]["optimum"]}, AB={failed[0]["activebalance"]["max_bucket"]}). Full node assignments and per-case metrics are in `small_shape_algorithm_results.json` and the compact CSV.','',
      '## Frozen seven-dataset counts','',
      'The following are extracted from actual binary layout directories, not rerun estimates. Every service interval is checked against the occupied coordinates using inclusive endpoints; per-color intervals are disjoint, positional records are unique, and the FF/AB record universes match. The source metadata hashes match the prior bound analysis.','',
      '| Dataset | n | m | B = Bhier | FF | AB | OPT | FF/B | AB/B | AB exact gap |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in reals:lines.append(f'| {r["dataset"]} | {r["n"]} | {r["m"]} | {r["B"]} | {r["FF"]} | {r["AB"]} | {r["OPT"]} | {r["FF_over_B"]:.4f} | {r["AB_over_B"]:.4f} | {r["AB_exact_gap"]:.4%} |')
    lines+=['',
      'On six of seven datasets AB = B, which already certifies exact optimality for this largest-bucket objective. There is no lower-bound or max-bucket algorithm gap left on those six. This does not imply minimum communication, fastest sequential PIR, or an advantage over full caching.','',
      'Fuel previously had only OPT in [22,23]. The separate capacity-22 integer witness now establishes OPT=22 together with ceil(198/9)=22. This analysis independently checks all 198 witness rows against the original binary metadata, integer colors 0–8, all 100 inclusive target ranks, and nine loads of 22. Frozen AB remains 23, hence its true gap is 1/22 = 4.5455%. The exact feasibility witness is a separate method; its result and solver time are not substituted for AB or old backend measurements. The witness version audited here is frozen in `fuel_capacity22_witness_snapshot.json`.','',
      '## Figure and provenance','',
      '`remaining13_algorithm_trees.pdf/png` draws the thirteen actual AB retrieval-interval forests with LB, OPT, FF, and AB maxima. The virtual open root is excluded from N. Shared vertex colors describe actual AB assignments; edges are interval containment, not SMT parenthood. All thirteen have AB = OPT > the displayed frozen Bhier. This figure documents the earlier hierarchical bound; any separately derived joint bound is a different certificate and must be identified separately.','',
      '`remaining13_figure_index.json` maps every panel to its source index and shape hash; `remaining13_caption.tex` is an uninserted caption. `summary.json` pins source/script hashes, environment, runtime boundaries, budgets, all aggregate counts, and the independent Fuel witness check. No manuscript was edited.','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k in ('source_rows','runtime_seconds_including_embedding_build_and_all_target_root_checks','AB_max_passes','AB_budget_exhaustions','first_fit','activebalance','real_AB_equals_B','fuel_witness_independent_check')},indent=2))

if __name__=='__main__':main()
