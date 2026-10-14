"""Deploy hash verification and a complete short-sequence native pan check."""
import argparse
import json
import subprocess
import sys

import prepare_m1_p1_deploy as c
import prepare_phase1_item2 as deploy

PRELUDE='''import json,sys,time,shutil
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.netmhc import pan,service
rt=Runtime('/var/lib/t01/runtime',scope='phase1-item2-engineering-r01',blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
p=json.load(sys.stdin)
'''


def save(name,value):
    deploy.EVIDENCE.mkdir(parents=True,exist_ok=True)
    with (deploy.EVIDENCE/name).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['deployment','start','tick','drive','audit'])
    ap.add_argument('--receipt',choices=['r01','r02','r03'],default='r01')
    ap.add_argument('--probe',choices=['r01','r02'],default='r01');args=ap.parse_args()
    if args.action=='drive':
        for _ in range(240):
            completed=subprocess.run([sys.executable,'-X','utf8','-B',__file__,'tick','--probe',args.probe],capture_output=True,text=True,check=True)
            print(completed.stdout.strip(),flush=True)
            if json.loads(completed.stdout)['state'] in ('succeeded','failed','cancelled','timed_out'):return
        raise RuntimeError('Drive budget elapsed; durable job remains available for recovery')
    if args.action=='deployment':
        result=c.remote(PRELUDE+'''
hashes={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['files']}
assert hashes==p['hashes']
panel=pan.manifest()
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
class Capture:
    def submit(self,principal,value):self.body=value['request'];return dict(job_id='not-submitted',state='queued')
capture=Capture();adapter=HiMatIntegration(capture,'https://example.invalid',b'x'*32)
adapter.submit_sequence(Principal('himat-t01-test',frozenset(['submit']),'not-a-credential'),'ACDEFGHIKLMNPQR','Sus scrofa')
assert capture.body['analysis']['netmhc']==pan.options()
print(json.dumps(dict(status='ITEM2_DEPLOYED_HASHES_PASS',source_hashes=hashes,panel_manifest=panel,
    himat_netmhc=capture.body['analysis']['netmhc'],disk=shutil.disk_usage(rt.root)._asdict(),
    scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
''',dict(files=deploy.FILES,hashes=deploy.hashes()))
        live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
        support=result['panel_manifest']['channels']
        expected={'/tools/src/'+v['availability']['model_member']:v['availability']['model_member_sha256']
                  for v in support.values()}
        native=json.loads(subprocess.check_output(c.K+['exec','deployment/antigen-design','-c','worker-netmhc','--',
            'python','-B','-c',"import hashlib,json;from pathlib import Path;print(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in "+repr(list(expected))+"}))"]))
        assert native==expected
        result['native_model_pseudosequence_hashes']=native
        assert live['status']['observedGeneration']==live['metadata']['generation']
        assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
        result['generation']=live['metadata']['generation'];save('deployment-'+args.receipt+'.json',result)
        print(json.dumps(dict(status=result['status'],generation=result['generation'])));return
    if args.action=='start':
        result=c.remote(PRELUDE+'''
body=dict(protein_sequence='ACDEFGHIKLMNPQR',user_sequence_id='complete-pan-engineering-probe',host_species='Sus scrofa',**pan.options())
job=rt.submit_sequence(encode(body),'item2-complete-pan-'+p['probe'],'t01.real.netmhc')
job=rt.dispatch(job['job_id'])
print(json.dumps(dict(job_id=job['job_id'],run_id=job['run_id'],state=job['state'],request=body,
    purpose='FULL_PACKAGE_INVENTORY_ENGINEERING_CHECK_NOT_A_BIOLOGICAL_DESIGN')))
''',dict(probe=args.probe))
        save('pan-run-'+args.probe+'.json',result);print(json.dumps(result));return
    run=json.loads((deploy.EVIDENCE/('pan-run-'+args.probe+'.json')).read_bytes())
    if args.action=='tick':
        print(json.dumps(c.remote(PRELUDE+'''
start=time.monotonic()
while time.monotonic()-start<35:
    job=rt.recover(p['job_id'])
    if job['state'] in ('succeeded','failed','cancelled','timed_out'):break
    time.sleep(.2)
ex=rt.execution(p['job_id']);ids=ex.get('batches',[])
last=rt.get(ids[-1]) if ids else None
print(json.dumps(dict(state=job['state'],error_code=job['error_code'],submitted_batches=len(ids),
    last_batch=dict(job_id=last['job_id'],state=last['state'],error_code=last['error_code']) if last else None,
    storage_preflight=ex.get('storage_preflight'),diagnostic=ex.get('diagnostic'))))
''',run)));return
    result=c.remote(PRELUDE+'''
job=rt.get(p['job_id']);value=rt.result(job['job_id'])
assert job['state']=='succeeded'
service.verify_sources(rt,job,value)
assert all(v['status']=='parsed_unreviewed' for v in value['channels'].values())
assert value['panel_selection']['completed_batches']==value['panel_selection']['required_batches']==738
assert {k:v['observed_rows'] for k,v in value['channels'].items()}==dict(mhc_i=442470,mhc_ii=11069)
# Exercise the actual registered N06/N07 chain, retaining the native N05 refs.
ref=rt.source_input(job['job_id'],'t01.real.netmhc')
body=dict(protein_sequence=p['request']['protein_sequence'],user_sequence_id='item2-pan-chain',
    bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),netmhc_input=ref,
    blast_input=dict(state='not_executed',artifact=None,reason_code='INDEPENDENT_N05_ENGINEERING_CHECK'),timeout_seconds=60)
n06=rt.submit_sequence_in_run(job['run_id'],encode(body),'item2-n06-r01','t01.real.epitope_map')
n06=rt.dispatch(n06['job_id']);assert n06['state']=='succeeded'
context=rt.n06_hotspot_input(n06['job_id'],body['protein_sequence'])
n07body=dict(protein_sequence=body['protein_sequence'],user_sequence_id='item2-pan-chain',hotspot_input=context,timeout_seconds=60)
n07=rt.submit_sequence_in_run(job['run_id'],encode(n07body),'item2-n07-r01','t01.real.glycosylation')
n07=rt.dispatch(n07['job_id']);assert n07['state']=='succeeded'
assert rt.result(n07['job_id'])['hotspot_assessment']['status']=='NOT_PERFORMED'
assert rt.result(n07['job_id'])['glycosylation']['shielding_risk'] is False
print(json.dumps(dict(status='COMPLETE_PAN_N06_N07_NATIVE_PASS',job=job,result=value,
    n06_job=n06,n06_result=rt.result(n06['job_id']),n07_job=n07,n07_result=rt.result(n07['job_id']),
    scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
''',run)
    save('pan-native-chain-'+args.probe+'.json',result)
    print(json.dumps(dict(status=result['status'],panel=result['result']['panel_selection'])))


if __name__=='__main__':main()
