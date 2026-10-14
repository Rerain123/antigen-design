"""Exercise real resident child launches under old and corrected Docker mounts; no models."""
import json
from pathlib import Path
import subprocess
import prepare_m1_p1_deploy as common
from version_bundle import encode

OUT = common.ROOT/'reports/n02-slot-fix-20260928'
REMOTE = r'''
import json,os,sys
from pathlib import Path
from t01_phase1_real.resident_process import Command,prepare,run
root=Path('/var/lib/t01/slot-test');root.mkdir()
package=root/'native';package.mkdir();(package/'marker').write_text('original')
slot=Path('/run/t01-slot')
before=dict(app=os.readlink('/app'),package_is_dir=(slot/'package').is_dir(),package_is_link=(slot/'package').is_symlink())
code="from pathlib import Path; assert Path('/app/marker').read_text()=='original'; Path('{output}/ok').write_text('executed')"
cmd=Command('layout-probe',(sys.executable,'-B','-c',code),tuple(sorted(dict(T01_RESIDENT_SLOT=str(slot),T01_PRIVATE_TMP='1',T01_NATIVE_PACKAGE=str(package),T01_NATIVE_CWD='/app').items())))
rows=[]
for index in range(2 if sys.argv[1]=='fixed' else 1):
 target=prepare(root/'spool',str(index+1)*32,dict(job_id='layout-probe',attempt_id=str(index),execution_identity=str(index)),cmd,{'input.json':b'{}'},10)
 result=run(target,cmd)
 rows.append(dict(state=result['state'],stopped=result['stopped_confirmed'],executed=(target/'output/ok').exists(),stderr=(target/'output/stderr.txt').read_text()))
assert (package/'marker').read_text()=='original'
if sys.argv[1]=='fixed':
 assert all(r['state']=='succeeded' and r['executed'] and r['stopped'] for r in rows),rows
 assert (slot/'package').is_symlink()
else:
 assert rows[0]['state']=='failed' and 'IsADirectoryError' in rows[0]['stderr'] and not rows[0]['executed'],rows
print(json.dumps(dict(mode=sys.argv[1],before=before,executions=rows,scientific_models_executed=False)))
'''


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    rows=[]
    for mode in ('legacy','fixed'):
        command=['docker','run','--rm','-i','--network','none','--user','10001:10001',
            '-e','T01_PROCESS_REGISTRY=/var/lib/t01/process-control',
            '--tmpfs','/run/t01-slot:rw,uid=10001,gid=10001',
            '--tmpfs','/var/lib/t01:rw,uid=10001,gid=10001',
            '--mount',f'type=bind,src={common.ROOT}/src,dst=/opt/t01/src,readonly']
        if mode=='legacy':
            command+=['--mount',f'type=bind,src={common.ROOT}/src/t01_phase1_real,dst=/app/src/t01_phase1_real,readonly']
        command+=['--entrypoint','/opt/t01/supervisor/bin/python3.11',
                  'antigen-design-resident-deeptmhmm:thread-fix-r01','-B','-c',REMOTE,mode]
        done=subprocess.run(command,capture_output=True,timeout=90)
        if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-4000:])
        rows.append(json.loads(done.stdout))
    (OUT/'linux-slot-probe.json').write_bytes(encode(dict(status='PASS',checks=rows)))
    print(json.dumps(rows))


if __name__=='__main__':main()
