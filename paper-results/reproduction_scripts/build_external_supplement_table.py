"""Build the manuscript's stated uniform-cohort table from frozen result JSON.

Reads only original experiment evidence. No benchmark, input change or result
filtering beyond the explicitly enumerated manuscript cohorts is performed.
"""
from pathlib import Path
import csv
import hashlib
import json

MANUSCRIPT = Path(__file__).resolve().parents[1]
ROOT = MANUSCRIPT.parent
VBASE = ROOT/'examples/tifs_external_extension_20260911'
SBASE = ROOT/'examples/tifs_simplepir_extension_20260911'
UNIFORM = ['uniform_n1000', 'uniform_n10000', 'uniform_n100000']
CONTROLS = ['complete_h10', 'complete_h14']


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evidence(source, tag, filename):
    canonical = source/'analysis'/filename
    frozen = MANUSCRIPT/'verification/frozen_evidence'/(tag+'_'+filename)
    frozen.parent.mkdir(parents=True, exist_ok=True)
    if canonical.exists():
        raw = canonical.read_bytes()
        if frozen.exists(): assert frozen.read_bytes() == raw
        else: frozen.write_bytes(raw)
    return frozen


def main():
    source_files = {f'examples/{source.name}/analysis/{name}': evidence(source, tag, name)
                    for source,tag in [(VBASE,'vbpir'),(SBASE,'simplepir')]
                    for name in ['results.json','INDEPENDENT_VERIFICATION.json']}
    v = load(source_files[f'examples/{VBASE.name}/analysis/results.json'])
    s = load(source_files[f'examples/{SBASE.name}/analysis/results.json'])
    indices = {name: {(x['case'], x['method']): x for x in result['aggregates']}
               for name, result in [('VBPIR', v), ('SimplePIR', s)]}
    selected_v = [x for x in v['process_means'] if
                  (x['case'] in UNIFORM and x['method'] in ['ab', 'pbc']) or
                  (x['case'] in CONTROLS and x['method'] in ['ab', 'pbc', 'treepir'])]
    selected_s = [x for x in s['process_means'] if x['case'] in UNIFORM and
                  x['method'] in ['ab', 'pbc', 'flat', 'first_fit']]
    assert len(selected_v) == 36 and len(selected_s) == 36
    assert sum(x['proofs'] for x in selected_v+selected_s) == 720
    for group, cases, methods in [(v, UNIFORM, ['ab', 'pbc']), (v, CONTROLS, ['ab', 'pbc', 'treepir']),
                                  (s, UNIFORM, ['ab', 'pbc', 'flat', 'first_fit'])]:
        for case in cases:
            for method in methods:
                rows = [x for x in group['process_means'] if x['case']==case and x['method']==method]
                assert len(rows)==3 and {x['repeat'] for x in rows}=={0,1,2}
                assert all(x['proofs']==10 for x in rows)
    records = []
    tex = ['% Generated from frozen JSON by build_external_supplement_table.py.',
           '% Each paired numerical cell is AB / PBC.',
           r'\begin{tabular}{lr r r r r r r r}', r'\toprule',
           r'Backend & Leaves & $I$ (s) & $H$ & $A/K$ & $D$ & $S$ & $F$ & RSS (GiB)\\',
           r'\midrule']
    for backend in ['VBPIR', 'SimplePIR']:
        for case in UNIFORM:
            pair = [indices[backend][case, method] for method in ['ab', 'pbc']]
            row = dict(backend=backend, case=case, leaves=int(case.split('n')[-1]), repeats_each=3)
            for method, item in zip(['ab', 'pbc'], pair):
                assert item['complete_planned_repeats'] and item['processes']==3
                row[method+'_setup_seconds'] = item['persistent_setup_wall_ms_mean']/1000
                row[method+'_hint_mib'] = item.get('hint_matrix_bytes_mean', 0)/2**20
                row[method+'_public_A_or_keys_mib'] = (item['public_A_matrix_bytes_mean'] if backend=='SimplePIR' else
                    item['galois_key_payload_bytes_mean']+item['relin_key_payload_bytes_mean'])/2**20
                row[method+'_directory_mib'] = (item['public_metadata_serialized_bytes_mean'] if backend=='SimplePIR' else
                    item['public_map_payload_bytes_mean']+item['common_metadata_payload_bytes_mean'])/2**20
                row[method+'_serialized_initialization_mib'] = item['setup_serialized_payload_bytes_mean']/2**20
                row[method+'_cache_reference_mib'] = (item['full_cache_reference_bytes_mean'] if backend=='SimplePIR' else
                    item['active_digest_payload_bytes_mean']+item['common_metadata_payload_bytes_mean'])/2**20
                row[method+'_digest_only_mib'] = item['active_digest_payload_bytes_mean']/2**20
                row[method+'_combined_peak_rss_gib'] = item['combined_peak_rss_final_bytes_mean']/2**30
            assert row['ab_cache_reference_mib']==row['pbc_cache_reference_mib']
            assert row['ab_digest_only_mib']==row['pbc_digest_only_mib']
            def paired(key):
                return f"{row['ab_'+key]:.2f}/{row['pbc_'+key]:.2f}"
            hint = paired('hint_mib') if backend=='SimplePIR' else '--'
            cited_backend = backend + r'~\cite{' + ('simplepir' if backend=='SimplePIR' else 'vectorbatchpir') + '}'
            tex.append(f"{cited_backend} & {row['leaves']:,} & {paired('setup_seconds')} & {hint} & "
                       f"{paired('public_A_or_keys_mib')} & {paired('directory_mib')} & "
                       f"{paired('serialized_initialization_mib')} & {row['ab_cache_reference_mib']:.2f} & "
                       f"{paired('combined_peak_rss_gib')}" + r' \\')
            records.append(row)
        if backend=='VBPIR':
            tex.append(r'\midrule')
    tex.extend([r'\bottomrule', r'\end{tabular}'])
    generated = MANUSCRIPT/'generated'
    generated.mkdir(exist_ok=True)
    (generated/'external_initialization_rows.tex').write_text('\n'.join(tex)+'\n', encoding='utf8')
    with (MANUSCRIPT/'reproduction_scripts/external_initialization_values.csv').open('w', newline='', encoding='utf8') as out:
        writer=csv.DictWriter(out, fieldnames=list(records[0]))
        writer.writeheader(); writer.writerows(records)
    manifest = dict(scope='Reported uniform scaling cohorts and VBPIR complete-tree controls; not all archived configurations.',
                    uniform_measured_simplepir=360, uniform_measured_vbpir=180,
                    complete_controls_measured_vbpir=180, reported_processes=72,
                    reported_measured_proofs=720, reported_warmups=144, reported_total_verified_proofs=864,
                    selected_simplepir_methods=['ab','pbc','flat','first_fit'],
                    selected_vbpir_uniform_methods=['ab','pbc'], selected_vbpir_control_methods=['ab','pbc','treepir'],
                    backend_sources={'VBPIR_PBC': {'repository':'https://github.com/PIR-PIXR/TreePIR',
                        'commit':'930063c5aefc441244abb4890fdf35383f3aa956'},
                        'SimplePIR': {'repository':'https://github.com/ahenzinger/simplepir',
                        'commit':'e9020b03bf2872c75b8954e749e32408b5db87ed'}},
                    sources={name: sha(path) for name,path in source_files.items()},
                    generator_sha256=sha(Path(__file__)), tables=records,
                    state_boundary='SimplePIR expanded-A received state; VBPIR initialization also includes uploaded evaluation keys. Neither is isolated runtime client RAM.',
                    cache_boundary='Digest plus the same backend-specific common public metadata encoding; not a minimal cache bound.')
    (MANUSCRIPT/'reproduction_scripts/external_core_source_selection.json').write_text(
        json.dumps(manifest, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k:manifest[k] for k in ['reported_processes','reported_measured_proofs','reported_warmups','reported_total_verified_proofs']}))


if __name__=='__main__':
    main()
