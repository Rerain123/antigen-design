"""Read bounded logs only inside one registered live resident execution."""
import json
import sys
import run_m1_p2_probe as p

name=sys.argv[1]
task=p.context();task['job_id']=p.local(name)['job']['job_id']
code=r'''
j=rt.get(task['job_id']);ex=rt.execution(j['job_id']);root=Path(ex['resident_target'])
assert root.is_relative_to(Path('/var/lib/t01/resident'))
logs={}
for rel in ('output/stdout.txt','output/stderr.txt','execution.json','output/native/repair.stdout.txt'):
    path=root/rel
    if path.is_file():logs[rel]=path.read_bytes()[-1500:].decode(errors='replace')
models=[dict(path=f.relative_to(root).as_posix(),bytes=f.stat().st_size,mtime=f.stat().st_mtime) for f in root.rglob('*.pdb')
        if '/buildmodel/' in f.as_posix()]
print(json.dumps(dict(job_id=j['job_id'],state=j['state'],started_at=j['started_at'],logs=logs,buildmodel_files=models)))
'''
result=p.deploy.remote(p.PREAMBLE+code,task)
p.save(name+'-progress.json',result)
print(json.dumps(dict(job_id=result['job_id'],state=result['state'],
    model_files=[r['path'].rsplit('/',1)[-1] for r in result['buildmodel_files']
                 if not r['path'].rsplit('/',1)[-1].startswith('WT_')],
    model_files_are_not_final_scores=True),indent=2))
