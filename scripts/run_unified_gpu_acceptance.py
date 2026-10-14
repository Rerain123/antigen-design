"""Run one resumable ESMFold2 request through the unified resident GPU Worker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'discovery/t01-phase1-real/unified-gpu-worker-20260920/r03'
REMOTE = r'''
import json,time
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import TERMINAL, encode
from t01_phase1_real.development import Runtime

scope='unified-gpu-esmfold2-acceptance-r03'
rt=Runtime(Path('/var/lib/t01/runtime'),scope=scope)
body=dict(
  protein_sequence='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG',
  user_sequence_id='unified-gpu-esmfold2-ubiquitin-r03', host_species='Homo sapiens',
  expression_host=None, organism=None, structure=None, reuse_jobs={}, timeout_seconds=1800,
  analysis={name:None for name in ('topology','blast','bepipred','netmhc','homology','domains','developability')},
  prediction=dict(engine='esmfold2', seed=1, timeout_seconds=600))
j=rt.submit_workflow(encode(body),scope)
j=rt.dispatch(j['job_id'])
deadline=time.monotonic()+1500
while time.monotonic()<deadline:
  j=rt.get(j['job_id'])
  if j['state'] in TERMINAL: break
  time.sleep(5)
view=rt.workflow(j['job_id'])
execution=rt.execution(j['job_id'])
nodes={name:{'state':row.get('state'),'job_id':row.get('job_id'),'error':row.get('error_code') or row.get('reason_code')} for name,row in view['nodes'].items()}
print(json.dumps({'job':{'job_id':j['job_id'],'state':j['state'],'usable_for_pipeline':j['usable_for_pipeline']},'nodes':nodes,'execution':execution},sort_keys=True))
'''


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    compile(REMOTE,'unified-gpu-acceptance-remote','exec')
    if args.check:
        print('PAYLOAD_SYNTAX_OK_NO_CLUSTER_ACTION'); return
    kube=['kubectl','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),'-n','him-ws']
    result=subprocess.run(kube+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-'],
                          input=REMOTE.encode(),capture_output=True,timeout=1800)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    lines=[line for line in result.stdout.decode(errors='replace').splitlines() if line.strip()]
    value=json.loads(lines[-1])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'latest.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'job_id':value['job']['job_id'],'state':value['job']['state'],
                      'nodes':value['nodes'],'saved':str(OUT)},ensure_ascii=False))
    if value['job']['state'] != 'succeeded': raise SystemExit(1)


if __name__=='__main__': main()
