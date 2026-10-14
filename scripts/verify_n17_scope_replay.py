"""Read-only archived WT inputs -> current scan requests. Never submits a scan."""
import argparse
import json
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import encode,sha

OUT=common.ROOT/'reports/n17-scope-20260927'
REMOTE=r'''
import json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import encode,sha
from t01_phase1_real.development.workflow import m1,policy,service
from t01_phase1_real.development.foldx import policy as foldx
from t01_phase1_real.development.thermompnn import policy as thermo
p=json.load(sys.stdin)
class ArchivedInputs:
    def __init__(self):
        self.records=p['records'];self.jobs={r['job']['job_id']:r for r in self.records.values()}
        self.rows={n:dict(state='succeeded',job_id=r['job']['job_id']) for n,r in self.records.items()}
    def get(self,jid):return self.jobs[jid]['job']
    def result(self,jid):return self.jobs[jid]['result']
rt=ArchivedInputs();body=policy.request(encode(p['body']))
fact,reason=m1.scan_scope(rt,body,rt.rows)
assert reason is None and len(fact['positions'])>1
requests={}
for name,parser in [('wt_foldx',foldx.request),('wt_thermompnn',thermo.request)]:
    request,reason=m1.request_for(rt,body,rt.rows,name)
    assert reason is None and parser(encode(request))==request and request['scan_positions']==fact['positions']
    requests[name]=request
print(json.dumps(dict(status='PASS',mode='ARCHIVED_INPUT_SCOPE_REPLAY_NOT_NEW_SCAN',
    scope=fact,requests=requests,source_files=p['source_files'],submitted=False,model_invocations=0,
    scientific_gate='CLOSED',usable_for_pipeline=False)))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--online',action='store_true');args=parser.parse_args()
    root=common.ROOT/'discovery/t01-phase1-real/m1-p1-20260921/r01'
    paths=[root/'batch.json',root/'structure.json',root/'topology.json']
    docs=[json.loads(p.read_bytes()) for p in paths]
    payload=dict(body=docs[0]['request'],records=dict(structure=docs[1],topology=docs[2]),
        source_files={p.relative_to(common.ROOT).as_posix():sha(p.read_bytes()) for p in paths})
    if args.online:value=common.remote(REMOTE,payload)
    else:
        import subprocess,sys
        code=REMOTE.replace('from t01_phase1_real.linux_service import install_platform_modules\ninstall_platform_modules()',
                            "sys.path.insert(0,'src')")
        result=subprocess.run([sys.executable,'-X','utf8','-B','-c',code],input=encode(payload),capture_output=True,check=True)
        value=json.loads(result.stdout)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/('online-scope-replay.json' if args.online else 'local-scope-replay.json')).write_bytes(encode(value)+b'\n')
    print(json.dumps(dict(status=value['status'],positions=len(value['scope']['positions']),
        excluded=value['scope']['excluded'],foldx_budget=value['requests']['wt_foldx']['timeout_seconds'],
        submitted=False,model_invocations=0)))


if __name__=='__main__':main()
