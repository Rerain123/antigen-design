"""Run the existing W1 tool campaigns serially after W2 runtime changes."""
import json
from pathlib import Path
import subprocess
import sys

BASE=Path(__file__).parent;REPO=BASE.parents[3]
cases=[('structure','run_structure_acceptance.py'),('deeptmhmm','run_deeptmhmm_acceptance.py')]
entries=[]
for name,script in cases:
    # These are W1 tool regressions of the W2 change, linked from the W2 delivery.
    batch=REPO/'discovery/t01-phase1-real/w1/bepipred-shared-regression-20260906'/name
    root=REPO/'var/t01-phase1-real'/('bepipred-'+name+'-regression')
    args=[sys.executable,'-X','utf8',str(REPO/'scripts'/script),'--root',str(root),'--batch',str(batch)]
    assert not batch.exists() and not root.exists()
    result=subprocess.run(args,capture_output=True)
    with (BASE/(name+'-regression.stdout')).open('xb') as out:out.write(result.stdout)
    with (BASE/(name+'-regression.stderr')).open('xb') as out:out.write(result.stderr)
    entry=dict(name=name,argv=args,exit_code=result.returncode,index=str(batch/'index.json'))
    entries.append(entry)
    (BASE/'shared-regressions.json').write_text(json.dumps(entries,indent=2),encoding='utf-8')
    print(json.dumps(entry),flush=True)
    assert result.returncode==0,result.stderr.decode(errors='replace')
