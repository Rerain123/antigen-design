"""Operator-run new ESMFold2 -> N01 acceptance; reruns resume the same task."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'discovery/t01-phase1-real/esmfold2-target-20260917/backend-r03'
REMOTE = r"""
import base64,json
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,TERMINAL
from t01_phase1_real.development.workflow.policy import OPTIONS
rt=Runtime(Path('/var/lib/t01/runtime'),scope='esmfold2-acceptance-r03')
body=dict(protein_sequence='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG',
 user_sequence_id='esmfold2-backend-ubiquitin-r03',host_species='Homo sapiens',
 expression_host=None,organism=None,structure=None,analysis={n:None for n in OPTIONS},
 reuse_jobs={},timeout_seconds=1800,prediction=dict(engine='esmfold2',seed=1,timeout_seconds=600))
j=rt.submit_workflow(encode(body),'esmfold2-backend-r03')
j=rt.dispatch(j['job_id'])
view=rt.workflow(j['job_id'])
value=dict(job=j,nodes=view['nodes'],terminal=j['state'] in TERMINAL)
if value['terminal']:
    value['evidence']=[]
    ids=[j['job_id']]+[r['job_id'] for r in view['nodes'].values() if r.get('job_id')]
    for jid in dict.fromkeys(ids):
        job=rt.get(jid)
        row=dict(job=job,execution=rt.execution(jid),events=rt.events(jid),artifacts=[])
        for ref in job['artifacts']:
            raw=rt.artifact_bytes(jid,ref['artifact_id'])
            row['artifacts'].append(dict(ref=ref,base64=base64.b64encode(raw).decode()))
        value['evidence'].append(row)
print(json.dumps(value))
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='Compile remote payload only; no cluster operation')
    args=parser.parse_args()
    compile(REMOTE,'esmfold2-acceptance-remote','exec')
    if args.check:
        print('PAYLOAD_SYNTAX_OK_NO_CLUSTER_ACTION');return
    kc=['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n','him-ws']
    dep=json.loads(subprocess.check_output(kc+['get','deployment','antigen-design','-o','json']))
    containers={c['name']:c for c in dep['spec']['template']['spec']['containers']}
    expected='sha256:0e572b386fd2ad45d3d9b844910b3ff6fb01ce0ad5d42a1be27e183fb76bdb2b'
    if not containers['service']['image'].endswith('@'+expected):raise RuntimeError('Unexpected control image')
    m=next(m for m in containers['worker-esmfold2']['volumeMounts'] if m['name']=='resident-config')
    if m.get('subPath')!='esmfold2.worker.json':raise RuntimeError('Configuration mount fix required')
    code=next(v for v in dep['spec']['template']['spec']['volumes'] if v['name']=='esmfold2-code')
    if code['configMap']['name']!='antigen-esmfold2-backend-code-r03':
        raise RuntimeError('Expected r03 worker source')
    structure_path='t01_phase1_real/development/structure/worker.py'
    if not any(m.get('name')=='esmfold2-code' and m.get('subPath')==structure_path
               and m.get('mountPath')=='/opt/t01/src/'+structure_path and m.get('readOnly') is True
               for m in containers['worker-structure']['volumeMounts']):
        raise RuntimeError('Expected r03 structure worker mount')
    if dep['status'].get('observedGeneration')!=dep['metadata']['generation'] or dep['status'].get('readyReplicas')!=1:
        raise RuntimeError('Deployment is not ready')
    OUT.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+2100
    while time.monotonic()<deadline:
        try:
            result=subprocess.run(kc+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-'],
                                  input=REMOTE.encode(),capture_output=True,timeout=180)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Connection wait expired; rerun this command to resume the same r03 task. Server computation may still be running.') from exc
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')+'\nRerun this command to resume the same task.')
        value=json.loads(result.stdout)
        (OUT/'latest.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(job_id=value['job']['job_id'],state=value['job']['state'],
              nodes={n:dict(state=r['state'],error=r.get('error_code') or r.get('reason_code')) for n,r in value['nodes'].items() if r['state']!='not_executed'})),flush=True)
        if value['terminal']:
            count=0
            for row in value['evidence']:
                folder=OUT/row['job']['job_id'];folder.mkdir(exist_ok=True)
                for item in row['artifacts']:
                    ref=item['ref'];raw=base64.b64decode(item['base64'],validate=True)
                    if len(raw)!=ref['size_bytes'] or hashlib.sha256(raw).hexdigest()!=ref['sha256']:
                        raise RuntimeError('Artifact integrity failure')
                    # Hash filenames avoid trusting remote paths and preserve every original byte.
                    (folder/ref['sha256']).write_bytes(raw);count+=1
            passed=value['job']['state']=='succeeded' and all(value['nodes'][n]['state']=='succeeded' for n in ('prediction','structure'))
            if any(row['job']['usable_for_pipeline'] for row in value['evidence']):raise RuntimeError('Science gate unexpectedly open')
            print('ARTIFACTS_VERIFIED',count,flush=True)
            print('ESMFOLD2_BACKEND_N01_PASS' if passed else 'ESMFOLD2_BACKEND_N01_NOT_PASSED',flush=True)
            print('SAVED',OUT)
            if not passed:raise SystemExit(1)
            return
        time.sleep(10)
    raise RuntimeError('Local wait limit reached; rerun to resume, do not create another task.')

if __name__=='__main__':main()
