"""Engineering-only WT envelope, separate from CandidateRecord/AgentCHandoff."""
from pathlib import Path
import re
import sys

from ...common import REPO, decode, encode, ensure, sha, profile as base_profile
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL='t01.real.wt_draft'
NODE='N18'
HERE=Path(__file__).parent
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
AUTHORITY=[AUTHORITY_ROOT/name for name in (
    'AgentA_SOP_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md',
    'AgentA_SKILL_v10.5_20260902.md')]
# N01 local structure and N02 topology are distinct registered producers.
PRODUCERS=dict(structure='t01.real.ingest_structure',topology='t01.real.deeptmhmm',
    blast='t01.real.blast',bepipred='t01.real.bepipred',netmhc='t01.real.netmhc',
    epitope_map='t01.real.epitope_map',glycosylation='t01.real.glycosylation',
    homology='t01.real.homology',domains='t01.real.domains',developability='t01.real.developability')
DESIGN_CONTEXT_FIELDS={'pathogen_type','membrane_design_confirm','low_conf_design_confirm'}
PATHOGEN_TYPES={'virus_enveloped','virus_non_enveloped','bacteria'}


def design_context(value=None):
    if value is None:
        return dict(pathogen_type=None,membrane_design_confirm=False,low_conf_design_confirm=False)
    ensure(isinstance(value,dict) and set(value)==DESIGN_CONTEXT_FIELDS,
        'INVALID_REQUEST','Exact R-57 design context required')
    ensure(value['pathogen_type'] is None or value['pathogen_type'] in PATHOGEN_TYPES,
        'INVALID_REQUEST','Registered pathogen type or null required')
    ensure(type(value['membrane_design_confirm']) is bool and type(value['low_conf_design_confirm']) is bool,
        'INVALID_REQUEST','Explicit R-57 confirmations must be booleans')
    return value


def request(raw):
    value=decode(raw)
    required={'protein_sequence','user_sequence_id','host_species','organism','upstream','timeout_seconds'}
    ensure(isinstance(value,dict) and set(value) in (required,required|{'design_context'}),
        'INVALID_REQUEST','Exact local WT draft request required')
    value['design_context']=design_context(value.get('design_context'))
    ensure(isinstance(value['protein_sequence'],str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,20000}',value['protein_sequence']),
        'INVALID_REQUEST','Exact uppercase AA20 sequence required')
    ensure(isinstance(value['user_sequence_id'],str) and 0<len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','Bounded user sequence label required')
    for field in ('host_species','organism'):
        ensure(value[field] is None or isinstance(value[field],str) and 0<len(value[field].strip())<=512,
            'INVALID_REQUEST','Species must be an explicit nonempty input fact or null')
    ensure(isinstance(value['upstream'],dict) and set(value['upstream'])==set(PRODUCERS),
        'INVALID_REQUEST','All registered upstream slots must be explicit, with null for missing input')
    for source in value['upstream'].values():
        if source is None:continue
        ensure(isinstance(source,dict) and set(source)=={'job_id','artifact'} and isinstance(source['job_id'],str)
            and re.fullmatch('t01p1r-job-[0-9a-f]{32}',source['job_id']), 'INVALID_REQUEST','Exact registered task source required')
        ref=source['artifact']
        if ref is None:continue
        ensure(isinstance(ref,dict) and set(ref)==ARTIFACT_FIELDS and ref['job_id']==source['job_id']
            and ref['role'] in ('result','diagnostic') and ref['media_type']=='application/json'
            and ref['evidence_kind']=='G0_REAL_OUTPUT' and isinstance(ref['sha256'],str)
            and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['size_bytes']) is int
            and 0<ref['size_bytes']<=32*1024**2,'INVALID_REQUEST','Exact result/diagnostic ArtifactRef required')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=60,
        'INVALID_REQUEST','Local draft deadline must be 1..60 seconds')
    return value


def sequence_id(seq):return 't01wt_'+sha(seq.encode())[:16]


def registered_rules():
    return dict(id='w4-gate-wt-local-draft-v105',version='0.2.0',sha256=sha(encode(dict(
        sources={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        code={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},
        sections=['R-57','T-01 step 14','S-42','S-43','S-44','T-01 steps 24-28','Schema 1','Schema 2'],
        unresolved=['OI-013','OI-014','OI-021 formal state/signoff'],business_gate='R57_IMPLEMENTED',
        scientific_gate=False,agent_c_handoff=False))))


def registered_profile():
    paths=list(HERE.glob('*.py'))+[HERE.parent/name for name in ('runtime.py','registry.py','contracts.py','cli.py')]
    return dict(id='w4-local-wt-assessment-draft',version='0.2.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),
        python=sys.version,python_sha256=sha(Path(sys.executable).read_bytes()),base=base_profile(),
        backend='trusted-local-in-process',network=False,production_protocol=False))))
