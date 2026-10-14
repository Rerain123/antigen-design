import sys
import os
import subprocess

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development import policy as deeptmhmm
from t01_phase1_real.development.proteinmpnn import policy as proteinmpnn

sys.path.insert(0, str(REPO/'scripts'))
from structure_integration_cases import SEQUENCE, cases


def sequence_body(label='same-run'):
    return dict(protein_sequence='ACDEFGHIK', user_sequence_id=label, timeout_seconds=60)


def n11_body(ref):
    return dict(protein_sequence=SEQUENCE, user_sequence_id='same-run-n11', structure_artifact=ref,
        constraints=dict(purpose='ENGINEERING_EXPLICIT_MASKS', source_id='same-run-test', fixed_positions=[1],
            restricted_positions=[dict(position=2, allowed_residues=SEQUENCE[1])],
            open_positions=list(range(3, len(SEQUENCE)+1))),
        n_designs=1, sampling_temperature=0.1, seed=17, timeout_seconds=60)


def structure_result(rt, run_id, key):
    if os.name == 'nt':
        # pytest's private temp-directory ACL uses OWNER RIGHTS. Docker Desktop
        # writes as a different owner; grant only this fixture root to this user.
        account = subprocess.check_output(['whoami'], text=True).strip()
        subprocess.run(['icacls', str(rt.root), '/grant', account + ':(OI)(CI)F', '/T'],
            check=True, capture_output=True)
    fixture=next(row for row in cases() if row['name']=='normal-pdb')
    job=rt.submit_structure_in_run(run_id, encode(fixture['request']), key, fixture['data'])
    rt.dispatch(job['job_id'])
    # Docker cold starts can exceed Runtime.wait's 15-second polling default.
    # Keep the request's 60-second worker budget and wait through reconciliation.
    final=rt.wait(job['job_id'], timeout=90)
    assert final['state']=='succeeded' and final['run_id']==run_id
    return final, next(ref for ref in final['artifacts'] if ref['role']=='result')


def test_sequence_same_run_idempotency_and_conflict(tmp_path):
    rt=Runtime(tmp_path)
    run=rt.create_run('acceptance-run')
    raw=encode(sequence_body())
    first=rt.submit_sequence_in_run(run['run_id'], raw, 'n02', deeptmhmm.TOOL)
    second=rt.submit_sequence_in_run(run['run_id'], raw, 'n02', deeptmhmm.TOOL)
    assert first['run_id']==run['run_id'] and second['job_id']==first['job_id']
    with pytest.raises(RuntimeFault) as exc:
        rt.submit_sequence_in_run(run['run_id'], encode(sequence_body('changed')), 'n02', deeptmhmm.TOOL)
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'


def test_same_run_submission_rejects_foreign_scope(tmp_path):
    owner=Runtime(tmp_path, scope='owner')
    foreign=Runtime(tmp_path, scope='foreign')
    run=foreign.create_run('foreign-run')
    with pytest.raises(RuntimeFault) as exc:
        owner.submit_sequence_in_run(run['run_id'], encode(sequence_body()), 'n02', deeptmhmm.TOOL)
    assert exc.value.code=='FORBIDDEN'


def test_structure_same_run_idempotency(tmp_path):
    rt=Runtime(tmp_path)
    run=rt.create_run('structure-run')
    fixture=next(row for row in cases() if row['name']=='normal-pdb')
    raw=encode(fixture['request'])
    first=rt.submit_structure_in_run(run['run_id'], raw, 'structure', fixture['data'])
    second=rt.submit_structure_in_run(run['run_id'], raw, 'structure', fixture['data'])
    assert first['run_id']==run['run_id'] and second['job_id']==first['job_id']
    with pytest.raises(RuntimeFault) as exc:
        rt.submit_structure_in_run(run['run_id'], raw, 'structure', fixture['data']+b'\n')
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'


def test_same_run_proteinmpnn_keeps_source_provenance_checks(tmp_path):
    rt=Runtime(tmp_path)
    target=rt.create_run('target-run')
    foreign=rt.create_run('foreign-run')
    _, foreign_ref=structure_result(rt, foreign['run_id'], 'foreign-structure')
    with pytest.raises(RuntimeFault) as exc:
        rt.submit_sequence_in_run(target['run_id'], encode(n11_body(foreign_ref)), 'n11-foreign', proteinmpnn.TOOL)
    assert exc.value.code=='FORBIDDEN'

    _, local_ref=structure_result(rt, target['run_id'], 'local-structure')
    job=rt.submit_sequence_in_run(target['run_id'], encode(n11_body(local_ref)), 'n11-local', proteinmpnn.TOOL)
    assert job['run_id']==target['run_id'] and job['tool_id']==proteinmpnn.TOOL


@pytest.mark.parametrize('damage',['sequence','hash'])
def test_same_run_proteinmpnn_still_rejects_corrupt_local_source(tmp_path,damage):
    rt=Runtime(tmp_path);run=rt.create_run('target')
    structure,ref=structure_result(rt,run['run_id'],'structure');body=n11_body(ref)
    if damage=='sequence':
        body['protein_sequence']='A'+SEQUENCE[1:]
    else:
        with rt._db() as db:
            path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
        (rt.root/path).write_bytes(b'changed native artifact')
    with pytest.raises(RuntimeFault) as exc:
        rt.submit_sequence_in_run(run['run_id'],encode(body),'bad-n11',proteinmpnn.TOOL)
    assert exc.value.code in ('OUTPUT_INVALID','HASH_MISMATCH')
