"""Build all local resident environments from verified source images, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real import resident_assembly as assembly


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker',default='docker')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--groups',nargs='+',choices=list(assembly.GROUPS),default=list(assembly.GROUPS))
    args=parser.parse_args()
    out=args.output.absolute();out.mkdir(parents=True,exist_ok=True)
    def call(argv):
        result=subprocess.run([args.docker]+argv,capture_output=True)
        if result.returncode: raise RuntimeError(result.stderr.decode(errors='replace')[-3000:])
        return result.stdout
    verified={}
    for name,(tag,digest) in dict(assembly.SOURCES,supervisor=assembly.SUPERVISOR).items():
        value=json.loads(call(['image','inspect',tag]))[0]
        if value['Id']!='sha256:'+digest or value['Architecture']!='amd64': raise ValueError('Source image changed: '+name)
        verified[name]=dict(tag=tag,image_id=value['Id'])
    context=out/'context';context.mkdir(exist_ok=True)
    for folder in ('t01_phase1_real','t01_structure_mapping'):
        shutil.copytree(ROOT/'src'/folder,context/'src'/folder,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copyfile(ROOT/'docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json',context/'profile.json')
    (context/'setup.py').write_text('import sys\nfrom t01_phase1_real.resident_assembly import setup\nsetup(sys.argv[1])\n')
    (out/'controller.json').write_text(json.dumps(assembly.configuration(),indent=2),encoding='utf-8')
    built={}
    for group in args.groups:
        tag='antigen-design-resident-'+group+':assembly-r01'
        (context/(group+'.Dockerfile')).write_text(assembly.dockerfile(group))
        worker=dict(version='0.1.0',commands=[assembly.command(tool).document() for tool in assembly.GROUPS[group]])
        (context/(group+'.worker.json')).write_text(json.dumps(worker,indent=2))
        print('building',group,flush=True)
        with (out/(group+'.build.log')).open('wb') as log:
            result=subprocess.run([args.docker,'build','--network','none','--pull=false','-f',str(context/(group+'.Dockerfile')),
                '-t',tag,str(context)],stdout=log,stderr=subprocess.STDOUT)
        if result.returncode: raise RuntimeError(group+' build failed; see '+str(out/(group+'.build.log')))
        inspected=json.loads(call(['image','inspect',tag]))[0]
        built[group]=dict(tag=tag,image_id=inspected['Id'],tools=list(assembly.GROUPS[group]))
        (out/'images.json').write_text(json.dumps(dict(sources=verified,built=built),indent=2))
        print('built',group,inspected['Id'],flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
