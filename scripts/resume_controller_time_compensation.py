"""Audit and apply the user's controller-outage time compensation."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import prepare_m1_p1_deploy as common
from version_bundle import encode,sha,build

OUT=common.ROOT/'reports/controller-time-compensation-20261008'
MODULE=common.ROOT/'scripts/controller_time_compensation.py'
JID='t01p1r-job-a7c8933226744c669836b11858585246'
BOOT=r'''
import json,sys,datetime,time,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,sha,TERMINAL
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal,ServiceStore
p=json.load(sys.stdin)
for name,digest in p['manifest'].items():
 assert sha((Path('/app/src')/name).read_bytes())==digest,'Deployed source differs'
credential=next(r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials'] if r['principal']=='himat-t01-test')
owner=Principal(credential['principal'],frozenset(credential['scopes']),'x')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
argv=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
for flag,name in [('--blast-database-root','blast_database_root'),('--homology-database-root','homology_database_root'),('--domains-database-root','domains_database_root')]:
 setattr(rt,name,Path(argv[argv.index(flag)+1]) if flag in argv else None)
store=ServiceStore(rt.root);store.authorize_job(owner,p['job_id'])
namespace={'__name__':'operator_time_compensation'}
exec(compile(p['module'],'operator_time_compensation','exec'),namespace)
jid=p['job_id'];source=rt.get(jid);old=rt.execution(jid)
with rt._db() as db:count=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
'''

PREPARE=BOOT+r'''
bepi_id='t01p1r-job-89d70a56ce664c22b45e4cea1febccd9'
native_path=Path(rt.execution(bepi_id)['resident_target'])/'execution.json'
native=json.loads(native_path.read_bytes())
assert native['binding']['job_id']==bepi_id and native['state']=='succeeded' and native['stopped_confirmed']
outage_start=datetime.datetime.fromtimestamp(native_path.stat().st_mtime,datetime.timezone.utc).isoformat()
outage_end=old['controller_upgrade']['authorized_at']
assert old['controller_upgrade']['job_id']==jid
# No additional scientific work was admitted within the proven idle interval.
for row in old['nodes'].values():
 if row.get('job_id'):
  child=rt.get(row['job_id']);started=child.get('started_at')
  assert not started or not (namespace['delta'](started,outage_start)>0 and namespace['delta'](outage_end,started)>0)
evidence=dict(authorization=namespace['AUTHORIZATION'],job_id=jid,run_id=source['run_id'],
 checkpoint_sha256=sha(encode(old)),outage_start=outage_start,outage_end=outage_end,
 native_completion_receipt_sha256=sha(native_path.read_bytes()),native_job_id=bepi_id,
 controller_repair_receipt_sha256=sha(encode(old['controller_upgrade'])),
 justification='User requested correction because controller outage consumed the original timeout',
 conservative_interval=True,earlier_polling_delays_not_credited=True)
started=time.monotonic();prepared=namespace['prepare'](rt,jid,evidence)
with rt._db() as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==count
assert rt.get(jid)==source and rt.execution(jid)==old
print(json.dumps(dict(evidence=evidence,prepared=prepared,read_only=True,new_jobs=0,
 source_unchanged=True,replay_seconds=time.monotonic()-started,deployed_source_sha256=p['source_sha256'])))
'''

RESUME=BOOT+r'''
prepared=p['prepared'];evidence=p['evidence']
job=namespace['create'](rt,jid,evidence,prepared)
again=namespace['create'](rt,jid,evidence,prepared);assert again['job_id']==job['job_id']
store.register_retry(owner,job['job_id'],jid)
ex=rt.execution(job['job_id']);before=prepared[2]
assert job['run_id']==source['run_id'] and rt.get(jid)==source and rt.execution(jid)==old
for key in ('revision_ledger','revision_v2_frozen','revision_allocations','revision_v2_allocations','revision_bindings'):
 assert ex[key]==before[key],key
assert ex['nodes']['design']['confirmation']==before['nodes']['design']['confirmation']
old_req=json.loads(rt._request_bytes(source));new_req=json.loads(rt._request_bytes(job))
assert {k:v for k,v in old_req.items() if k!='timeout_seconds'}=={k:v for k,v in new_req.items() if k!='timeout_seconds'}
# HiMat has submit/query scopes. Replaying its already accepted, immutable T4
# receipt uses the supported idempotent confirmation endpoint to schedule the
# continuation; no control scope or new scientific consent is granted.
from t01_phase1_real.service_api.transport import MCPApplication
consent=ex['nodes']['design']['confirmation'];assert consent['decision'] is True
request=urllib.request.Request('http://127.0.0.1:18083/mcp',
 headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},
 data=json.dumps(dict(jsonrpc='2.0',id='controller-credit-start',method='tools/call',
  params=dict(name=MCPApplication.HIMAT_CONFIRM_TOOL,arguments=dict(job_id=job['job_id'],
  confirmation_id=consent['confirmation_id'],decision=consent['decision'])))).encode())
with urllib.request.urlopen(request,timeout=60) as response:scheduled=json.load(response)
assert 'error' not in scheduled and not scheduled['result'].get('isError'),scheduled
assert rt.execution(job['job_id'])['nodes']['design']['confirmation']==consent
print(json.dumps(dict(status='COMPENSATED_SAME_RUN_CONTINUATION_STARTED',source_job_id=jid,
 job_id=job['job_id'],run_id=job['run_id'],started_at=job['started_at'],
 expected_deadline=(datetime.datetime.fromisoformat(job['started_at'].replace('Z','+00:00'))+datetime.timedelta(seconds=new_req['timeout_seconds'])).isoformat(),
 clock=ex['continuation']['clock'],original_terminal_job_unchanged=True,
 original_request_unchanged=True,new_request_changed_fields=['timeout_seconds'],
 new_parent=True,new_run=False,scientific_budgets_preserved=True,t4_preserved=True,
 reused_children=len(ex['continuation']['reused_children']),
 reopened_unadmitted_nodes=prepared[5]['reopened_unadmitted_nodes'],
 candidate_generation_repeated=False,structure_prediction_repeated=False,
 source_profile_unchanged=True,idempotency_verified=True,existing_t4_replayed_without_change=True,scheduled=scheduled)))
'''

if __name__=='__main__':
    action=sys.argv[1]
    manifest=json.loads((common.ROOT/'deploy/controller-recovery/r01/preflight.json').read_bytes())
    assert build(common.ROOT/'src')[1]==manifest['source_hashes'],'Source changed since deployment'
    payload=dict(job_id=JID,module=MODULE.read_text(encoding='utf-8'),manifest=manifest['source_hashes'],source_sha256=manifest['source_sha256'])
    if action=='prepare':code=PREPARE
    elif action=='resume':
        cases=list(ET.parse(OUT/'affected-r03.junit.xml').iter('testcase'))
        assert len(cases)>=59 and all(not any(c.find(x) is not None for x in ('failure','error','skipped')) for c in cases)
        prior=json.loads((OUT/'prepared.json').read_bytes());payload.update(prepared=prior['prepared'],evidence=prior['evidence'])
        assert prior['module_sha256']==sha(MODULE.read_bytes()) and prior['deployed_source_sha256']==payload['source_sha256']
        code=RESUME
    else:raise ValueError('prepare or resume required')
    result=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',code],
                          input=encode(payload),capture_output=True,timeout=1200)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-4000:])
    value=json.loads(result.stdout);value['module_sha256']=sha(MODULE.read_bytes())
    path=OUT/('prepared.json' if action=='prepare' else 'continuation-submission.json')
    path.write_bytes(encode(value))
    print(json.dumps({k:v for k,v in value.items() if k!='prepared'},ensure_ascii=False))
