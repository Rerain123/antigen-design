"""Read-only current N14 progress and owned native CPU evidence."""
import datetime,json,subprocess
from pathlib import Path
import prepare_m1_p1_deploy as common
from version_bundle import encode
from run_pcv2_n14_continuation import REMOTE

OUT=common.ROOT/'reports/n14-performance-20260928'
WORKER=r'''
import json,sys,time,datetime,os
from pathlib import Path
target=Path(json.load(sys.stdin)['target']);native=target/'output/native'
def snapshot():
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   if (p/'comm').read_text().strip()!='foldx_20270131':continue
   cwd=(p/'cwd').resolve()
   if native!=cwd and native not in cwd.parents:continue
   stat=(p/'stat').read_text().rsplit(')',1)[1].split()
   rows.append(dict(pid=int(p.name),cwd=str(cwd),state=stat[0],cpu_ticks=int(stat[11])+int(stat[12])))
  except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 return rows
a=snapshot();time.sleep(2);b=snapshot();prior={r['pid']:r for r in a}
for r in b:r['cpu_seconds_in_sample']=(r['cpu_ticks']-prior[r['pid']]['cpu_ticks'])/os.sysconf('SC_CLK_TCK') if r['pid'] in prior else None
result=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),processes=b,sample_seconds=2,
 cpu_max=Path('/sys/fs/cgroup/cpu.max').read_text().strip(),cpu_stat=Path('/sys/fs/cgroup/cpu.stat').read_text(),
 memory_current=int(Path('/sys/fs/cgroup/memory.current').read_text()))
for name in ('buildmodel-plan.json','buildmodel-progress.json'):
 p=native/name
 if p.is_file():result[name]=json.loads(p.read_bytes())
result['native_detail']=[]
for folder in sorted((native/'buildmodel/batches').glob('[0-9][0-9][0-9][0-9]')):
 if not folder.is_dir():continue
 log=folder/'stdout.txt';err=folder/'stdout.stderr.txt'
 result['native_detail'].append(dict(candidate=int(folder.name),
  pdbs=[dict(name=f.name,mtime_utc=datetime.datetime.fromtimestamp(f.stat().st_mtime,datetime.timezone.utc).isoformat()) for f in sorted(folder.glob('*.pdb'))],
  stdout_tail=log.read_text(errors='replace').splitlines()[-18:] if log.is_file() else [],
  stderr_tail=err.read_text(errors='replace')[-1000:] if err.is_file() else ''))
print(json.dumps(result))
'''

if __name__=='__main__':
    receipt=json.loads((OUT/'continuation-submission.json').read_bytes());job=receipt['job_id']
    status=common.remote(REMOTE,dict(action='status',job_id=job,source=receipt['source_job_id']))
    (OUT/'continuation-status.json').write_bytes(encode(status))
    target=status.get('foldx',{}).get('resident_target');worker=None
    if target:
        done=subprocess.run(common.K+['exec','-i','deployment/antigen-design','-c','worker-foldx','--',
            '/opt/t01/supervisor/bin/python3.11','-B','-c',WORKER],input=encode(dict(target=target)),capture_output=True,timeout=30)
        if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-1500:])
        worker=json.loads(done.stdout)
    value=dict(parent=status['parent'],foldx=(status.get('foldx') or {}).get('job'),worker=worker)
    (OUT/'parallel-live.json').write_bytes(encode(value))
    summary=dict(value)
    if worker:
        summary['worker']={k:v for k,v in worker.items() if k!='buildmodel-plan.json'}
        planned=worker.get('buildmodel-plan.json') or {}
        summary['worker']['plan']={k:planned.get(k) for k in ('marker','workers','serial_equivalence','expert_signoff')}
    print(json.dumps(summary,ensure_ascii=False))
