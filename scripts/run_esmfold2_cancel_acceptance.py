"""Operator-run real inference cancellation plus controller recovery, resumable."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'discovery/t01-phase1-real/esmfold2-target-20260917/lifecycle-20260918-r01'
REMOTE=r'''
import base64,json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.esmfold2 import policy
from t01_phase1_real.common import encode,TERMINAL
from t01_phase1_real.resident_process import atomic
rt=Runtime(Path('/var/lib/t01/runtime'),scope='esmfold2-cancel-20260918-r01')
b=dict(protein_sequence='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG',user_sequence_id='esmfold2-cancel-r01',host_species='Homo sapiens',seed=1,timeout_seconds=600)
j=rt.submit_sequence(encode(b),'esmfold2-cancel-r01',policy.TOOL)
j=rt.dispatch(j['job_id'])
ex=rt.execution(j['job_id']); target=Path(ex['resident_target'])
receipt_path=target/'execution.json'
receipt=json.loads(receipt_path.read_bytes()) if receipt_path.exists() else {}
marker=target/'operator-recovery.json'
if receipt.get('state')=='running' and not marker.exists():
    before=dict(job_id=j['job_id'],attempt_id=j['attempt_id'],target=str(target),process_identity=receipt['process_identity'])
    rt.recover(j['job_id'])
    after=rt.execution(j['job_id'])
    assert after['resident_target']==str(target)
    assert rt.get(j['job_id'])['attempt_id']==before['attempt_id']
    atomic(marker,dict(before=before,after_target=after['resident_target'],kind='explicit_controller_recovery_no_pod_restart'))
log=target/'output/stdout.txt'
stdout=log.read_text(errors='replace') if log.exists() else ''
started='ESMFOLD2_INFERENCE_START' in stdout
if started and j['state'] not in TERMINAL:
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='inference-cancel-r01')))
j=rt.reconcile(j['job_id']);ex=rt.execution(j['job_id'])
value=dict(job=j,execution=ex,inference_started=started,recovery=json.loads(marker.read_bytes()) if marker.exists() else None,terminal=j['state'] in TERMINAL)
if value['terminal']:
    value['events']=rt.events(j['job_id']);value['result']=rt.result(j['job_id']);value['artifacts']=[]
    for ref in j['artifacts']:
        value['artifacts'].append(dict(ref=ref,base64=base64.b64encode(rt.artifact_bytes(j['job_id'],ref['artifact_id'])).decode()))
print(json.dumps(value))
'''

def process_probe(receipt):
    # kubectl exec does not inherit environment set inside resident_worker.main.
    # Select its persistent registry before importing posix (REGISTRY is cached).
    return ("import os,json; os.environ['T01_PROCESS_REGISTRY']='/var/lib/t01/resident/esmfold2/.processes'; "
            "from t01_phase1_real.process_control.posix import Job; name="+repr(receipt['process_name'])+
            "; expected="+repr(receipt['process_identity'])+
            "; job=Job(name,create=False); record=job._record(); assert record['leader']==expected; "
            "print(json.dumps(dict(process_name=name,active=job.active(),process_identity=record['leader'],registry=str(job.path))))")

def validate(value,process):
    j=value['job']; ex=value['execution']; receipt=ex['resident_receipt']; recovery=value['recovery']
    if not (j['state']=='cancelled' and j['stop_confirmed'] and ex['tree_stopped'] and receipt['stopped_confirmed']):
        raise ValueError('Cancellation and process-tree stop not confirmed')
    if not value['inference_started'] or not recovery: raise ValueError('Inference/recovery evidence missing')
    before=recovery['before']
    if before['attempt_id']!=j['attempt_id'] or before['target']!=ex['resident_target'] or before['process_identity']!=receipt['process_identity']:
        raise ValueError('Recovery changed execution identity')
    if j['usable_for_pipeline'] or value['result']['prediction'] is not None:
        raise ValueError('Cancelled prediction must not be usable')
    if process['active']!=0 or process['process_name']!=receipt['process_name'] or process['process_identity']!=receipt['process_identity']:
        raise ValueError('Owned process group still active or identity differs')

def main(*, payload=REMOTE, output=OUT, validator=validate,
         success='ESMFOLD2_INFERENCE_CANCEL_AND_CONTROLLER_RECOVERY_PASS'):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();compile(payload,'remote-lifecycle','exec')
    if args.check:print('PAYLOAD_SYNTAX_OK_NO_CLUSTER_ACTION');return
    kc=['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n','him-ws','--request-timeout=45s']
    dep=json.loads(subprocess.check_output(kc+['get','deployment','antigen-design','-o','json']))
    pod=dep['spec']['template']['spec']
    image=next(c['image'] for c in pod['containers'] if c['name']=='service')
    if not image.endswith('@sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'):
        raise ValueError('Expected r03 deployment')
    if dep['status'].get('observedGeneration')!=dep['metadata']['generation'] or dep['status'].get('readyReplicas')!=1:
        raise ValueError('Deployment not ready')
    output.mkdir(parents=True,exist_ok=True)
    def remote(container,payload):
        result=subprocess.run(kc+['exec','-i','deployment/antigen-design','-c',container,'--','python','-B','-'],input=payload.encode(),capture_output=True,timeout=65)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')+'\nRerun the same command to resume this task.')
        return json.loads(result.stdout)
    deadline=time.monotonic()+720
    while time.monotonic()<deadline:
        value=remote('service',payload)
        (output/'latest.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(job_id=value['job']['job_id'],state=value['job']['state'],inference_started=value['inference_started'],recovery_recorded=bool(value.get('recovery')))),flush=True)
        if value['terminal']:
            for a in value['artifacts']:
                raw=base64.b64decode(a['base64'],validate=True);ref=a['ref']
                if hashlib.sha256(raw).hexdigest()!=ref['sha256'] or len(raw)!=ref['size_bytes']:raise ValueError('Artifact mismatch')
                (output/ref['sha256']).write_bytes(raw)
            receipt=value['execution'].get('resident_receipt',{})
            name=receipt.get('process_name')
            if not name:raise ValueError('No process ownership evidence')
            probe=process_probe(receipt)
            process=remote('worker-esmfold2',probe)
            (output/'process-check.json').write_text(json.dumps(process,indent=2),encoding='utf-8')
            validator(value,process)
            print(success,flush=True)
            print('SAVED',output);return
        time.sleep(2)
    raise RuntimeError('Local wait limit reached; rerun same command to resume.')

if __name__=='__main__':main()
