from pathlib import Path
from ...common import decode,encode,ensure,sha,REPO
from ..epitope_protection.policy import source,AUTHORITY
TOOL='t01.real.wt_reference'
NODE='N17'
HERE=Path(__file__).parent
PRODUCERS=dict(structure='t01.real.ingest_structure',foldx='t01.real.foldx',thermompnn='t01.real.thermompnn',design_audit='t01.real.design_audit',topology='t01.real.deeptmhmm')

def base(b,fields):
    ensure(isinstance(b,dict) and set(b)==fields,'INVALID_REQUEST','Exact engineering assembly request required')
    ensure(isinstance(b['protein_sequence'],str) and 1<=len(b['protein_sequence'])<=20000 and set(b['protein_sequence'])<=set('ACDEFGHIKLMNPQRSTVWY'),'INVALID_REQUEST','Exact AA20 protein required')
    ensure(isinstance(b['user_sequence_id'],str) and 0<len(b['user_sequence_id'])<=128,'INVALID_REQUEST','Explicit engineering label required')
    ensure(type(b['timeout_seconds']) is int and 1<=b['timeout_seconds']<=60,'INVALID_REQUEST','Deadline must be 1..60 seconds')

def request(raw):
    b=decode(raw);base(b,{'protein_sequence','user_sequence_id','upstream','timeout_seconds'})
    ensure(isinstance(b['upstream'],dict) and set(b['upstream'])==set(PRODUCERS),'INVALID_REQUEST','All N17 slots required')
    for s in b['upstream'].values():source(s)
    return b

def sequence_id(s):return 't01ref_'+sha(s.encode())[:16]
def registered_rules():return dict(id='w7-n17-historical-reference',version='0.1.0',sha256=sha(encode({p.name:sha(p.read_bytes()) for p in AUTHORITY})))
def registered_profile():
    paths=list(HERE.glob('*.py'))+[HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')]
    for package in ('foldx','thermompnn','design_backend','proteinmpnn'):paths.extend((HERE.parent/package).glob('*.py'))
    return dict(id='w7-n17-local-reference',version='0.1.0',sha256=sha(encode({p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths})))
