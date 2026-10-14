from pathlib import Path
from ...common import decode,encode,ensure,sha,REPO
from ..variant_report.policy import request as report_request
from ..design_backend.policy import TOOL as DESIGN_AUDIT_TOOL
from ..foldx.policy import artifact

TOOL='t01.real.epitope_protection'
NODE='N13'
HERE=Path(__file__).parent
PRODUCERS={'design_audit':DESIGN_AUDIT_TOOL}
SIDE_PRODUCERS={'structure':'t01.real.ingest_structure','epitope_map':'t01.real.epitope_map','domains':'t01.real.domains'}
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
AUTHORITY=[AUTHORITY_ROOT/n for n in ('AgentA_SOP_v10.5_20260902.md','AgentA_SKILL_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md',
    '一期裁剪算法图（一期 18 节点 + 落地优先级）.md')]

def source(src):
    if src is None:return
    ensure(isinstance(src,dict) and set(src)=={'job_id','artifact'} and isinstance(src['job_id'],str),'INVALID_REQUEST','Exact registered source required')
    ref=src['artifact']
    if ref is not None:
        ensure(isinstance(ref,dict) and ref.get('job_id')==src['job_id'] and ref.get('role') in ('result','diagnostic'),'INVALID_REQUEST','Source artifact identity differs')
        ref=dict(ref);ref['role']='result';artifact(ref)

def request(raw):
    b=decode(raw)
    ensure(isinstance(b,dict) and set(b)=={'protein_sequence','user_sequence_id','upstream','preselection','pairs','timeout_seconds'},'INVALID_REQUEST','Exact N13 request required')
    report_request(encode(dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],
        upstream=dict(design_audit=None,foldx=None),variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=b['timeout_seconds'])))
    ensure(isinstance(b['upstream'],dict) and set(b['upstream'])=={'design_audit'} and b['upstream']['design_audit'] is not None,
        'INVALID_REQUEST','Registered N12 design audit required')
    source(b['upstream']['design_audit'])
    fact=b['preselection']
    ensure(isinstance(fact,dict) and set(fact)-{'validation_source','selection_scope'}=={'kind','source','sample_numbers','records_sha256','total_records','selected','scientific_eligible'}
        and fact['kind']=='N12_REPRESENTATIVE_PRESELECTION' and fact['source']==b['upstream']['design_audit']
        and fact['scientific_eligible'] is False and isinstance(fact['sample_numbers'],list)
        and isinstance(fact['selected'],list) and len(fact['selected'])<=(64 if fact.get('selection_scope')=='ALL_VALIDATED' else 3)
        and [r.get('sample_number') for r in fact['selected']]==fact['sample_numbers'],
        'INVALID_REQUEST','Exact N12 internal preselection required')
    if 'validation_source' in fact:
        context=fact['validation_source']
        from ..workflow.validation import NAMES
        ensure(isinstance(context,dict) and set(context)=={'workflow_job_id','node'} and
            isinstance(context['workflow_job_id'],str) and context['node'] in NAMES,
            'INVALID_REQUEST','Exact S28 workflow validation context required')
    ensure(fact.get('selection_scope') in (None,'ALL_VALIDATED') and
        (fact.get('selection_scope') is None or 'validation_source' in fact),'INVALID_REQUEST','Full pool needs S28 source')
    ensure(isinstance(b['pairs'],list) and len(b['pairs'])<=64,'INVALID_REQUEST','Bounded selected variant pairs required')
    ids=[]
    for pair in b['pairs']:
        ensure(isinstance(pair,dict) and set(pair)=={'variant_id','wt','variant'} and isinstance(pair['variant_id'],str),'INVALID_REQUEST','Exact pair identity required')
        ids.append(pair['variant_id'])
        for side in ('wt','variant'):
            ensure(isinstance(pair[side],dict) and set(pair[side])==set(SIDE_PRODUCERS),'INVALID_REQUEST','All side sources explicit')
            for src in pair[side].values():source(src)
    ensure(len(ids)==len(set(ids)),'INVALID_REQUEST','Duplicate paired variant')
    ensure(ids==[r.get('id') for r in fact['selected']],'INVALID_REQUEST','N13 pairs must match N12 selected representatives')
    return b

def sequence_id(seq):return 't01n13_'+sha(seq.encode())[:16]

def registered_rules():
    from ..expert_feedback import authority as feedback
    return dict(id='w6-n13-r56-engineering',version='20261009-v1',sha256=sha(encode(dict(
        expert_feedback=feedback(),
        authority={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        code={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},scientific_release=False))))

def registered_profile():
    paths=list(HERE.glob('*.py'))
    for package in ('variant_report','design_backend','structure','epitope_map','workflow'):
        paths.extend((HERE.parent/package).glob('*.py'))
    paths.extend(HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py'))
    return dict(id='w6-n13-local-paired-observation',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),network=False))))
