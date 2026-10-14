"""Read the native MSA process counters; never change a process or model input."""
import json
import subprocess
from pathlib import Path
import run_expert_revision_v2_native as run
from version_bundle import encode

OUT=run.common.ROOT/'reports/expert-revision-v2-resume-20260930'
REMOTE=r'''
import json,os,time
from pathlib import Path
rows=[]
for root in Path('/proc').iterdir():
 if not root.name.isdigit():continue
 try:
  args=(root/'cmdline').read_bytes().decode().split('\0')
  if not args or Path(args[0]).name!='jackhmmer':continue
  db=Path(args[-2]);stat=(root/'stat').read_text().rsplit(')',1)[1].split()
  rss=next(line.split()[1] for line in (root/'status').read_text().splitlines() if line.startswith('VmRSS:'))
  positions=[]
  for fd in (root/'fd').iterdir():
   try:
    if Path(os.readlink(fd))!=db:continue
    positions.append(int(next(line.split()[1] for line in (root/'fdinfo'/fd.name).read_text().splitlines() if line.startswith('pos:'))))
   except (OSError,StopIteration):pass
  try:size=(root/'root'/str(db).lstrip('/')).stat().st_size
  except OSError:size=None
  rows.append(dict(pid=int(root.name),birth=stat[19],database=db.name,rss_kib=int(rss),
   cpu_seconds=(int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK'),
   database_bytes=size,reader_positions=positions,
   reader_fraction=max(positions)/size if positions and size else None))
 except (OSError,StopIteration,ValueError):pass
cgroup=Path('/sys/fs/cgroup');cpu=(cgroup/'cpu.stat').read_text() if (cgroup/'cpu.stat').exists() else None
print(json.dumps(dict(observed_epoch=time.time(),processes=rows,cgroup_cpu=cpu,
 reader_positions_are_not_completion_percent=True,read_only=True)))
'''

if __name__=='__main__':
    result=subprocess.run(run.common.K+['exec','-i','deployment/antigen-design','-c','worker-unified-gpu',
        '--','/opt/t01/supervisor/bin/python3.11','-B','-c',REMOTE],capture_output=True,timeout=30)
    if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace'))
    value=json.loads(result.stdout);path=OUT/'native-process-observation.json'
    if path.exists():
        prior=json.loads(path.read_bytes());elapsed=value['observed_epoch']-prior['observed_epoch']
        for row in value['processes']:
            previous=next((r for r in prior['processes'] if (r['pid'],r['birth'])==(row['pid'],row['birth'])),None)
            if previous and elapsed>0:row['observed_cpu_cores']=(row['cpu_seconds']-previous['cpu_seconds'])/elapsed
    path.write_bytes(encode(value)+b'\n')
    print(json.dumps(value))
