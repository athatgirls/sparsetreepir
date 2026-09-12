"""Targeted five-case structural audit; no old results or algorithms are changed."""
from pathlib import Path
import hashlib, itertools, json, math, time, importlib.util
import prototype_construction_kempe_20260910 as local
import explore_remaining_joint_anchors_20260910 as joint

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'examples/tifs_layout_transfer_20260910/theory'
SOURCE=ROOT/'examples/tifs_sufficiency_20260910/construction'
IDS=['S0606','S0710','H1199','H1265','H1285']

def dump(p,obj):p.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def joint_at_palette_size(forest,m):
    nodes,roots=joint.index_forest(forest);N=len(nodes);best=math.ceil(N/m);witness=None
    for context in [-1]+list(range(N)):
        d=0 if context<0 else nodes[context]['depth'];q=m-d
        localN=N if context<0 else nodes[context]['size']-1
        if not localN:continue
        assert q>0
        c=math.ceil(localN/q)
        if c>best:best=c;witness={'type':'context_average','context':context,'N_context':localN,'q':q,'bound':c}
        for end in range(N):
            chain=[];p=end
            while p>=0 and p!=context:chain.append(p);p=nodes[p]['parent']
            if p!=context or not chain:continue
            k=len(chain)
            if k>=q:continue
            J,path,regions=joint.joint_capacity(nodes,roots,context,end)
            c=math.ceil((localN-J)/(q-k))
            if c>best:best=c;witness={'type':'joint_anchors','context':context,'terminal':end,'N_context':localN,'q':q,'k':k,'J':J,'bound':c,'regions':regions}
    return best,witness

def palette_profiles(parent,colors,palette):
    current={(0,0,0,0):()};order=[]
    forest=local.induced_forest(parent,colors,palette)
    for shape,ids in forest:
        options=local.tree_profiles(shape,(1<<len(palette))-1);new={}
        for p,w in current.items():
            for q,v in options.items():new.setdefault(tuple(a+b for a,b in zip(p,q)),w+v)
        current=new;order+=ids
    return current,order,tuple(s for s,ids in forest)

def main():
    if (OUT/'five_case_analysis.json').exists():raise RuntimeError('preserve prior output')
    OUT.mkdir(parents=True,exist_ok=True);started=time.monotonic();deadline=started+75
    files=[SOURCE/'base_construction_results.json',SOURCE/'holdout_construction_results.json']
    cases={r['id']:r for p in files for r in json.loads(p.read_text()) if r['id'] in IDS}
    result=[]
    for cid in IDS:
        r=cases[cid];colors=r['final_colors'];m=r['m'];L=r['OPT'];parent,edges=local.graph(r['records']);old=local.signature(colors,m)
        assert len(colors)==m*L and old==(L+1,)+(L,)*(m-2)+(L-1,)
        counts=local.loads(colors,m);over=counts.index(L+1)+1;under=counts.index(L-1)+1
        local.tree_profiles.cache_clear();critical=[];neutral=[];seen={tuple(colors)}
        for palette in itertools.combinations(range(1,m+1),4):
            profiles,order,forest=palette_profiles(parent,colors,palette)
            if over in palette and under in palette:
                bound,w=joint_at_palette_size(forest,4)
                wanted=(L,)*4
                assert wanted not in profiles
                critical.append({'palette':palette,'forest':forest,'records':len(order),'root_count':len(forest),'joint_bound':bound,'target_L':L,'structural_witness':w,'exact_uniform_profile_absent':True,'attainable_profile_count':len(profiles)})
            for profile,assignment in sorted(profiles.items()):
                trial=colors.copy()
                for v,c in zip(order,assignment):trial[v]=palette[c]
                if local.signature(trial,m)!=old or tuple(trial) in seen:continue
                assert local.valid(trial,edges);seen.add(tuple(trial))
                neutral.append((palette,profile,trial))
        rescue=None;tried=0;limited=False
        for palette,profile,trial in neutral[:128]:
            if time.monotonic()>deadline:limited=True;break
            tried+=1
            nextmove=local.best_three_color(trial,parent,edges,m,k=4)
            if nextmove is None:continue
            sig,pal2,order,assignment,profile2=nextmove
            final=trial.copy()
            for v,c in zip(order,assignment):final[v]=pal2[c]
            assert sig==(L,)*m and local.valid(final,edges)
            changed_classes=sorted({v for i,c in enumerate(final) if c!=colors[i] for v in (colors[i],c)})
            changed_source_classes=sorted({colors[i] for i,c in enumerate(final) if c!=colors[i]})
            assert len(changed_classes)>=5
            rescue={'neutral_palette':palette,'neutral_profile':profile,'neutral_colors':trial,
                    'strict_palette':pal2,'strict_profile':profile2,'optimal_colors':final,
                    'initial_signature':old,'neutral_signature':local.signature(trial,m),
                    'final_signature':sig,'color_classes_with_changed_membership':changed_classes,
                    'original_classes_containing_changed_vertices':changed_source_classes,
                    'neutral_changed_vertices':[i for i,c in enumerate(trial) if c!=colors[i]],
                    'final_changed_vertices':[i for i,c in enumerate(final) if c!=colors[i]]}
            break
        row={'id':cid,'N':len(colors),'m':m,'L':L,'original_loads':counts,'overloaded_color':over,'underloaded_color':under,
             'critical_four_palettes':critical,'all_critical_profiles_exhausted':True,
             'minimum_color_classes_with_changed_membership_lower_bound':5,
             'neutral_candidate_model':'one exact-DP witness per attainable neutral profile and 4-palette; not all neutral colorings',
             'neutral_candidates_generated':len(neutral),'neutral_candidates_tried':tried,
             'neutral_candidate_limit':128,'time_limited':limited,'neutral_then_strict_witness':rescue}
        result.append(row);print(cid,'critical',len(critical),'Jcert',sum(x['joint_bound']>L for x in critical),'neutral',tried,'rescued',rescue is not None,flush=True)
    summary={'case_ids':IDS,'cases':len(result),'critical_palettes':sum(len(r['critical_four_palettes']) for r in result),
             'joint_projection_infeasibility_certificates':sum(p['joint_bound']>r['L'] for r in result for p in r['critical_four_palettes']),
             'neutral_then_strict_rescued':sum(r['neutral_then_strict_witness'] is not None for r in result),
             'seconds':time.monotonic()-started,'budget_seconds':75,'neutral_limit_per_case':128,
             'source_files':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in files],
             'script_sha256':sha(Path(__file__)),'local_algorithm_sha256':sha(ROOT/'scripts/prototype_construction_kempe_20260910.py')}
    dump(OUT/'five_case_analysis.json',result);dump(OUT/'summary.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
