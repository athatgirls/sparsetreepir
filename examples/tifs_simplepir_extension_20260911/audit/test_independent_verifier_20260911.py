"""Bounded mutation checks for the auditor; never execute or alter PIR/raw runs."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).absolute().parents[3]
BASE = ROOT/'examples/tifs_simplepir_extension_20260911'
SCRIPT = ROOT/'scripts/analyze_simplepir_extension_20260911.py'
spec = importlib.util.spec_from_file_location('independent_auditor', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def write(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def mutate_recovered(result):
    item = result['queries'][0]['recovered_by_bucket'][0]
    raw = bytes.fromhex(item['record_hex'])
    item['record_hex'] = (bytes([raw[0]^1])+raw[1:]).hex()


def mutate_position(result):
    item = result['queries'][0]['recovered_by_bucket'][0]
    item['position'] = (item['position']+1) % 1998
    result['queries'][0]['positions_by_query'][0] = item['position']


def mutate_proof(result):
    result['queries'][0]['proof_bottom_up_hex'][0] = '01'*32


def main():
    smoke = BASE/'smoke'
    config = audit.read(smoke/'run_configuration.json')
    source_outcome = next(x for x in audit.read(smoke/'process_outcomes.json')
                          if x['case']=='uniform_n1000' and x['method']=='flat')
    scheduled = next(x for x in audit.read(smoke/'schedule.json') if audit.triple_key(x)==audit.triple_key(source_outcome))
    old = smoke/'uniform_n1000/flat/repeat0'
    original = audit.read(old/'result.json')
    sources = audit.SourceAudit(BASE/'inputs', audit.VBPIR)
    audit.validate_process(source_outcome, scheduled, config, smoke, sources)
    checks = []
    mutations = [
        ('forged_decoded_digest_with_pass_flags', mutate_recovered, 'ACTUAL recovered digest differs'),
        ('wrong_bucket_position', mutate_position, 'record/position mismatch'),
        ('forged_proof_with_pass_flags', mutate_proof, 'actual recovery/defaults'),
        ('warmup_flag_changed', lambda r: r['warmups'][0].update(warmup=False), 'warmup flags'),
        ('query_frame_underreported', lambda r: r['queries'][0].update(query_framed_bytes=r['queries'][0]['query_framed_bytes']-4), 'framing formula'),
        ('hint_underreported', lambda r: r['setup'].update(hint_matrix_bytes=r['setup']['hint_matrix_bytes']-4), 'setup hint_matrix_bytes'),
        ('flat_state_duplicated', lambda r: r['setup'].update(initialized_databases=13), 'physical DB/state'),
        ('changed_security_parameter', lambda r: r['parameters']['params'].update(N=512), 'security parameter'),
    ]
    with tempfile.TemporaryDirectory(prefix='simplepir_audit_mutations_') as temporary:
        temporary = Path(temporary)
        for name, mutate, expected_error in mutations:
            runs = temporary/name
            directory = runs/'uniform_n1000/flat/repeat0'
            directory.mkdir(parents=True)
            for filename in ['input.json', 'command.json']:
                shutil.copyfile(old/filename, directory/filename)
            result = copy.deepcopy(original)
            mutate(result)
            write(directory/'result.json', result)
            outcome = dict(source_outcome, result_sha256=audit.sha(directory/'result.json'))
            write(directory/'status.json', outcome)
            # Re-hash mutated output/status deliberately: tests substantive
            # checks beyond merely noticing a changed result file checksum.
            try:
                audit.validate_process(outcome, scheduled, config, runs, sources)
            except ValueError as error:
                if expected_error not in str(error):
                    raise AssertionError((name, str(error), expected_error)) from error
                checks.append(dict(test=name, mutation_rejected=True, reason=str(error)))
            else:
                raise AssertionError(f'Auditor accepted mutation: {name}')
        empty = temporary/'no_results'
        empty.mkdir()
        for filename in ['run_configuration.json', 'schedule.json', 'input_availability.json']:
            shutil.copyfile(smoke/filename, empty/filename)
        write(empty/'process_outcomes.json', [])
        output = temporary/'empty_analysis'
        subprocess.run([sys.executable, str(SCRIPT), '--runs', str(empty), '--output', str(output)],
                       check=True, stdout=subprocess.DEVNULL)
        verification = audit.read(output/'INDEPENDENT_VERIFICATION.json')
        assert verification['status']=='no_verified_evidence'
        assert not verification['complete_requested_experiment']
        assert not verification['scheduled_executed_all']
        checks.append(dict(test='no_process_outcomes_cannot_pass', mutation_rejected=True,
                           reason=verification['status']))
    destination = BASE/'audit/VERIFIER_MUTATION_CHECKS.json'
    write(destination, dict(status='passed', tests=len(checks), checks=checks,
                            auditor_sha256=audit.sha(SCRIPT), test_script_sha256=audit.sha(Path(__file__)),
                            scope='No backend execution; original raw evidence unchanged. Mutated clones rehashed so semantic checks are tested.'))
    print(json.dumps(dict(status='passed', tests=len(checks), output=str(destination))))


if __name__=='__main__':
    main()
