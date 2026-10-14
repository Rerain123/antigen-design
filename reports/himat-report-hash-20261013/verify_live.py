"""Read deployed identity or verify the existing HiMat report; never submit science."""
import json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_m1_p1_deploy as common
import verify_scientific_report as report
OUT=Path(__file__).parent

def deployment():
    values=json.loads(subprocess.check_output(common.K+['get','deployments','-o','json']))['items']
    pods=json.loads(subprocess.check_output(common.K+['get','pods','-o','json']))['items']
    deps=[dict(name=d['metadata']['name'],generation=d['metadata']['generation'],ready=d.get('status',{}).get('readyReplicas',0))
          for d in values if d['metadata']['name'].startswith('antigen-design')]
    service=[dict(name=p['metadata']['name'],created=p['metadata']['creationTimestamp'],
                  containers=[{k:s.get(k) for k in ('name','imageID','ready','restartCount')} for s in p.get('status',{}).get('containerStatuses',[])])
             for p in pods if any(c['name']=='service' for c in p['spec']['containers']) and p['metadata']['name'].startswith('antigen-design-')]
    value=dict(deployments=deps,api_pods=service)
    (OUT/'live-deployment.json').write_text(json.dumps(value,indent=2),encoding='utf8')
    print(json.dumps(value))

def start():
    before=common.remote('''import sqlite3,json,hashlib
with sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True) as db:
 def h(t):return hashlib.sha256(json.dumps(db.execute('SELECT data FROM '+t+' ORDER BY data').fetchall(),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
 print(json.dumps(dict(job_count=db.execute('SELECT count(*) FROM jobs').fetchone()[0],jobs_sha256=h('jobs'),executions_sha256=h('executions'))))''')
    (OUT/'previous-task-before.json').write_text(json.dumps(before),encoding='utf8')
    report.start()

report.OUT=OUT
report.REMOTE_DIR='/var/lib/t01/historical-report-profile-20261013-r01'
if __name__=='__main__':
    dict(deployment=deployment,start=start,check=report.check)[sys.argv[1]]()
