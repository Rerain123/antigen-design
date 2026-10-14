"""Validate the assembled environments without running a scientific design workflow."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.resident_assembly import GROUPS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker',default='docker')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--groups',nargs='+',choices=list(GROUPS),default=list(GROUPS))
    args=parser.parse_args();out=args.output.absolute();out.mkdir(parents=True,exist_ok=True)
    originals=json.loads((ROOT/'discovery/t01-phase1-real/resident-worker-20260915/engineering-r01/image-environments.json').read_bytes())
    expected={r['tool']:r['environment'] for r in originals}
    checks=[]
    for group in args.groups:
        argv=[args.docker,'run','--rm','--network','none','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--user','10001:10001','--pids-limit','256','--memory','12g',
            '--tmpfs','/run/t01-slot:rw,noexec,nosuid,size=4m,uid=10001,gid=10001',
            '--tmpfs','/var/lib/t01/resident:rw,nosuid,size=512m,uid=10001,gid=10001',
            '--mount','type=bind,source='+str(ROOT/'tests')+',target=/tests,readonly',
            '--mount','type=bind,source='+str(ROOT/'var/t01-phase1-real/tool-assets')+',target=/t01/assets,readonly']
        if group=='gpu':argv+=['--gpus','device=0']
        argv+=['--entrypoint','/opt/t01/supervisor/bin/python3.11','antigen-design-resident-'+group+':assembly-r01',
               '-B','/tests/resident_environment_probe.py',group]
        print('checking',group,flush=True)
        done=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=500)
        (out/(group+'.stdout')).write_bytes(done.stdout);(out/(group+'.stderr')).write_bytes(done.stderr)
        row=dict(group=group,argv=argv,exit_code=done.returncode)
        checks.append(row)
        if done.returncode:
            print(done.stderr.decode(errors='replace')[-3500:],flush=True)
            continue
        value=json.loads(done.stdout)
        for result in value['results']:
            native=result['environment'];old=expected[native['tool']]
            assert native['python']==old['python'],native['tool']
            normalize=lambda s:s.lower().replace('_','-')
            packages={normalize(k):v for k,v in native['packages'].items()}
            changed={k:(v,packages.get(normalize(k))) for k,v in old['packages'].items() if packages.get(normalize(k))!=v}
            assert not changed,(native['tool'],changed)
        row['native_versions_match_source']=True
        print('passed',group,len(value['results']),'executions',flush=True)
    (out/'summary.json').write_text(json.dumps(dict(boundary='LOCAL_ENVIRONMENT_ASSEMBLY',checks=checks),indent=2))
    return int(any(row['exit_code'] for row in checks))


if __name__=='__main__':raise SystemExit(main())
