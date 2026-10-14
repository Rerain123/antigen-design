"""Verify deployed bytes and replay a historical report without starting calculations."""
import hashlib
import json
import subprocess
import prepare_host_panel_deploy as deploy
import prepare_m1_p1_deploy as common
import first_version_flow_probe as probe


def main():
    expected={n:hashlib.sha256((common.ROOT/'src/t01_phase1_real'/n).read_bytes()).hexdigest() for n in deploy.FILES}
    actual=common.remote('''import json,sys,hashlib
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.netmhc import host_panel,pan,policy
from t01_phase1_real.common import encode
expected=json.load(sys.stdin)
actual={n:hashlib.sha256((Path('/app/src/t01_phase1_real')/n).read_bytes()).hexdigest() for n in expected}
assert actual==expected
p=host_panel.manifest('猪');parts=pan.batches('A'*233,p)
assert len(parts)==4 and p['channels']['mhc_i']['count']==76 and p['channels']['mhc_ii']['count']==0
for part in parts:
 b=dict(protein_sequence='A'*233,user_sequence_id='verify',host_species='猪',timeout_seconds=900,
        mhc_i_alleles=part['mhc_i_alleles'],mhc_ii_alleles=[],host_panel_sha256=p['sha256'])
 assert policy.request(encode(b))==b
print(json.dumps(dict(source_hashes=actual,panel_sha256=p['sha256'],batches=len(parts))))
''',expected)
    worker=subprocess.check_output(common.K+['exec','deployment/antigen-design','-c','worker-netmhc','--',
        '/usr/local/bin/python','-B','-c',"import hashlib;print(hashlib.sha256(open('/opt/t01/src/t01_phase1_real/development/netmhc/worker.py','rb').read()).hexdigest())"]).decode().strip()
    assert worker==expected['development/netmhc/worker.py']
    historical=common.remote(probe.REMOTE,dict(action='status',job_id='t01p1r-job-120f08a88827456e83bfdf5e6ef19b92'))
    assert len(historical['controlled_downloads'])==3
    assert any(r['file_name']=='antigen-report.html' for r in historical['controlled_downloads'])
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['metadata']['generation']==live['status']['observedGeneration']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    value=dict(status='HOST_PANEL_AND_HTML_READY',generation=live['metadata']['generation'],**actual,
        worker_hash=worker,controlled_downloads=historical['controlled_downloads'],idle=common.idle(),
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
        native_host_panel_run_verified=False)
    with (deploy.EVIDENCE/'host-panel-deployment.json').open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(value))


if __name__=='__main__':main()
