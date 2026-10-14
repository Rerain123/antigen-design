"""Exercise every registered interpreter twice under one resident supervisor."""
import dataclasses
import json
import os
from pathlib import Path
import sys

from t01_phase1_real.resident_assembly import GROUPS, command
from t01_phase1_real.resident_process import prepare, run

group=sys.argv[1]
root=Path('/var/lib/t01/resident')/group
os.environ['T01_PROCESS_REGISTRY']=str(root/'.processes')
results=[]
for repeat in range(2):
    for index,tool in enumerate(GROUPS[group]):
        original=command(tool)
        env=dict(original.environment)
        env.pop('T01_DATABASE_ROOT',None)  # Database selection belongs to workflow tests.
        env['T01_PROBE_NATIVE_ENTRY']=original.argv[-1]
        probe=dataclasses.replace(original,tool=tool+'-environment',
            argv=(original.argv[0],'-B','/tests/resident_science_environment.py',tool),environment=tuple(sorted(env.items())))
        eid=('%032x'%(repeat*16+index+1))
        target=prepare(root,eid,dict(job_id='environment-'+tool,attempt_id=eid,execution_identity=eid),probe,
                       {'input.json':b'{}','native/runtime-local.yaml':b'environment-probe-only\n'},180)
        receipt=run(target,probe)
        if receipt['state']!='succeeded':
            raise AssertionError(dict(tool=tool,receipt=receipt,stderr=(target/'output/stderr.txt').read_text()))
        observed=json.loads((target/'output/native/environment.json').read_bytes())
        results.append(dict(receipt=receipt,environment=observed))
print(json.dumps(dict(status='PASS',boundary='ENVIRONMENT_ASSEMBLY_NOT_FULL_SCIENTIFIC_WORKFLOW',
                      group=group,supervisor_pid=os.getpid(),results=results)))
