"""Read deployed sources and run an isolated N10 engineering probe, no design."""
import json
import subprocess

import prepare_phase1_item3 as deploy
import prepare_m1_p1_deploy as common
from t01_phase1_real.common import sha


def main():
    files=deploy.FILES+('development/structure/normalization.py','development/domains/geometry.py',
                       'development/domains/compute.py','development/domains/service.py')
    hashes={n:sha((common.ROOT/'src/t01_phase1_real'/n).read_bytes()) for n in files}
    result=common.remote('''import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,sha
p=json.load(sys.stdin)
observed={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['hashes']}
assert observed==p['hashes']
rt=Runtime('/var/lib/t01/runtime',scope='phase1-item3-engineering-r01')
body=dict(protein_sequence='ACDEFGHIKLMNPQRSTVWY',user_sequence_id='c44-engineering-aa20',
    structure_input=dict(state='not_provided',artifact=None,reason_code=None),
    target_ph=None,target_ph_range=[4.0,8.0],dimension_weights=None,timeout_seconds=30)
job=rt.submit_sequence(encode(body),'item3-n10-r01','t01.real.developability')
if job['state']=='queued':job=rt.dispatch(job['job_id'])
assert job['state']=='succeeded'
value=rt.result(job['job_id'])
assert value['steps']['solubility']['global_score'] is None
assert value['steps']['solubility']['intermediate_terms']['eq1_raw'][0]>0.96
assert value['developability']['overall_score'] is None
assert value['developability']['dev_dims_available']==1
assert not value['usable_for_pipeline'] and not value['automatic_handoff']
print(json.dumps(dict(status='ITEM3_DEFINED_PARTIAL_BRANCHES_DEPLOYED',source_hashes=observed,
    job=job,result=value,new_design_workflow_started=False,new_candidates_generated=False)))
''',dict(hashes=hashes))
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['status']['observedGeneration']==live['metadata']['generation']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    result['generation']=live['metadata']['generation'];result['idle']=common.idle()
    assert not result['idle']['active_jobs'] and result['idle']['gpu_state']['phase']=='idle'
    with (deploy.EVIDENCE/'deployment-r01.json').open('x',encoding='utf8') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(dict(status=result['status'],generation=result['generation'],job_id=result['job']['job_id'])))


if __name__=='__main__':main()
