"""Operator maintenance access while the HiMat controller is scaled to zero."""
import json
import subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import encode

EV=common.ROOT/'reports/controller-latency-20261010'
JID='t01p1r-job-45aea7ed7de143d08dbf0dea6597eefb'
BOOT='''import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import encode,decode,sha,TERMINAL,now
from t01_phase1_real.service_api.app import Principal
p=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset({'query','control'}),'x').runtime_scope,
 blast_database_root='/var/lib/t01/m1-p1-test-data/blast',
 domains_database_root='/var/lib/t01/databases/domains')
jid=p['jid']
'''


def remote(code,payload=None,timeout=110,pod='antigen-controller-maintenance-20261010'):
    boot="import json,sys;p=json.load(sys.stdin);exec(compile(p.pop('code'),'maintenance','exec'))"
    args=common.K+['exec','-i',pod,'-c','maintenance',
                  '--','python','-B','-c',boot]
    source=BOOT.replace('p=json.load(sys.stdin)','')+code
    done=subprocess.run(args,input=encode(dict(payload or {},jid=JID,code=source)),capture_output=True,timeout=timeout)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-3000:])
    return json.loads(done.stdout)


def status():
    return remote('''
with rt._db() as db:
 jobs=[json.loads(r[0]) for r in db.execute('SELECT data FROM jobs')]
active=[dict(job_id=j['job_id'],tool=j['tool_id'],state=j['state'],run_id=j['run_id']) for j in jobs if j['state'] not in TERMINAL]
e=rt.execution(jid)
print(json.dumps(dict(time=now(),active=active,dispatcher=e.get('dispatcher'),nodes=len(e['nodes']),
                     gpu=json.loads(Path('/var/lib/t01/resident/unified-gpu/state.json').read_bytes()))))
''')


if __name__=='__main__':print(json.dumps(status()))
