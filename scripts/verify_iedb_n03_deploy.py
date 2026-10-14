"""Read-only deployment and HiMat routing check; no workflow submission."""
import json
import subprocess
import prepare_m1_p1_deploy as c
import prepare_iedb_n03_deploy as deployment
import verify_himat_p1_fixes as old


def main():
    pre=json.loads((deployment.OUT/'preflight.json').read_bytes())
    service=c.remote(old.REMOTE,dict(job_id=old.JOB,files=list(deployment.FILES)))
    assert service['source_hashes']==pre['deployed_hashes']
    worker_code='''import json,hashlib
from pathlib import Path
names=('development/blast/worker.py','development/blast/iedb.py')
print(json.dumps({n:hashlib.sha256((Path('/opt/t01/src/t01_phase1_real')/n).read_bytes()).hexdigest() for n in names}))
'''
    hashes=json.loads(subprocess.check_output(c.K+['exec','deployment/antigen-design','-c','worker-blast','--',
        '/opt/t01/supervisor/bin/python3.11','-B','-c',worker_code]))
    assert all(pre['deployed_hashes'][n]==h for n,h in hashes.items())
    routing=c.remote('''import json,ast,inspect
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
class Capture:
 def submit(self,p,body):self.body=body;return dict(state='queued')
s=Capture();a=HiMatIntegration(s,'https://example.invalid',b'x'*32)
p=Principal('himat-t01-test',frozenset(['submit']),'probe-not-credential')
r=a.submit_sequence(p,'ACDEFGHIKLMNPQRSTVWY','Homo sapiens','routing-probe')
assert '.progress import project' not in inspect.getsource(HiMatIntegration.check)
print(json.dumps(dict(blast=s.body['request']['analysis']['blast'],input_profile=r['input_profile'],
    idempotency_key=s.body['idempotency_key'],p2_live_check_preserved=True,actual_submit_called=False)))
''')
    assert routing['blast']['database_id']=='iedb-20260924-r01'
    assert routing['blast']['database_manifest_sha256']=='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12'
    assert routing['blast']['thresholds']==dict(identity_percent_min=70,query_coverage_percent_min=80)
    live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
    assert live['status'].get('readyReplicas')==1
    assert live['status']['observedGeneration']==live['metadata']['generation']
    state=c.idle()
    value=dict(status='IEDB_N03_DEPLOYED_READONLY_VERIFIED',generation=live['metadata']['generation'],
        service=service,worker_hashes=hashes,routing=routing,idle=state,
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    (c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/iedb-deployment-r11.json').write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(dict(status=value['status'],generation=value['generation'],routing=routing,old_nr_hsps=service['blast_replay_hsps'])))


if __name__=='__main__':main()
