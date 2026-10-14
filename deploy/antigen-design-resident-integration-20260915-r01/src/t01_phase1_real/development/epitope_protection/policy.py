from pathlib import Path
from ...common import decode,encode,ensure,sha,REPO
from ..variant_report.policy import request as report_request
from ..foldx.policy import artifact

TOOL='t01.real.epitope_protection'
NODE='N13'
HERE=Path(__file__).parent
PRODUCERS={'base_report':'t01.real.variant_report'}
SIDE_PRODUCERS={'structure':'t01.real.ingest_structure','epitope_map':'t01.real.epitope_map','domains':'t01.real.domains'}
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
AUTHORITY=[AUTHORITY_ROOT/n for n in ('AgentA_SOP_v10.5_20260902.md','AgentA_SKILL_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md')]

def source(src):
    if src is None:return
    ensure(isinstance(src,dict) and set(src)=={'job_id','artifact'} and isinstance(src['job_id'],str),'INVALID_REQUEST','Exact registered source required')
    ref=src['artifact']
    if ref is not None:
        ensure(isinstance(ref,dict) and ref.get('job_id')==src['job_id'] and ref.get('role') in ('result','diagnostic'),'INVALID_REQUEST','Source artifact identity differs')
        ref=dict(ref);ref['role']='result';artifact(ref)

def request(raw):
    b=decode(raw)
    ensure(isinstance(b,dict) and set(b)=={'protein_sequence','user_sequence_id','upstream','pairs','timeout_seconds'},'INVALID_REQUEST','Exact N13 request required')
    report_request(encode(dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],
        upstream=dict(design_audit=None,foldx=None),variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=b['timeout_seconds'])))
    ensure(isinstance(b['upstream'],dict) and set(b['upstream'])=={'base_report'} and b['upstream']['base_report'] is not None,'INVALID_REQUEST','Registered base variant report required')
    source(b['upstream']['base_report'])
    ensure(isinstance(b['pairs'],list) and len(b['pairs'])<=500,'INVALID_REQUEST','Bounded variant pairs required')
    ids=[]
    for pair in b['pairs']:
        ensure(isinstance(pair,dict) and set(pair)=={'variant_id','wt','variant'} and isinstance(pair['variant_id'],str),'INVALID_REQUEST','Exact pair identity required')
        ids.append(pair['variant_id'])
        for side in ('wt','variant'):
            ensure(isinstance(pair[side],dict) and set(pair[side])==set(SIDE_PRODUCERS),'INVALID_REQUEST','All side sources explicit')
            for src in pair[side].values():source(src)
    ensure(len(ids)==len(set(ids)),'INVALID_REQUEST','Duplicate paired variant')
    return b

def sequence_id(seq):return 't01n13_'+sha(seq.encode())[:16]

def registered_rules():
    return dict(id='w6-n13-r56-engineering',version='0.1.0',sha256=sha(encode(dict(
        authority={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        code={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},scientific_release=False))))

def registered_profile():
    paths=list(HERE.glob('*.py'))
    for package in ('variant_report','design_backend','structure','epitope_map'):
        paths.extend((HERE.parent/package).glob('*.py'))
    paths.extend(HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py'))
    return dict(id='w6-n13-local-paired-observation',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),network=False))))
