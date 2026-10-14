"""Read-only deployed permissions/round checks; never starts candidate generation."""
import json
import subprocess
import prepare_phase1_item4 as deploy
import prepare_m1_p1_deploy as common
from t01_phase1_real.common import sha


def main():
    hashes={n:sha((common.ROOT/'src/t01_phase1_real'/n).read_bytes()) for n in deploy.FILES}
    archived=json.loads((common.ROOT/'discovery/t01-phase1-real/phase1-item2-20260925/iedb-bepi-chain-r01.json').read_bytes())
    value=common.remote('''import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.design_backend import permissions,policy
from t01_phase1_real.development.workflow import design_rounds,policy as flow
p=json.load(sys.stdin)
observed={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['hashes']}
assert observed==p['hashes']
rt=Runtime('/var/lib/t01/runtime',scope='phase1-item2-engineering-r01')
j=rt.get(p['n06']);req=decode(rt._request_bytes(j))
ref=next(r for r in j['artifacts'] if r['role']=='result')
with rt._db() as db:_,_,mapped=rt._registered_result_artifact(db,ref,'t01.real.epitope_map')
body=dict(protein_sequence=req['protein_sequence'],user_regions=[],epitope_mode='both',membrane_design_confirm=False)
receipts={n:dict(state='missing',artifact=None) for n in policy.PRODUCERS}
receipts['epitope_map']=dict(state='available',artifact=ref)
perms=permissions.assemble(body,dict(epitope_map=mapped),receipts,decode((policy.HERE/'scales.json').read_bytes()))
e3=[e for r in perms['per_residue'] for e in r['evidence_source'] if e['rule']=='S27_E3_REGION_RESTRICTED']
assert e3 and all(e['artifact']==ref for e in e3)
assert not perms['scientific_release'] and rt.get(j['job_id'])==j
checks=[]
for count,temp in design_rounds.ROUNDS:
    generated=dict(records=[dict(sample_number=i) for i in range(1,count+1)])
    scored=dict(engineering_rules=dict(records=[dict(sample_number=i,passed=False) for i in range(1,count+1)]))
    decision=design_rounds.disposition(generated,scored)
    assert decision['status']=='ALL_REJECTED'
    checks.append(dict(count=count,temperature=temp,decision=decision,fixture=True))
order=flow.order(dict(engineering_design='BACKEND_EVIDENCE_V1'))
assert order.index('retry2_design_audit')<order.index('preselection')
print(json.dumps(dict(status='ITEM4_DEPLOYED_READONLY_CHECK_PASS',source_hashes=observed,
    real_e3=dict(job_id=j['job_id'],run_id=j['run_id'],artifact=ref,evidence_count=len(e3),archived_job_unchanged=True),
    round_fixture_checks=checks,order=order,native_48_64_generation='NOT_EXECUTED',
    new_design_workflow_started=False,new_candidates_generated=False,
    scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
''',dict(hashes=hashes,n06=archived['n06_job']['job_id']))
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['metadata']['generation']==live['status']['observedGeneration']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    value['generation']=live['metadata']['generation'];value['idle']=common.idle()
    assert not value['idle']['active_jobs'] and value['idle']['gpu_state']['phase']=='idle'
    with (deploy.EVIDENCE/'deployment-r01.json').open('x',encoding='utf8') as stream:json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=value['status'],generation=value['generation'],e3_evidence_count=value['real_e3']['evidence_count'])))


if __name__=='__main__':main()
