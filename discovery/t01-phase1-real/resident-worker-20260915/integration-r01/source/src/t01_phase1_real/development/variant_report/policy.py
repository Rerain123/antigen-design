"""Only registered artifacts enter the report; numeric fixtures have no runtime route."""
from pathlib import Path
import re
from ...common import REPO,decode,encode,ensure,sha
from ..design_backend import policy as design
from ..foldx.policy import artifact,AUTHORITY

TOOL='t01.real.variant_report'
NODE='N15'
HERE=Path(__file__).parent
PRODUCERS={'design_audit':design.TOOL,'foldx':'t01.real.foldx'}

def request(raw):
    body=decode(raw)
    ensure(isinstance(body,dict) and set(body)-{'n13_source'}=={'protein_sequence','user_sequence_id','upstream','variant_source','foldx_bindings','timeout_seconds'},
        'INVALID_REQUEST','Exact variant report request required')
    ensure(isinstance(body['protein_sequence'],str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,1000}',body['protein_sequence']),
        'INVALID_REQUEST','Exact WT AA20 required')
    ensure(isinstance(body['user_sequence_id'],str) and 0<len(body['user_sequence_id'])<=512,'INVALID_REQUEST','Bounded label required')
    ensure(body['variant_source'] in ('N11_DESIGN_AUDIT','FOLDX_EXPLICIT_ENGINEERING'),'INVALID_REQUEST','Explicit variant origin required')
    ensure(isinstance(body['upstream'],dict) and set(body['upstream'])==set(PRODUCERS),'INVALID_REQUEST','Explicit source slots required')
    for src in body['upstream'].values():
        if src is None:continue
        ensure(isinstance(src,dict) and set(src)=={'job_id','artifact'} and isinstance(src['job_id'],str)
            and re.fullmatch('t01p1r-job-[0-9a-f]{32}',src['job_id']),'INVALID_REQUEST','Exact registered job required')
        if src['artifact'] is not None:
            ensure(isinstance(src['artifact'],dict),'INVALID_REQUEST','Artifact must be an object')
            ref=dict(src['artifact'])
            ensure(ref.get('job_id')==src['job_id'] and ref.get('role') in ('result','diagnostic'),'INVALID_REQUEST','Source ID/role differs')
            ref['role']='result';artifact(ref)
    links=body['foldx_bindings']
    ensure(isinstance(links,list) and len(links)<=24,'INVALID_REQUEST','Bounded explicit sample-to-FoldX links required')
    for link in links:
        ensure(isinstance(link,dict) and set(link)=={'sample_number','variant_id'} and type(link['sample_number']) is int
            and 1<=link['sample_number']<=24 and isinstance(link['variant_id'],str) and 0<len(link['variant_id'])<=256,
            'INVALID_REQUEST','Exact sample number and variant ID required')
    ensure(len({r['sample_number'] for r in links})==len(links) and len({r['variant_id'] for r in links})==len(links),
        'INVALID_REQUEST','Ambiguous duplicate links forbidden')
    if body['variant_source']=='FOLDX_EXPLICIT_ENGINEERING':
        ensure(not links and body['upstream']['design_audit'] is None,'INVALID_REQUEST','Standalone FoldX engineering records cannot claim N11 identity')
    ensure(type(body['timeout_seconds']) is int and 1<=body['timeout_seconds']<=60,'INVALID_REQUEST','Deadline 1..60 seconds required')
    if 'n13_source' in body:
        from ..epitope_protection.policy import source
        source(body['n13_source'])
    return body

def sequence_id(seq):return 't01report_'+sha(seq.encode())[:16]

def registered_rules():
    return dict(id='w6-step19b20-engineering-report',version='0.1.0',sha256=sha(encode(dict(
        authority={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        sections=['T-01 step19b','T-01 step20','C35 BuildModel'],
        implementation={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},scientific_release=False))))

def registered_profile():
    paths=list(HERE.glob('*.py'))
    for package in ('design_backend','foldx','proteinmpnn','esm_if1','epitope_protection'):
        paths.extend((HERE.parent/package).glob('*.py'))
    paths.extend(HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py'))
    return dict(id='w6-variant-report-local',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},
        design_profile=design.registered_profile(),rules=registered_rules(),network=False))))
