"""Explicit local engineering requests; no caller-supplied scientific evidence or scores."""
from pathlib import Path
import sys
import re
from ...common import REPO,decode,encode,ensure,sha,profile as base_profile
from ..wt_draft.policy import request as wt_request,PRODUCERS as WT_PRODUCERS
from ..esm_if1.policy import artifact

TOOL='t01.real.design_audit'
NODE='N12'
HERE=Path(__file__).parent
PRODUCERS={k:WT_PRODUCERS[k] for k in ('structure','topology','epitope_map','glycosylation','homology','domains')}
PRODUCERS.update(n11='t01.real.proteinmpnn',esm_if1='t01.real.esm_if1')
AA='ACDEFGHIKLMNPQRSTVWY'


def request(raw):
    body=decode(raw)
    ensure(isinstance(body,dict) and set(body)=={'protein_sequence','user_sequence_id','upstream','user_regions',
        'objective','epitope_policy','epitope_mode','membrane_design_confirm','sample_numbers','timeout_seconds'},
        'INVALID_REQUEST','Exact combined design audit request required')
    seq=body['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,1000}',seq),'INVALID_REQUEST','WT AA20 length 1..1000 required')
    ensure(isinstance(body['user_sequence_id'],str) and 0<len(body['user_sequence_id'])<=512,'INVALID_REQUEST','Bounded input label required')
    ensure(isinstance(body['upstream'],dict) and set(body['upstream'])==set(PRODUCERS),'INVALID_REQUEST','All upstream slots must be explicit')
    for source in body['upstream'].values():
        if source is None:continue
        ensure(isinstance(source,dict) and set(source)=={'job_id','artifact'} and isinstance(source['job_id'],str)
            and re.fullmatch('t01p1r-job-[0-9a-f]{32}',source['job_id']),'INVALID_REQUEST','Exact registered source required')
        if source['artifact'] is not None:
            ref=source['artifact'];ensure(isinstance(ref,dict),'INVALID_REQUEST','Artifact object required');copy=dict(ref)
            ensure(ref.get('role') in ('result','diagnostic') and ref.get('job_id')==source['job_id'],'INVALID_REQUEST','Source identity differs')
            copy['role']='result';artifact(copy)
    ensure(body['objective'] in ('general','solubility','thermostability'),'INVALID_REQUEST','Supported burden objective required')
    ensure(body['epitope_policy']=='PRESERVE','INVALID_REQUEST','Other epitope policy semantics remain unresolved')
    ensure(body['epitope_mode'] in ('both','bcell_only','tcell_only') and type(body['membrane_design_confirm']) is bool,'INVALID_REQUEST','Explicit mode/confirmation required')
    numbers=body['sample_numbers']
    ensure(isinstance(numbers,list) and len(numbers)<=24 and all(type(n) is int and 1<=n<=24 for n in numbers)
        and len(numbers)==len(set(numbers)),'INVALID_REQUEST','Unique N11 sample numbers required')
    users=body['user_regions']
    ensure(isinstance(users,list) and len(users)<=1000,'INVALID_REQUEST','Bounded explicit user regions required')
    for row in users:
        ensure(isinstance(row,dict) and set(row)=={'start','end','permission','allowed_residues','source_id'},'INVALID_REQUEST','Exact user region required')
        ensure(type(row['start']) is int and type(row['end']) is int and 1<=row['start']<=row['end']<=len(seq),'INVALID_REQUEST','User coordinates must be 1-based inclusive')
        ensure(row['permission'] in ('FIXED','RESTRICTED','OPEN') and isinstance(row['source_id'],str) and 0<len(row['source_id'])<=512,'INVALID_REQUEST','Explicit user instruction identity required')
        allowed=row['allowed_residues']
        if row['permission']=='RESTRICTED' and allowed is not None:
            ensure(isinstance(allowed,str) and 0<len(allowed)<20 and len(set(allowed))==len(allowed)
                and set(allowed)<=set(AA) and set(seq[row['start']-1:row['end']])<=set(allowed),'INVALID_REQUEST','Restricted AA20 proper subset must contain all WT residues')
        else:ensure(allowed is None,'INVALID_REQUEST','Only RESTRICTED may specify allowed residues')
    ensure(type(body['timeout_seconds']) is int and 1<=body['timeout_seconds']<=60,'INVALID_REQUEST','Local deadline 1..60 seconds required')
    return body


def sequence_id(seq):return 't01design_'+sha(seq.encode())[:16]


def registered_rules():
    root=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    return dict(id='w5-s27-s28-engineering-v105',version='0.1.0',sha256=sha(encode(dict(
        authority={n:sha((root/n).read_bytes()) for n in ('AgentA_SOP_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md',
            'ToolSpec_C15_ProteinMPNN_v10.5.md','ToolSpec_C18_ESM-IF1_v10.5.md')},
        implementation={p.name:sha(p.read_bytes()) for p in HERE.glob('*') if p.suffix in ('.py','.json','.txt')},scientific_release=False))))


def registered_profile():
    paths=[p for p in HERE.glob('*') if p.suffix in ('.py','.json','.txt')]
    paths += [HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py')]
    for package in ('proteinmpnn','esm_if1'):
        paths += [p for p in (HERE.parent/package).glob('*') if p.suffix in ('.py','.json')]
    paths += list((REPO/'src/t01_structure_mapping').glob('*.py'))
    return dict(id='w5-design-permissions-burden-local',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},python=sys.version,
        python_sha256=sha(Path(sys.executable).read_bytes()),rules=registered_rules(),base=base_profile(),
        backend='trusted-local-in-process',network=False))))
