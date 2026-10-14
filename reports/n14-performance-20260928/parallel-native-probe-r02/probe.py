
import concurrent.futures,json,subprocess,time,hashlib
from pathlib import Path
root=Path('/probe');lines=(root/'individual_list.txt').read_text().splitlines()
def run(label,indices):
 d=root/label;d.mkdir();(d/'individual_list.txt').write_text('\n'.join(lines[i] for i in indices)+'\n')
 argv=['/app/foldx_20270131','--command=BuildModel','--pdb=target_Repair.pdb','--pdb-dir=/probe',
       '--mutant-file=individual_list.txt','--numberOfRuns=5','--output-dir='+str(d)]
 t=time.monotonic()
 with (d/'stdout.txt').open('wb') as out,(d/'stderr.txt').open('wb') as err:
  p=subprocess.run(argv,cwd=d,stdout=out,stderr=err,timeout=180)
 assert p.returncode==0,(label,p.returncode)
 return dict(label=label,indices=indices,seconds=time.monotonic()-t)
t=time.monotonic();serial=run('serial',list(range(len(lines))));serial_seconds=time.monotonic()-t
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
(root/'comparison.json').write_text(json.dumps(value,indent=2));print(json.dumps(value))
