"""Read frozen external-comparison runs; write complete accounting and provenance."""
from pathlib import Path
import hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'examples/tifs_contribution_gate_20260910/external'
COMMIT='930063c5aefc441244abb4890fdf35383f3aa956'
def read(p):return json.loads(p.read_text())
def source(path,lines):return f'https://github.com/PIR-PIXR/TreePIR/blob/{COMMIT}/{path}#L{lines}'
def stat(xs):return {'mean':statistics.mean(xs),'sample_sd':statistics.stdev(xs) if len(xs)>1 else None,'processes':len(xs)}
def main():
    simple=read(OUT/'common_simplepir/summary.json');native=read(OUT/'native_vbpir/authenticated_common_runs/summary.json');audit=read(OUT/'independent_raw_audit.json')
    names={'treepir_official':'Official TreePIR layout','first_fit':'First-fit','activebalance':'ActiveBalance'}
    result=[]
    for g in simple['groups']:
        h,method=g['height'],g['method'];raw=[read(OUT/f'common_simplepir/h{h}/repeat{rep}/{method}/backend_result.json') for rep in range(3)]
        result.append({'height':h,'layout':method,'source':'same unchanged SimplePIR backend',
          'initialization':{'backend_setup_ms':stat([r['setup']['total_setup_wall_ms'] for r in raw]),'hint_payload_bytes':g['metrics']['hint_bytes']['mean'],'expanded_public_A_payload_bytes':g['metrics']['public_A_bytes']['mean'],'serialized_bootstrap_bytes':None,'bootstrap_NA_reason':'No transport/bootstrap serialization in this component harness.'},
          'online':{k:g['metrics'][k] for k in ['client_query_ms','server_answer_ms','client_decode_ms','backend_wall_ms','online_total_bytes']},
          'client_storage':{'hint_plus_expanded_A_bytes':g['metrics']['hint_bytes']['mean']+g['metrics']['public_A_bytes']['mean'],'scope':'PIR payload only: excludes indexing, secret state, objects and allocator overhead. Not full client RAM.',
                             'independent_client_RSS_bytes':None,'client_RSS_NA_reason':'The runner combines client and server; its VmHWM cannot isolate client memory.',
                             'combined_process_peak_RSS_bytes':stat([r['process_peak_rss_bytes'] for r in raw])},
          'full_system_E2E_ms':None,'E2E_NA_reason':'Backend wall excludes online indexing, root verification, process launch, serialization and transport; no native common-service E2E run.'})
    for r in native['rows']:
        result.append({'height':10,'layout':r['method'],'source':'official VBPIR core + portability and external authentication adapter',
          'initialization':{'backend_setup_ms':None,'serialized_bootstrap_bytes':None,'NA_reason':'Official main creates fresh server/client objects per target but does not time setup or serialize bootstrap.'},
          'online':{'query_ms':r['query_us']/1000,'answer_ms':r['answer_us']/1000,'recover_ms':r['recover_us']/1000,'unit':'one process, mean over 10 targets with fresh objects; descriptive only',
                    'original_query_estimate_KiB':r['query_artifact_estimate_KB'],'original_answer_estimate_KiB':r['answer_artifact_estimate_KB'],'actual_wire_bytes':None,'wire_NA_reason':'No transport. Original estimates use save_size()/2 and save_size(), then integer division by 1024.'},
          'client_storage':{'bytes':None,'independent_client_RSS_bytes':None,'NA_reason':'Native executable combines client/server and does not measure serialized keys/state or process RSS.'},
          'full_system_E2E_ms':None,'E2E_NA_reason':'Root verification is external and untimed; native executable has no client/server transport.'})
    (OUT/'comparison_metrics.json').write_text(json.dumps({'rows':result,'same_backend_paired_intervals':audit['paired_timing_differences'],
          'payload_only_cache_control':{'height4_bytes':960,'height10_bytes':65472,'all_occupied_target_proofs':1040,'full_system_cache_timing':None,
          'scope':'Full-tree heap positions implicit from public height; same pinned root and selected known value are common inputs. Digest payloads are materialized and checked, but a complete cache service/bootstrap is not timed.'}},indent=2)+'\n')
    lines=['# Fair external TreePIR comparison — contribution gate','',
      '**Result:** on two genuinely common complete-tree instances, ActiveBalance and the official TreePIR algorithm have identical optimal load multisets, identical SimplePIR matrix shapes, and identical communication/hint/public-A payload sizes. No incremental layout advantage over TreePIR is established. An actual official VBPIR query/recovery path was also completed with a separate common-root verifier. A native common TCP service experiment remains **not completed**.','',
      '## Fair protocol and attribution','',
      f'- Official repository: https://github.com/PIR-PIXR/TreePIR, pinned commit `{COMMIT}` (HEAD checked on 2026-09-11). The 12 downloaded source files match the historical local copy byte-for-byte. All 55 copied VBPIR source/build-header files were additionally checked against Git blob IDs from the official commit tree.',
      '- Common inputs are fully occupied height-4 and height-10 binary trees: 16/1024 leaves and 30/2046 non-root 32-byte records. No height-128 expansion, pruning, omitted defaults, duplicate records, or sparse-vs-complete size mismatch is introduced. All methods retrieve exactly the same standard membership proofs from the same digests, known values, and pinned roots.',
      '- The official unmodified Java CSA produces the ordered buckets. The official unmodified SubCSA fast index is separately run on every leaf; both results agree at every color/position. The faithful sibling swap stores original digest v at swapped position v xor 1. Two new Java wrappers only call and serialize the original classes.',
      '- First-fit and the frozen original Hungarian ActiveBalance (20-scan budget) are called directly through the current SMT implementation. Nonempty-depth is not used or relabeled as TreePIR.',
      '- The common SimplePIR test uses the unchanged eight-chunk backend: 8 × 32-bit chunks, LWE dimension 1024, logq=32, sigma=6.4, plaintext modulus 991, sequential GOMAXPROCS=1. Indices are prepared before the backend timers for every layout. This isolates backend consequences; it is not a measurement of TreePIR\'s native indexing/storage advantage. In particular, the official height-based fast index need not store our audit directory.',
      '- Three independent backend processes per method/height: all 16 targets at h4, 32 paired targets at h10, five warmups per process. Method order and target order are seeded and shuffled per repeat. The independent auditor replays both schedules. The statistical unit is a process mean, not an individual target.',
      '- The VBPIR block uses the same h10 snapshot and ten paired boundary/spread targets. One process per layout executes the official fresh-server/client-per-target sequence, without warmup. It is a functional authenticated component demonstration with descriptive timing, not repeated-process significance evidence.',
      '- Historical indexing-only perfectized ratios and earlier native smoke logs are not pooled or used as new performance evidence. The old notes\' ASCII working directory no longer exists. A new independent VBPIR copy was built in this experiment.','',
      '## Common layout and SimplePIR results','',
      '| h | Layout | U | Q / Answer / Recover ms | Backend wall ms (mean ± process SD) | Online matrix payload B | Hint B | Public A B |',
      '|---:|---|---:|---|---|---:|---:|---:|']
    for g in simple['groups']:
        m=g['metrics'];lines.append(f"| {g['height']} | {names[g['method']]} | {m['max_bucket']['mean']} | {m['client_query_ms']['mean']:.3f} / {m['server_answer_ms']['mean']:.3f} / {m['client_decode_ms']['mean']:.3f} | {m['backend_wall_ms']['mean']:.3f} ± {m['backend_wall_ms']['sample_sd']:.3f} | {m['online_total_bytes']['mean']} | {m['hint_bytes']['mean']} | {m['public_A_bytes']['mean']} |")
    lines += ['',
      'TreePIR and AB have loads (7,7,8,8) at h4 and four 204s plus six 205s at h10. They attain ceil(N/h). h4 selects L=8,M=4; h10 selects L=28,M=30. The equality of matrix shapes and bytes is deterministic. First-fit has larger maximum buckets but fewer aggregate online and initialization payload bytes at both points; reducing maximum capacity alone does not minimize this backend\'s total communication.','',
      'Paired AB-minus-TreePIR backend wall differences (three process pairs, descriptive 95% Student-t intervals with df=2):']
    for h,p in audit['paired_timing_differences'].items():
        ci=p['95pct_t_df2_interval_ms'];lines.append(f"- h{h}: {p['AB_minus_official_backend_wall_ms']:.6f} ms, interval [{ci[0]:.6f}, {ci[1]:.6f}] ms.")
    lines += ['','Both intervals include zero. These results do not establish a latency advantage or equivalence. No additional repeats were added to seek significance.','',
      '## Initialization, client storage, and E2E boundaries','',
      '| h | Layout | Backend setup ms, mean ± SD | Hint + expanded A payload B | Combined-process peak RSS MiB, mean | Full-system E2E |',
      '|---:|---|---|---:|---:|---|']
    for r in result[:6]:
        init=r['initialization']['backend_setup_ms'];mem=r['client_storage'];lines.append(f"| {r['height']} | {names[r['layout']]} | {init['mean']:.3f} ± {init['sample_sd']:.3f} | {mem['hint_plus_expanded_A_bytes']} | {mem['combined_process_peak_RSS_bytes']['mean']/2**20:.3f} | N/A |")
    lines += ['',
      'Backend setup is the existing Go initialization interval; it excludes Java/Python layout construction and process startup. Hint+A is a matrix-payload byte count, **not** measured serialized bootstrap or complete client storage. Indexing data, secret state, object overhead and allocator overhead are excluded. The reported RSS belongs to one combined server/client process, never to an isolated client. Serialized bootstrap bytes and full client RAM are N/A. Backend wall excludes online indexing, standard-root verification, output serialization, network and process launch; it must not be compared as TCP E2E.','',
      'The payload-only complete-cache controls are 960 B (h4) and 65472 B (h10), stored in complete_h*/full_cache_digest_payload.bin. All 1040 target proofs are checked from these files. A complete tree has implicit heap positions determined by public height; pinned root and the selected known leaf are common inputs. This is a payload-only control, not a measured cache service. Both PIR layouts\' hint payloads alone exceed these entire digest payloads. No full-cache process latency, complete bootstrap or client RSS is claimed.','',
      '## Actual official VBPIR core with external authentication','',
      '| Layout, h10 | Query ms | Answer ms | Recover ms | Original artifact query/answer estimate, KiB | Init / client storage / native E2E |',
      '|---|---:|---:|---:|---|---|']
    for r in native['rows']:lines.append(f"| {names[r['method']]} | {r['query_us']/1000:.3f} | {r['answer_us']/1000:.3f} | {r['recover_us']/1000:.3f} | {r['query_artifact_estimate_KB']} / {r['answer_artifact_estimate_KB']} | N/A / N/A / N/A |")
    lines += ['',
      'These rows are deliberately separate from the SimplePIR rows. VBPIR uses the original BFV degree 8192, coefficient-modulus bit sizes [42,58,58,60], 28-bit plaintext modulus, first dimension 64 and dimensions [64,4], with 256 rounded entries for the 205-record buckets. Both layouts select the identical parameters. The dependency is installed SEAL 4.3.2, not a reproduction of the paper\'s original SEAL 4.0 environment.','',
      '**The 385/257 KiB values are the original artifact\'s estimates, not measured bytes:** query cost sums Ciphertext.save_size()/2 and answer cost sums save_size(), then both are integer-divided by 1024. No ciphertext transport is executed. They must not be placed in a common byte column with Go matrix payloads or TCP socket measurements. Initialization is untimed in native main; native client state/keys/RSS are unmeasured. The whole-process wall time includes repeated object setup and printing, while the external Python verifier executes afterward. It is not native proof-service E2E.','',
      'The C++ query, answer and recovery algorithms are unchanged. Source adaptations are limited to C++17, resolving the installed SEAL CONFIG package, one missing <cstdint> include, and replacing hard-coded input-directory strings with TREEPIR_INPUT_DIR. The original layout data input is replaced with our checked common snapshot. After recovery, a separate standard-library verifier reconstructs the original root from all ten actual recovered digests and the known leaf and rejects a bit flip. This adaptation supports **official backend + authenticated common-task verification**, not an unmodified native full system.','',
      'The public native VBPIR main checks recovered entries against the server\'s RAW_DB, not a client-pinned root. The public SealPIR gRPC path exists, but its client does not perform a standard Merkle root check (its optional raw-value ValidateResult call is commented out). We did not build an additional network/authentication layer or report it as an original artifact feature. The full native common-service/TCP gate remains not completed.','',
      '## Evidence and reproduction','',
      '- common_instance_layouts.json; complete_h4/ and complete_h10/: official CSA/fast-index TSVs, all-target routes, identical digests/roots, raw binary buckets, and payload-only full-cache files.',
      '- common_simplepir/: 18 raw backend JSONs with all recovered digests, manifests, targets/orders, process logs, process_measurements.csv and query_measurements.csv. All 432 measured proofs/3456 recovered sibling records pass.',
      '- native_vbpir/authenticated_common_runs/: original stdout with all recovered digests, ten targets per layout, component summaries and separate independent_root_verification.json. All 20 measured proofs pass. native_vbpir/smoke/ is a separate two-proof development check and is not pooled.',
      '- independent_raw_audit.json: independently rebuilt roots, 3120 all-target layout checks, 1040 cache proof checks, the 432+20 actual recoveries, bitflip rejection, matrix-derived byte counts, source hashes and paired statistics.',
      '- SOURCE_AUDIT.md: official source URLs/line numbers, actual source hashes, dependency/build modifications and initial failure log.',
      '- comparison_metrics.json: machine-readable initialization, online, client-storage and E2E accounting; unavailable fields are explicit nulls with reasons.','',
      'Linux/WSL requirements: Python 3 with matplotlib for imported layout helpers, JDK, Go/C compiler for the common SimplePIR binary, CMake/G++ and SEAL 4.3.2 for this native reproduction. Run from a fresh project copy preserving relative input paths; measured directories are intentionally protected from overwrite:',
      '```bash',
      'python scripts/fetch_contribution_gate_treepir_20260910.py',
      'python scripts/prepare_contribution_gate_treepir_20260910.py',
      'python scripts/prepare_contribution_gate_vbpir_20260910.py',
      '# In an empty result copy, run the following serially:',
      'python scripts/run_contribution_gate_common_backend_20260910.py',
      'python scripts/run_contribution_gate_vbpir_20260910.py',
      '# For an existing measured copy, these checks do not repeat timing:',
      'python scripts/audit_contribution_gate_external_20260910.py',
      'python scripts/report_contribution_gate_external_20260910.py',
      '```','',
      'The unchanged common Go source is backend/simplepir/tifs_full_proof_backend.go, compiled from .tools/simplepir/simplepir-main/go.mod. Its reused binary is examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend. Both source and binary are pinned in external_evidence_manifest.json. Native build commands and complete diagnostics are retained in native_vbpir/configure_log.json and build_log.json; the first missing-include failure is preserved separately. No paper or historical result was modified.']
    (OUT/'FAIR_EXTERNAL_COMPARISON.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    refs=[('CSA/src/MerkleTrees.java','78-L88','Official sibling swap; record at swapped node x is the original digest at x xor 1.'),
          ('CSA/src/CSA.java','176-L190','Ordered bucket JSON serialization.'),('CSA/src/CSA.java','335-L398','Official ColorSplitting and recursive traversal called by the wrapper.'),
          ('CSA/src/CSA.java','509-L535','Balanced color sequence used without reimplementation.'),('TreePIR-Indexing/src/SubCSA.java','349-L406','One-based target-leaf path and node IDs.'),
          ('TreePIR-Indexing/src/SubCSA.java','480-L549','Official mapIndices called independently for every leaf.'),
          ('VBPIR_TreePIR/src/main.cpp','163-L199','Original fresh server/client per target and Query/Answer/Recover timing boundaries; setup timers commented out.'),
          ('VBPIR_TreePIR/src/main.cpp','204-L211','Native communication estimates use save_size(), including division by two for query estimate.'),
          ('VBPIR_TreePIR/src/main.cpp','225-L243','Original recovery check reads server RAW_DB and counts matching entries; not a root verifier.'),
          ('VBPIR_TreePIR/src/batchpirserver.cpp','87-L90','Native balanced-bucket capacity formula ceil(N/h).'),
          ('VBPIR_TreePIR/src/batchpirparams.cpp','39-L45','Original fixed first dimension 64.'),
          ('VBPIR_TreePIR/src/utils.h','108-L123','Original BFV parameters.'),
          ('SealPIRplus/pirmessage_client.cpp','80-L114','Decoded bytes are printed; ValidateResult is commented out and is raw-value equality, not Merkle verification.'),
          ('SealPIR-Orchestrator/orchestrator.py','63-L106','Public gRPC route exists as a separate orchestration path; not run in this comparison.')]
    pins=read(OUT/'official_source_manifest.json')['files'];nativepins=read(OUT/'native_vbpir/source_derivation.json')
    sr=['# Official source audit','',f'Pinned repository commit: `{COMMIT}`. [Official commit](https://github.com/PIR-PIXR/TreePIR/commit/{COMMIT}).',
        '', '[Original full paper](https://arxiv.org/html/2205.05211v5): §II-A defines the swapped tree, Algorithm 1 defines retrieval, Algorithms 2–3 give CSA and fast indexing; Appendix J already discusses sparse Merkle coloring. We do not treat complete-tree-only code as a claim that the authors ignored SMTs.','',
        '| Source lines at pinned commit | Role in this comparison | SHA-256 |','|---|---|---|']
    for path,ls,role in refs:
        info=pins.get(path) or nativepins['verified_original_files'][path]
        sr.append(f'| [{path}:{ls}]({source(path,ls)}) | {role} | `{info["sha256"]}` |')
    sr += ['','## Adaptation boundary','',
        'The two Java wrappers call unchanged official classes and serialize outputs only. All original downloaded bytes and Git blob IDs are pinned; no replacement coloring algorithm is labeled official.',
        '', 'Native VBPIR source_derivation.json records the 55 original verified files and each adapted-file hash. Four source/build locations change: CMake C++ standard/package resolution; database_constants.h adds <cstdint>; main.cpp and batchpirserver.cpp use an environment-selected directory. Main query/answer/recovery and its original timers are otherwise unchanged. Build configuration detects SEAL 4.3.2. The first build failed on the missing uint64_t include and is preserved in build_attempt1.json; the second build succeeds.','',
        'Native authentication is a separate verifier in run_contribution_gate_vbpir_20260910.py, independently rechecked by audit_contribution_gate_external_20260910.py. It runs on the recovered byte output and a pinned root, but is outside the original C++ timers. A complete shared client/server transport experiment was not performed.','']
    (OUT/'SOURCE_AUDIT.md').write_text('\n'.join(sr),encoding='utf8')
    sourcefiles=list((ROOT/'scripts').glob('*contribution_gate*20260910*'))+[ROOT/'backend/simplepir/tifs_full_proof_backend.go',ROOT/'examples/tifs_revision_20260910/backend_smoke/tifs_full_proof_backend',ROOT/'.tools/simplepir/simplepir-main/go.mod']
    sourcefiles += list((ROOT/'.tools/simplepir/simplepir-main/pir').glob('*.go'))+list((ROOT/'.tools/simplepir/simplepir-main/pir').glob('*.c'))+list((ROOT/'.tools/simplepir/simplepir-main/pir').glob('*.h'))
    sourcefiles += [ROOT/'scripts'/p for p in ['tifs_revision_smt.py','fixed_sparse_tree_coloring.py','generate_full_sparse_smt_example.py','run_height_sparsity_profile_balance_experiment.py','run_sparse_smt_pir_backend_experiment.py','run_tifs_verified_backend_suite_20260910.py']]
    artifacts=[p for p in OUT.rglob('*') if p.is_file() and 'build' not in p.parts and 'java_build' not in p.parts and p.name!='external_evidence_manifest.json']
    artifacts += [OUT/'native_vbpir/source/build/bin/vbpir_treepir']
    (OUT/'external_evidence_manifest.json').write_text(json.dumps({'official_commit':COMMIT,
      'script_and_dependency_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sourcefiles if p.exists()},
      'artifact_sha256':{str(p.relative_to(OUT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in artifacts}},indent=2)+'\n')
    print('Report, four-category cost matrix, source audit, and complete evidence pins generated.')
if __name__=='__main__':main()
