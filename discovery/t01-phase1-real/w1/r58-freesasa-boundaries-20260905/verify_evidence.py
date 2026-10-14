"""Read-only evidence checks using archived code, keeping historical and current code distinct."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def require(value,message):
    if not value:raise ValueError(message)


def verify_files(base,rows):
    base=base.resolve();seen=set()
    for row in rows:
        path=(base/row['path']).resolve()
        require(path.is_relative_to(base) and path!=base and path not in seen,'Unsafe or duplicate manifest path')
        seen.add(path);data=path.read_bytes()
        require(len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],'Evidence hash mismatch: '+row['path'])


def load(name,path,package=False):
    spec=importlib.util.spec_from_file_location(name,path,submodule_search_locations=[str(path.parent)] if package else None)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def verify():
    manifest=read(BATCH/'manifest.json');verify_files(BATCH,manifest['files'])
    actual={p.relative_to(BATCH).as_posix() for p in BATCH.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='manifest.json'}
    require(actual=={r['path'] for r in manifest['files']},'Batch inventory drift')
    before=read(BATCH/'before.json')
    for path,digest in before['experts'].items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,'Expert source changed: '+path)
    execution=read(BATCH/'raw-run/execution.json')
    for path,digest in execution['source_hashes'].items():
        snapshot=BATCH/'after'/path.replace('\\','/')
        require(hashlib.sha256(snapshot.read_bytes()).hexdigest()==digest,'Archived execution source differs: '+path)
    for row in before['files']:
        require(hashlib.sha256((BATCH/row['snapshot']).read_bytes()).hexdigest()==row['sha256'],'Pre-change source snapshot differs')
    old_batch=ROOT/'discovery/t01-phase1-real/w1/r58-local-20260905'
    old=read(old_batch/'campaign_result.json')
    for row in old['evidence_files']:
        require(hashlib.sha256((old_batch/row['path']).read_bytes()).hexdigest()==row['sha256'],'Initial R58 output changed')
    package=BATCH/'after/src/t01_structure_mapping'
    load('t01_r58_boundary_archive',package/'__init__.py',package=True)
    probe=load('t01_r58_boundary_archive.probe',package/'probe.py')
    sasa=load('t01_r58_boundary_archive.sasa_probe',package/'sasa_probe.py')
    assessment=load('r58_boundary_assessment',BATCH/'assess.py')
    for name in ['parse_local','propose','read_sequence']:setattr(assessment,name,getattr(probe,name))
    assessment.align_absolute_sasa=sasa.align_absolute_sasa
    require(assessment.assess()==read(BATCH/'assessment.json'),'Saved assessment differs from archived-code recheck')
    return {'status':'PASS','batch_files':len(manifest['files']),'expert_sources_unchanged':len(before['experts']),
            'prior_r58_evidence_files_unchanged':len(old['evidence_files']),
            'raw_calculations':6,'scientific_acceptance':'NOT_RUN','production_status':'NOT_DEPLOYED'}


if __name__=='__main__':print(json.dumps(verify()))
