"""Real ESMFold2 execution with a 30-second deadline; no synthetic sleep or cancel."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.run_esmfold2_cancel_acceptance import ROOT, main as run

OUT=ROOT/'discovery/t01-phase1-real/esmfold2-target-20260917/timeout-20260918-r01'
REMOTE=r'''
import base64,json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.esmfold2 import policy
from t01_phase1_real.common import encode,TERMINAL
rt=Runtime(Path('/var/lib/t01/runtime'),scope='esmfold2-timeout-20260918-r01')
b=dict(protein_sequence='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG',user_sequence_id='esmfold2-timeout-r01',host_species='Homo sapiens',seed=1,timeout_seconds=30)
j=rt.submit_sequence(encode(b),'esmfold2-timeout-r01',policy.TOOL)
j=rt.dispatch(j['job_id']);j=rt.reconcile(j['job_id'])
ex=rt.execution(j['job_id']);target=Path(ex['resident_target'])
log=target/'output/stdout.txt'
stdout=log.read_text(errors='replace') if log.exists() else ''
value=dict(job=j,execution=ex,terminal=j['state'] in TERMINAL,inference_started='ESMFOLD2_INFERENCE_START' in stdout)
if value['terminal']:
    request_path=target/'request.json'
    value['resident_request']=json.loads(request_path.read_bytes())
    value['native_request_started']=(target/'output/native/native-request.json').is_file()
    value['cancel_file_present']=(target/'cancel').exists()
    observation=target/'output/executor-observation.json'
    value['observation']=json.loads(observation.read_bytes()) if observation.exists() else None
    value['events']=rt.events(j['job_id']);value['result']=rt.result(j['job_id']);value['artifacts']=[]
    for ref in j['artifacts']:
        value['artifacts'].append(dict(ref=ref,base64=base64.b64encode(rt.artifact_bytes(j['job_id'],ref['artifact_id'])).decode()))
print(json.dumps(value))
'''

def validate(value,process):
    j=value['job'];ex=value['execution'];receipt=ex['resident_receipt']
    if not (j['state']=='timed_out' and j['error_code']=='TIMEOUT' and j['stop_confirmed']
            and ex['tree_stopped'] and receipt['state']=='timed_out' and receipt['stopped_confirmed']):
        raise ValueError('Actual timeout and process-tree stop required')
    if value['resident_request']['timeout_seconds']!=30 or ex['timeout_seconds']!=30:
        raise ValueError('Deadline changed')
    if value['cancel_file_present'] or not value['native_request_started']:
        raise ValueError('Must time out during real native execution, without cancellation')
    if not value['observation'] or value['observation'].get('network_restriction')!='seccomp-local-sockets-only-v1':
        raise ValueError('Offline executor evidence missing')
    if j['usable_for_pipeline'] or value['result']['prediction'] is not None:
        raise ValueError('Timed-out prediction must not be usable')
    if process['active']!=0 or process['process_name']!=receipt['process_name'] or process['process_identity']!=receipt['process_identity']:
        raise ValueError('Owned process group still active or identity differs')

if __name__=='__main__':
    run(payload=REMOTE,output=OUT,validator=validate,success='ESMFOLD2_NATIVE_EXECUTION_TIMEOUT_PASS')
