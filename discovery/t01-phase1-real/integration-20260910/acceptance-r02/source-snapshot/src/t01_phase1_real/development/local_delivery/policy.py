from pathlib import Path
from ...common import decode,encode,ensure,sha,REPO
from ..wt_reference.policy import base,source,AUTHORITY
TOOL='t01.real.local_delivery'
NODE='N18'
HERE=Path(__file__).parent
PRODUCERS=dict(wt_draft='t01.real.wt_draft',variant_report='t01.real.variant_report',wt_reference='t01.real.wt_reference')

def request(raw):
    b=decode(raw);base(b,{'protein_sequence','user_sequence_id','host_species','expression_host','upstream','dna_bindings','timeout_seconds'})
    for field in ('host_species','expression_host'):
        ensure(b[field] is None or isinstance(b[field],str) and 0<len(b[field])<=128,'INVALID_REQUEST','Explicit host or null required')
    ensure(isinstance(b['upstream'],dict) and set(b['upstream'])==set(PRODUCERS),'INVALID_REQUEST','All N18 slots required')
    for s in b['upstream'].values():source(s)
    ensure(isinstance(b['dna_bindings'],list) and len(b['dna_bindings'])<=500,'INVALID_REQUEST','Bounded DNA bindings required')
    ids=[]
    for item in b['dna_bindings']:
        ensure(isinstance(item,dict) and set(item)=={'subject','source'} and isinstance(item['subject'],str) and item['source'] is not None,
            'INVALID_REQUEST','DNA requires an explicit WT or report variant identity')
        source(item['source']);ids.append(item['subject'])
    ensure(len(ids)==len(set(ids)),'INVALID_REQUEST','Duplicate DNA subject')
    return b

def sequence_id(s):return 't01delivery_'+sha(s.encode())[:16]
def registered_rules():return dict(id='w7-n18-local-assembly',version='0.1.0',sha256=sha(encode({p.name:sha(p.read_bytes()) for p in AUTHORITY})))
def registered_profile():
    paths=list(HERE.glob('*.py'))+[HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')]
    for package in ('wt_reference','wt_draft','variant_report','epitope_protection','codon'):paths.extend((HERE.parent/package).glob('*.py'))
    return dict(id='w7-n18-local-package',version='0.1.0',sha256=sha(encode({p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths})))
