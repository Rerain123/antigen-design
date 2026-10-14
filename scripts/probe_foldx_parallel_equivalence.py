"""Offline nine-residue native engineering probe; no PCV2 job or candidate generation."""
import json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_foldx_development import recording
from t01_phase1_real.development.foldx import policy
from t01_phase1_real.common import encode,sha

CODE=r'''
import concurrent.futures,json,subprocess,time,hashlib
from pathlib import Path
root=Path('/probe');lines=(root/'individual_list.txt').read_text().splitlines()
def run(label,indices,extra=()):
 d=root/label;d.mkdir();(d/'individual_list.txt').write_text('\n'.join(lines[i] for i in indices)+'\n')
 argv=['/app/foldx_20270131','--command=BuildModel','--pdb=target_Repair.pdb','--pdb-dir=/probe',
       '--mutant-file=individual_list.txt','--numberOfRuns=5','--output-dir='+str(d),*extra]
 t=time.monotonic()
 with (d/'stdout.txt').open('wb') as out,(d/'stderr.txt').open('wb') as err:
  p=subprocess.run(argv,cwd=d,stdout=out,stderr=err,timeout=180)
 assert p.returncode==0,(label,p.returncode)
 return dict(label=label,indices=indices,seconds=time.monotonic()-t)
t=time.monotonic();serial=run('serial',list(range(len(lines))));serial_seconds=time.monotonic()-t
repeat=run('serial-repeat',list(range(len(lines))))
quiet=run('serial-quiet',list(range(len(lines))),['--screen=false'])
t=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 parallel=list(pool.map(lambda i:run('parallel-'+str(i),[i]),range(len(lines))))
parallel_seconds=time.monotonic()-t
def table(path):
 header=None;rows=[]
 for line in path.read_text().splitlines():
  if line.startswith('Pdb\t'):header=line.split('\t')
  elif header and line.strip():rows.append(dict(zip(header,line.split('\t'))))
 return rows
differences=[]
for filename in ('Dif_target_Repair.fxout','Average_target_Repair.fxout','Raw_target_Repair.fxout'):
 full=table(root/'serial'/filename);offset=0
 for i in range(len(lines)):
  piece=table(root/('parallel-'+str(i))/filename)
  expected=full[offset:offset+len(piece)];offset+=len(piece)
  for a,b in zip(expected,piece):
   for k in a:
    if k!='Pdb' and a[k]!=b.get(k):differences.append(dict(file=filename,candidate=i,column=k,serial=a[k],parallel=b.get(k)))
 assert offset==len(full)
pdb_differences=[]
for i in range(len(lines)):
 for r in range(5):
  for prefix in ('','WT_'):
   a=(root/'serial'/f'{prefix}target_Repair_{i+1}_{r}.pdb').read_bytes()
   b=(root/('parallel-'+str(i))/f'{prefix}target_Repair_1_{r}.pdb').read_bytes()
   if a!=b:pdb_differences.append(dict(candidate=i,run=r,prefix=prefix))
value=dict(status='PASS' if not differences and not pdb_differences else 'DIFFERENT',serial=serial,parallel=parallel,
 serial_seconds=serial_seconds,parallel_seconds=parallel_seconds,numeric_differences=differences,pdb_differences=pdb_differences,
 scope='9-aa engineering fixture; no PCV2 scientific conclusion')
for record in (repeat,quiet):
 label=record['label'];changes=[]
 for filename in ('Dif_target_Repair.fxout','Average_target_Repair.fxout','Raw_target_Repair.fxout'):
  if table(root/'serial'/filename)!=table(root/label/filename):changes.append(filename)
 for path in (root/'serial').glob('*.pdb'):
  if path.read_bytes()!=(root/label/path.name).read_bytes():changes.append(path.name)
 value[label]=dict(record,identical=not changes,different_files=changes)
(root/'comparison.json').write_text(json.dumps(value,indent=2));print(json.dumps(value))
'''

if __name__=='__main__':
    out=ROOT/'reports/n14-performance-20260928'/('parallel-native-probe-'+(sys.argv[1] if len(sys.argv)>1 else 'r02'))
    out.mkdir(parents=True,exist_ok=False)
    _,_,files,_=recording('buildmodel-three-variants-five-runs')
    (out/'target_Repair.pdb').write_bytes(files['output/repair/target_Repair.pdb'])
    (out/'individual_list.txt').write_bytes(files['output/buildmodel/individual_list.txt'])
    (out/'probe.py').write_text(CODE,encoding='utf8')
    cmd=['docker','run','--rm','--network','none','--cpus','2','--memory','4g','--pids-limit','128',
        '--mount',f'type=bind,source={out},target=/probe',
        '--mount',f'type=bind,source={policy.PACKAGE},target=/app,readonly',
        '--entrypoint','python',policy.IMAGE,'-B','/probe/probe.py']
    done=subprocess.run(cmd,capture_output=True,timeout=600)
    (out/'launch.json').write_bytes(encode(dict(argv=cmd,exit_code=done.returncode)))
    (out/'stdout.txt').write_bytes(done.stdout);(out/'stderr.txt').write_bytes(done.stderr)
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-1800:])
    value=json.loads((out/'comparison.json').read_bytes())
    print(json.dumps({k:v for k,v in value.items() if k not in ('numeric_differences','pdb_differences')}))
