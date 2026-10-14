"""Deploy tested controller repair at the authorized, stopped-child checkpoint."""
import concurrent.futures
import datetime
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,encode,sha

ROOT=release.common.ROOT
EVIDENCE=ROOT/'reports/controller-recovery-20261008'
OUT=ROOT/'deploy/controller-recovery/r01'
JID='t01p1r-job-a7c8933226744c669836b11858585246'
BASE=ROOT/'deploy/himat-report-repair/r01/preflight.json'
release.EVIDENCE=EVIDENCE;release.OUT=OUT

BOOT='''import json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import encode,sha,TERMINAL
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset({'control','query'}),'x').runtime_scope)
p=json.load(sys.stdin);jid=p['job_id']
'''


def regression():
    tested=json.loads((EVIDENCE/'tested-source.json').read_bytes())
    if build(ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Tested source changed')
    paths=[EVIDENCE/n for n in ('full-final.junit.xml','affected-final.junit.xml')]
    cases=list(ET.parse(paths[0]).iter('testcase'))
    affected=list(ET.parse(paths[1]).iter('testcase'))
    failures=[c for c in cases if any(c.find(k) is not None for k in ('failure','error'))]
    if failures:
        allowed={('tests.test_same_run_submission',n) for n in (
            'test_same_run_proteinmpnn_keeps_source_provenance_checks',
            'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[sequence]',
            'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[hash]')}
        assert {(c.get('classname'),c.get('name')) for c in failures}==allowed
        path=EVIDENCE/'docker-recheck.junit.xml';paths.append(path)
        checks=list(ET.parse(path).iter('testcase'))
        assert len(checks)==6 and all(c.get('classname')=='tests.test_same_run_submission' and
            not any(c.find(k) is not None for k in ('failure','error','skipped')) for c in checks)
        index={(c.get('classname'),c.get('name')):c for c in cases}
        index.update({(c.get('classname'),c.get('name')):c for c in checks});cases=list(index.values())
    if len(cases)<3100 or len(affected)<92 or any(any(c.find(k) is not None for k in ('failure','error')) for c in cases+affected):
        raise RuntimeError('Complete final-source regression and affected tests must pass')
    return dict(total=len(cases),passed=sum(c.find('skipped') is None for c in cases),
        skipped=sum(c.find('skipped') is not None for c in cases),affected=len(affected),
        original_local_docker_failures=len(failures),single_all_green_full_run=not bool(failures),
        receipts={p.name:sha(p.read_bytes()) for p in paths})


def quiescent():
    value=release.common.remote(BOOT+'''
with rt._db() as db:
 active=[json.loads(r[0]) for r in db.execute('SELECT data FROM jobs') if json.loads(r[0])['state'] not in TERMINAL]
assert len(active)==1 and active[0]['job_id']==jid
j=rt.get(jid);ex=rt.execution(jid)
assert j['state']=='running' and not j['stop_reason'] and not ex.get('dispatcher') and not ex.get('pending_confirmation')
for row in ex['nodes'].values():
 if row.get('job_id'):
  child=rt.get(row['job_id']);assert child['state'] in TERMINAL
  assert not child.get('attempt_id') or rt.execution(child['job_id']).get('tree_stopped') is True
from pathlib import Path
gpu=json.loads(Path('/var/lib/t01/resident/unified-gpu/state.json').read_bytes());assert gpu['phase']=='idle'
print(json.dumps(dict(status='QUIESCENT_AUTHORIZED_CONTROLLER_REPAIR',job_id=jid,checkpoint_sha256=sha(encode(ex)),gpu_state=gpu)))
''',dict(job_id=JID))
    return value


def authorize():
    pre=json.loads((OUT/'preflight.json').read_bytes())
    assert build(ROOT/'src')[1]==pre['source_hashes'] and regression()==pre['regression']
    from t01_phase1_real.development.workflow.policy import registered_profile
    profile=registered_profile()
    patch=(ROOT/'src/t01_phase1_real/service_api/controller_recovery.py').read_text(encoding='utf-8')
    checkpoint=quiescent()['checkpoint_sha256']
    result=release.common.remote(BOOT+'''
namespace={'__name__':'t01_phase1_real.service_api.controller_recovery','__package__':'t01_phase1_real.service_api'}
exec(compile(p['module'],'operator_controller_recovery','exec'),namespace)
receipt=namespace['authorize'](rt,jid,p['profile'],p['checkpoint'])
print(json.dumps(receipt))
''',dict(job_id=JID,module=patch,profile=profile,checkpoint=checkpoint))
    (EVIDENCE/'upgrade-authorization.json').write_bytes(encode(result))
    print(json.dumps(result))


def verify():
    import verify_version_unification as base
    pre=json.loads((OUT/'preflight.json').read_bytes());assert build(ROOT/'src')[1]==pre['source_hashes']
    live=json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
    assert live['spec']['template']==json.loads((OUT/'deployment.patch.json').read_bytes())[-1]['value']
    assert live['status'].get('readyReplicas')==1 and live['status'].get('updatedReplicas')==1
    before=json.loads((EVIDENCE/'before-deployment.json').read_bytes())
    for a,b in zip(before['spec']['template']['spec']['containers'],live['spec']['template']['spec']['containers']):
        assert {k:v for k,v in a.items() if k!='volumeMounts'}=={k:v for k,v in b.items() if k!='volumeMounts'}
    def check(container):
        name=container['name'];python='python' if name=='service' else '/opt/t01/supervisor/bin/python3.11'
        r=subprocess.run(release.common.K+['exec','-i','deployment/antigen-design','-c',name,'--',python,'-B','-c',base.REMOTE],
            input=encode(dict(container=name,manifest=pre['source_hashes'])),capture_output=True,timeout=150)
        if r.returncode:raise RuntimeError(name+': '+r.stderr.decode(errors='replace')[-1200:])
        return json.loads(next(s[7:] for s in r.stdout.decode().splitlines() if s.startswith('VERIFY=')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(check,live['spec']['template']['spec']['containers']))
    value=dict(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        generation=live['metadata']['generation'],source_sha256=pre['source_sha256'],files=len(pre['source_hashes']),
        containers=results,resources_images_commands_unchanged=True,
        existing_authorized_workflow_may_progress=True,new_independent_run=False)
    (EVIDENCE/'deployment-verification.json').write_bytes(encode(value))
    print(json.dumps({k:v for k,v in value.items() if k!='containers'}))


if __name__=='__main__':
    action=sys.argv[1]
    if action=='authorize':authorize()
    elif action=='verify':verify()
    else:
        if action in ('prepare','apply'):
            live=json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
            assert live['spec']['template']['metadata']['annotations']['antigen-design/source-sha256']==json.loads(BASE.read_bytes())['source_sha256']
        if action=='apply':
            approval=json.loads((EVIDENCE/'upgrade-authorization.json').read_bytes())
            from t01_phase1_real.development.workflow.policy import registered_profile
            assert approval['to_profile']==registered_profile()
        release.deploy.idle=quiescent;release.regression=regression
        release.main()
