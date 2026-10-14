"""Run the resumable same-run N01 -> N11 -> N12 -> ESMFold2 engineering acceptance."""
import argparse
import base64
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from run_proteinmpnn_acceptance import request as proteinmpnn_request
from structure_integration_cases import cases


NAMESPACE = 'him-ws'
DEPLOYMENT = 'antigen-design'
CONTAINER = 'service'
CODE_CONFIGMAP = 'antigen-n12-same-run-code-r05'
CONTROL_IMAGE_DIGEST = 'sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'
OUT = ROOT / 'discovery/t01-phase1-real/esmfold2-target-20260917/n12-same-run-20260918-r02'
SOURCE_PATHS = (
    't01_phase1_real/development/runtime.py',
    't01_phase1_real/development/proteinmpnn/source.py',
    't01_phase1_real/development/esm_if1/source.py',
    't01_phase1_real/development/thermompnn/source.py',
    't01_phase1_real/development/foldx/source.py',
    't01_phase1_real/development/supervisor.py',
    't01_phase1_real/development/n12_prediction_evidence.py',
    't01_phase1_real/development/esmfold2/source.py',
    't01_phase1_real/development/esmfold2/standard.py',
)


def source_hashes():
    return {p: hashlib.sha256((ROOT / 'src' / p).read_bytes()).hexdigest() for p in SOURCE_PATHS}


def _case():
    return next(row for row in cases() if row['name'] == 'rsa-out-of-domain')


def remote_payload():
    case = _case()
    helper = inspect.getsource(proteinmpnn_request)
    sequence = case['request']['protein_sequence']
    structure_request = json.dumps(case['request'], ensure_ascii=False, sort_keys=True)
    structure_b64 = base64.b64encode(case['data']).decode()
    return f'''import base64
import json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import TERMINAL, RuntimeFault, encode, ensure
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.proteinmpnn import policy as mpnn
from t01_phase1_real.development.esm_if1 import policy as esm_if1
from t01_phase1_real.development.esmfold2 import policy as esmfold2
from t01_phase1_real.development.n12_prediction_evidence import inspect as inspect_prediction

{helper}
mpnn_request = request

SEQUENCE = {sequence!r}
HOST = {case['request']['host_species']!r}
STRUCTURE_REQUEST = json.loads({structure_request!r})
STRUCTURE_BYTES = base64.b64decode({structure_b64!r})
rt = Runtime(Path('/var/lib/t01/runtime'), scope='n12-esmfold2-same-run-r05')
run = rt.create_run('n12-esmfold2-same-run-r05')
run_id = run['run_id']

def result_ref(job):
    ensure(job['state'] == 'succeeded', 'INVALID_STATE', 'Required upstream task did not succeed')
    ref = next((r for r in job['artifacts'] if r['role'] == 'result'), None)
    ensure(ref is not None, 'OUTPUT_INVALID', 'Successful task has no result ArtifactRef')
    ensure(ref['run_id'] == run_id and ref['job_id'] == job['job_id'],
           'OUTPUT_INVALID', 'Result ArtifactRef differs from same-run task')
    return ref

def settle(job, seconds):
    job = rt.get(job['job_id'])
    if job['state'] == 'queued':
        rt.dispatch(job['job_id'])
    elif job['state'] == 'running':
        try:
            rt.recover(job['job_id'])
        except RuntimeFault as exc:
            if exc.code not in ('INVALID_STATE', 'CONFLICT'):
                raise
    elif job['state'] not in TERMINAL:
        raise RuntimeError('Unexpected nonterminal state: ' + job['state'])
    job = rt.wait(job['job_id'], seconds)
    if job['state'] != 'succeeded':
        def clipped(raw, limit=16384):
            text = raw.decode('utf-8', errors='replace')
            if len(text) > limit:
                return text[:limit] + '\\n...[truncated at %d characters]' % limit
            return text

        def failure_artifacts(current):
            """Expose bounded native stdout.txt/stderr.txt and diagnostics without changing state."""
            path_by_id = {{}}
            for ref in current.get('artifacts', []):
                if ref.get('role') != 'diagnostic':
                    continue
                try:
                    diagnostic = json.loads(rt.artifact_bytes(current['job_id'], ref['artifact_id']))
                    for row in diagnostic.get('raw_artifacts', []):
                        artifact = row.get('artifact', {{}})
                        if artifact.get('artifact_id') and row.get('path'):
                            path_by_id[artifact['artifact_id']] = row['path']
                except Exception:
                    pass
            rows = []
            for ref in current.get('artifacts', []):
                if ref.get('role') not in ('log', 'diagnostic'):
                    continue
                item = dict(artifact_id=ref.get('artifact_id'), role=ref.get('role'),
                            path=path_by_id.get(ref.get('artifact_id')),
                            media_type=ref.get('media_type'), size_bytes=ref.get('size_bytes'),
                            sha256=ref.get('sha256'))
                try:
                    item['content'] = clipped(rt.artifact_bytes(current['job_id'], ref['artifact_id']))
                except Exception as exc:
                    item['read_error'] = type(exc).__name__ + ': ' + str(exc)
                rows.append(item)
            return rows

        details = dict(job_id=job.get('job_id'), run_id=job.get('run_id'),
                       state=job.get('state'), error_code=job.get('error_code'),
                       diagnostic=job.get('diagnostic'), stop_reason=job.get('stop_reason'),
                       stop_confirmed=job.get('stop_confirmed'),
                       failure_artifacts=failure_artifacts(job))
        if job.get('attempt_id'):
            details['execution'] = rt.execution(job['job_id'])
        raise RuntimeFault(job.get('error_code') or 'TOOL_FAILED',
                           'Acceptance dependency did not succeed: ' + json.dumps(details, sort_keys=True))
    ensure(job['run_id'] == run_id, 'OUTPUT_INVALID', 'Task escaped acceptance run')
    return job

structure_job = rt.submit_structure_in_run(
    run_id, encode(STRUCTURE_REQUEST), 'n12-r05-structure-1ubq', STRUCTURE_BYTES)
structure_job = settle(structure_job, 300)
structure_ref = result_ref(structure_job)

n11_body = mpnn_request(SEQUENCE, structure_ref, 'N12 same-run engineering source 1UBQ')
n11_job = rt.submit_sequence_in_run(
    run_id, encode(n11_body), 'n12-r05-proteinmpnn', mpnn.TOOL)
n11_job = settle(n11_job, 1200)
n11_ref = result_ref(n11_job)

n12_body = dict(
    protein_sequence=SEQUENCE,
    user_sequence_id='N12 same-run engineering scoring 1UBQ',
    structure_artifact=structure_ref,
    n11_artifact=n11_ref,
    sample_numbers=list(range(1, 25)),
    baseline_artifact=None,
    timeout_seconds=300,
)
n12_job = rt.submit_sequence_in_run(
    run_id, encode(n12_body), 'n12-r05-esm-if1', esm_if1.TOOL)
n12_job = settle(n12_job, 1200)
n12_ref = result_ref(n12_job)
n12_value = rt.result(n12_job['job_id'])
records = [r for r in n12_value['scoring']['records'] if r['score'] is not None]
ensure(records, 'OUTPUT_INVALID', 'No successfully scored original N11 sample is available')
selected = sorted(records, key=lambda r: r['sample_number'])[0]
sample_number = selected['sample_number']
r35 = [r for r in n12_value['engineering_rules']['records'] if r['sample_number'] == sample_number]
ensure(len(r35) == 1, 'OUTPUT_INVALID', 'Original R-35 record is missing')

prediction_body = dict(
    protein_sequence=selected['sequence'],
    user_sequence_id='N12 sample %d explicit ESMFold2 engineering verification' % sample_number,
    host_species=HOST,
    seed=1,
    timeout_seconds=900,
)
prediction_job = rt.submit_sequence_in_run(
    run_id, encode(prediction_body), 'n12-r05-esmfold2-sample-%d' % sample_number, esmfold2.TOOL)
prediction_job = settle(prediction_job, 1800)

with rt._db() as db:
    linkage = inspect_prediction(rt, db, n12_ref, sample_number, prediction_job['job_id'], HOST)
ensure(linkage['r35_original'] == r35[0], 'OUTPUT_INVALID', 'R-35 evidence changed during prediction linkage')
ensure(linkage['scientific_gate'] == 'CLOSED'
       and linkage['usable_for_pipeline'] is False
       and linkage['automatic_handoff'] is False
       and linkage['engine_selection'] == 'EXPLICIT_ENGINEERING_ONLY_NOT_R04',
       'OUTPUT_INVALID', 'Engineering-only prediction linkage qualification changed')

jobs = [structure_job, n11_job, n12_job, prediction_job]
evidence = []
for item in jobs:
    current = rt.get(item['job_id'])
    row = dict(job=current, events=rt.events(current['job_id']), artifacts=[])
    if current.get('attempt_id'):
        row['execution'] = rt.execution(current['job_id'])
    for ref in current['artifacts']:
        raw = rt.artifact_bytes(current['job_id'], ref['artifact_id'])
        ensure(len(raw) == ref['size_bytes'], 'HASH_MISMATCH', 'Artifact size differs')
        row['artifacts'].append(dict(ref=ref, base64=base64.b64encode(raw).decode()))
    evidence.append(row)

receipt = dict(
    status='N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS',
    run_id=run_id,
    structure_job_id=structure_job['job_id'],
    n11_job_id=n11_job['job_id'],
    n12_job_id=n12_job['job_id'],
    prediction_job_id=prediction_job['job_id'],
    selected_sample_number=sample_number,
    selected_scoring_record=selected,
    selected_r35_original=r35[0],
    linkage=linkage,
    scientific_gate='CLOSED',
    usable_for_pipeline=False,
    automatic_handoff=False,
    production_status='NOT_DEPLOYED',
    complete_n12_engineering_acceptance=True,
    complete_scientific_n12=False,
)
print(json.dumps(dict(receipt=receipt, evidence=evidence)))
'''


def _run(cmd, *, data=None, timeout=60):
    return subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout, check=False)


def _kubectl():
    return ['kubectl', '--kubeconfig', str(ROOT / '.tmp/himat.kubeconfig'), '-n', NAMESPACE]


def verify_deployment_and_sources(kc):
    dep = json.loads(subprocess.check_output(kc + ['get', 'deployment', DEPLOYMENT, '-o', 'json']))
    containers = {c['name']: c for c in dep['spec']['template']['spec']['containers']}
    service = containers[CONTAINER]
    if not service['image'].endswith('@' + CONTROL_IMAGE_DIGEST):
        raise RuntimeError('Unexpected control image; prepare/apply the guarded r05 source overlay first')
    if dep['status'].get('observedGeneration') != dep['metadata']['generation'] or dep['status'].get('readyReplicas') != 1:
        raise RuntimeError('Deployment is not fully observed and ready')
    volume = next((v for v in dep['spec']['template']['spec']['volumes'] if v['name'] == 'esmfold2-code'), None)
    if not volume or volume.get('configMap', {}).get('name') != CODE_CONFIGMAP:
        raise RuntimeError('Expected r05 same-run source ConfigMap is not mounted')

    cm = json.loads(subprocess.check_output(kc + ['get', 'configmap', CODE_CONFIGMAP, '-o', 'json']))
    if cm.get('immutable') is not True:
        raise RuntimeError('Expected immutable r05 source ConfigMap')
    items = {row['path']: row['key'] for row in volume['configMap']['items']}
    expected = source_hashes()
    for path, digest in expected.items():
        key = items.get(path)
        if key is None or key not in cm.get('data', {}):
            raise RuntimeError('Required source path is absent from r05 ConfigMap: ' + path)
        if hashlib.sha256(cm['data'][key].encode()).hexdigest() != digest:
            raise RuntimeError('ConfigMap source differs from local acceptance source: ' + path)

    probe = (
        "import hashlib,json;from pathlib import Path;"
        "root=Path('/app/src');paths=" + repr(list(SOURCE_PATHS)) + ";"
        "print(json.dumps({p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}))"
    )
    live = json.loads(subprocess.check_output(
        kc + ['exec', 'deployment/' + DEPLOYMENT, '-c', CONTAINER, '--', 'python', '-B', '-c', probe]))
    if live != expected:
        raise RuntimeError('Live service source hash mismatch; refusing N12 acceptance')
    return dep, expected


def save_and_verify(value, source_identity):
    receipt = value['receipt']
    if receipt['status'] != 'N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS':
        raise RuntimeError('Remote acceptance did not return PASS')
    if receipt['scientific_gate'] != 'CLOSED' or receipt['usable_for_pipeline'] is not False:
        raise RuntimeError('Scientific gate unexpectedly opened')
    if receipt['automatic_handoff'] is not False or receipt['production_status'] != 'NOT_DEPLOYED':
        raise RuntimeError('Automatic handoff or production status changed')
    if receipt['linkage']['engine_selection'] != 'EXPLICIT_ENGINEERING_ONLY_NOT_R04':
        raise RuntimeError('Automatic R-04 routing appeared in engineering acceptance')
    run_id = receipt['run_id']
    expected_jobs = {
        receipt['structure_job_id'], receipt['n11_job_id'],
        receipt['n12_job_id'], receipt['prediction_job_id'],
    }
    observed_jobs = {row['job']['job_id'] for row in value['evidence']}
    if observed_jobs != expected_jobs:
        raise RuntimeError('Evidence job set differs from receipt')
    if any(row['job']['state'] != 'succeeded' or row['job']['run_id'] != run_id for row in value['evidence']):
        raise RuntimeError('Acceptance jobs are not all successful in the exact same run')
    if any(row['job']['usable_for_pipeline'] for row in value['evidence']):
        raise RuntimeError('A task unexpectedly became usable_for_pipeline')

    OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    inventory = []
    for row in value['evidence']:
        folder = OUT / row['job']['job_id']
        folder.mkdir(exist_ok=True)
        for item in row['artifacts']:
            ref = item['ref']
            raw = base64.b64decode(item['base64'], validate=True)
            if len(raw) != ref['size_bytes'] or hashlib.sha256(raw).hexdigest() != ref['sha256']:
                raise RuntimeError('Artifact integrity failure')
            path = folder / ref['sha256']
            if path.exists() and path.read_bytes() != raw:
                raise RuntimeError('Existing local artifact differs: ' + str(path))
            path.write_bytes(raw)
            inventory.append(dict(job_id=row['job']['job_id'], artifact_id=ref['artifact_id'],
                                  sha256=ref['sha256'], size_bytes=ref['size_bytes'],
                                  path=path.relative_to(OUT).as_posix()))
            count += 1
    latest = OUT / 'latest.json'
    latest.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    index = dict(
        status='PASS',
        scope='N12_ESMFOLD2_SAME_RUN_INDEPENDENT_ENGINEERING',
        run_id=run_id,
        source_hashes=source_identity,
        artifacts=inventory,
        artifact_count=count,
        scientific_gate='CLOSED',
        usable_for_pipeline=False,
        automatic_handoff=False,
        production_status='NOT_DEPLOYED',
        complete_scientific_n12=False,
    )
    (OUT / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compile payload and verify local source identity only')
    args = parser.parse_args()
    payload = remote_payload()
    compile(payload, 'n12-esmfold2-same-run-remote', 'exec')
    local_hashes = source_hashes()
    if args.check:
        print('N12_SAME_RUN_PAYLOAD_CHECK_PASS')
        print(json.dumps(local_hashes, sort_keys=True))
        print('No cluster resources were read or changed.')
        return

    kc = _kubectl()
    _, expected = verify_deployment_and_sources(kc)
    result = _run(
        kc + ['exec', '-i', 'deployment/' + DEPLOYMENT, '-c', CONTAINER, '--', 'python', '-u', '-B', '-X', 'utf8', '-'],
        data=payload.encode(), timeout=2100)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors='replace') +
                           '\nRerun this exact command to resume the same run and jobs.')
    value = json.loads(result.stdout)
    count = save_and_verify(value, expected)
    print('ARTIFACTS_VERIFIED', count)
    print('N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS')
    print('SAVED', OUT)


if __name__ == '__main__':
    main()
