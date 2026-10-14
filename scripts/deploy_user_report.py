"""Stage a hash-bound report overlay; optionally wait for idle and apply once.

No scientific job is started or confirmed. The local waiter expires after 24 h.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

import yaml
import prepare_m1_p1_deploy as common
import prepare_phase1_item3 as overlay

NAME = 'antigen-user-report-r01'
OUT = common.ROOT / 'deploy/user-report/r01'
EVIDENCE = common.ROOT / 'reports/user-report-20260926'
FILES = ('service_api/user_report.py', 'service_api/himat.py', 'service_api/transport.py')
TESTS = ('tests/test_user_report.py', 'tests/test_real_service_api.py',
         'tests/test_himat_p1_fixes.py', 'tests/test_himat_progress.py',
         'tests/test_user_report_deploy.py')
JUNIT = EVIDENCE / 'delivery-tests.junit.xml'
FULL_JUNIT = EVIDENCE / 'full-tests.junit.xml'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bindings():
    paths = [common.ROOT / 'src/t01_phase1_real' / n for n in FILES]
    paths += [common.ROOT / n for n in TESTS]
    paths += [Path(__file__), common.ROOT / 'scripts/first_version_flow_probe.py', common.ROOT / 'scripts/prepare_phase1_item3.py',
              common.ROOT / 'scripts/prepare_m1_p1_deploy.py', JUNIT, FULL_JUNIT]
    return {str(p.relative_to(common.ROOT)).replace('\\', '/'): digest(p) for p in paths}


def tests_passed(path=JUNIT):
    cases = list(ET.parse(path).getroot().iter('testcase'))
    modules = {c.get('classname', '').split('.')[-1] for c in cases}
    return (len(cases) >= 65 and {Path(p).stem for p in TESTS} <= modules
            and all(not any(c.find(n) is not None for n in ('failure', 'error', 'skipped')) for c in cases))


def is_idle(state):
    return state.get('active_jobs') == [] and (state.get('gpu_state') or {}).get('phase') == 'idle'


def live_deployment():
    return json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))


def write(name, value):
    path = OUT / name
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')
    tmp.replace(path)


def status(phase, **extra):
    write('state.json', dict(phase=phase, pid=os.getpid(), updated_at=time.time(), **extra))


def assert_unchanged(pre, live):
    if pre['bindings'] != bindings():
        raise RuntimeError('Staged sources or passing test evidence changed; restage required')
    if (pre['uid'], pre['generation']) != (live['metadata']['uid'], live['metadata']['generation']):
        raise RuntimeError('Another deployment changed the baseline; restage required')
    if any(digest(OUT / n) != h for n, h in pre['prepared_sha256'].items()):
        raise RuntimeError('Prepared deployment artifacts changed')


def stage():
    if not tests_passed():
        raise RuntimeError('Report/API/deployment checks must pass without skips')
    full_cases = list(ET.parse(FULL_JUNIT).getroot().iter('testcase'))
    if len(full_cases) < 2400 or any(c.find('failure') is not None or c.find('error') is not None for c in full_cases):
        raise RuntimeError('Current-root regression must pass; platform skips remain disclosed')
    live = live_deployment()
    overlay.NAME, overlay.FILES = NAME, FILES
    cm, patch, rollback = overlay.render(live)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf8')
    write('deployment.patch.json', patch)
    write('rollback.patch.json', rollback)
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file',
                              str(OUT / 'deployment.patch.json'), '--dry-run=server', '-o', 'name'], check=True)
    write('preflight.json', dict(uid=live['metadata']['uid'], generation=live['metadata']['generation'],
        expires_at=time.time() + 86400, bindings=bindings(),
        prepared_sha256={n: digest(OUT / n) for n in ('configmap.yaml', 'deployment.patch.json', 'rollback.patch.json')}))
    status('STAGED')


def apply_when_idle():
    pre = json.loads((OUT / 'preflight.json').read_bytes())
    # Exclusive claim prevents duplicate waiters or retrying an ambiguous patch.
    with (OUT / 'waiter.claim').open('x', encoding='utf8') as stream:
        stream.write(str(os.getpid()))
    try:
        while time.time() < pre['expires_at']:
            assert_unchanged(pre, live_deployment())
            state = common.idle()
            if is_idle(state):
                break
            status('WAITING_IDLE', active_job_count=len(state['active_jobs']),
                   gpu_phase=(state.get('gpu_state') or {}).get('phase'), expires_at=pre['expires_at'])
            time.sleep(60)
        else:
            status('EXPIRED_NOT_DEPLOYED')
            return
        live = live_deployment()
        assert_unchanged(pre, live)
        patch = json.loads((OUT / 'deployment.patch.json').read_bytes())
        # Only refresh the optimistic lock after validating the unchanged generation.
        patch[1]['value'] = live['metadata']['resourceVersion']
        write('apply.patch.json', patch)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file',
            str(OUT / 'apply.patch.json'), '--dry-run=server', '-o', 'name'], check=True)
        if not is_idle(common.idle()):
            raise RuntimeError('Work arrived during preflight; no rollout requested')
        assert_unchanged(pre, live_deployment())
        status('APPLYING')
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json',
            '--patch-file', str(OUT / 'apply.patch.json')], check=True)
        subprocess.run(common.K + ['rollout', 'status', 'deployment/antigen-design', '--timeout=300s'], check=True)
        expected = {n: pre['bindings']['src/t01_phase1_real/' + n] for n in FILES}
        observed = common.remote('''import json,sys,hashlib
from pathlib import Path
expected=json.load(sys.stdin)
actual={n:hashlib.sha256((Path('/app/src/t01_phase1_real')/n).read_bytes()).hexdigest() for n in expected}
assert actual==expected
from t01_phase1_real.service_api.user_report import render
assert b'<!doctype html>' in render({}).lower()
print(json.dumps(actual))
''', expected)
        live = live_deployment()
        assert live['metadata']['generation'] == live['status']['observedGeneration']
        assert live['status'].get('readyReplicas') == live['status'].get('updatedReplicas') == 1
        # Replay only a completed, owner-authorized historical report through live MCP.
        import first_version_flow_probe as probe
        historical = common.remote(probe.REMOTE, dict(action='status',
            job_id='t01p1r-job-120f08a88827456e83bfdf5e6ef19b92'))
        write('historical-download-check.json', historical)
        assert any(r['file_name'] == 'antigen-report.html' and r['verified']
                   for r in historical['controlled_downloads'])
        write('deployment-receipt.json', dict(generation=live['metadata']['generation'], source_hashes=observed,
            report_overlay_ready=True, scientific_gate='CLOSED', usable_for_pipeline=False,
            production_status='NOT_DEPLOYED', new_scientific_task_started=False))
        status('DEPLOYED_READY')
    except Exception as exc:
        # Keep server stderr/credentials out of the durable summary. No automatic retry/rollback.
        status('STOPPED_REQUIRES_REVIEW', error_type=type(exc).__name__)
        raise


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('stage', 'wait-apply'))
    args = ap.parse_args()
    stage() if args.action == 'stage' else apply_when_idle()
