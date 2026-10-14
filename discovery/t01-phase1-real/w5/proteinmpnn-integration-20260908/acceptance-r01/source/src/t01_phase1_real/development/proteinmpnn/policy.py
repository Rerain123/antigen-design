"""Pinned GPU ProteinMPNN profile and exhaustive explicit engineering masks."""
from pathlib import Path
import math
import re
from ...common import REPO, decode, encode, ensure, sha, profile as base_profile
from ...files import read_locked, no_links
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL='t01.real.proteinmpnn'
NODE='N11'
HERE=Path(__file__).parent
PACKAGE=REPO/'var/t01-phase1-real/tool-assets/proteinmpnn-8907e6671bfb'
COMMIT='8907e6671bfbfc92303b5f79c4b5e6ce47cdef57'
MODEL='v_48_020'
IMAGE='sha256:5b6baa8ebc5660bd3de9cf8b6d1694c7de35fadd23fea6cd7a8352a536e3f3af'
SLOT='t01p1r-proteinmpnn-development-slot'
LIMITS=dict(memory=4*1024**3,cpus=2,cpuset='0-1',pids=128)
ALPHABET='ACDEFGHIKLMNPQRSTVWY'
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
AUTHORITY=[AUTHORITY_ROOT/n for n in ('ToolSpec_C15_ProteinMPNN_v10.5.md','AgentA_SOP_v10.5_20260902.md')]


def request(raw):
    body=decode(raw)
    ensure(isinstance(body,dict) and set(body)=={'protein_sequence','user_sequence_id','structure_artifact','constraints',
        'n_designs','sampling_temperature','seed','timeout_seconds'},'INVALID_REQUEST','Exact N11 engineering request required')
    seq=body['protein_sequence'];ensure(isinstance(seq,str) and re.fullmatch('['+ALPHABET+']{1,1000}',seq),
        'INVALID_REQUEST','Exact uppercase AA20 sequence, 1..1000 aa required')
    ensure(isinstance(body['user_sequence_id'],str) and 0<len(body['user_sequence_id'])<=512,'INVALID_REQUEST','Bounded user sequence label required')
    ref=body['structure_artifact']
    ensure(isinstance(ref,dict) and set(ref)==ARTIFACT_FIELDS and ref['role']=='result' and ref['media_type']=='application/json'
        and ref['evidence_kind']=='G0_REAL_OUTPUT' and isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
        and type(ref['size_bytes']) is int and 0<ref['size_bytes']<=32*1024**2,'INVALID_REQUEST','Registered successful structure ArtifactRef required')
    c=body['constraints']
    ensure(isinstance(c,dict) and set(c)=={'purpose','source_id','fixed_positions','restricted_positions','open_positions'}
        and c['purpose']=='ENGINEERING_EXPLICIT_MASKS' and isinstance(c['source_id'],str) and 0<len(c['source_id'])<=512,
        'INVALID_REQUEST','Explicit traceable engineering masks are required; scientific permission synthesis is closed')
    ensure(all(isinstance(c[k],list) for k in ('fixed_positions','restricted_positions','open_positions')),
        'INVALID_REQUEST','Constraint lists required')
    positions=[]
    for key in ('fixed_positions','open_positions'):
        ensure(all(type(p) is int and 1<=p<=len(seq) for p in c[key]),'INVALID_REQUEST','Position outside bound sequence')
        positions.extend(c[key])
    for item in c['restricted_positions']:
        ensure(isinstance(item,dict) and set(item)=={'position','allowed_residues'} and type(item['position']) is int
            and 1<=item['position']<=len(seq),'INVALID_REQUEST','Invalid restricted position')
        allowed=item['allowed_residues']
        ensure(isinstance(allowed,str) and 1<=len(allowed)<20 and len(set(allowed))==len(allowed)
            and set(allowed)<=set(ALPHABET) and seq[item['position']-1] in allowed,
            'INVALID_REQUEST','Restricted hard allow-set must include WT and be an explicit AA20 subset')
        positions.append(item['position'])
    ensure(len(positions)==len(seq) and set(positions)==set(range(1,len(seq)+1)),
        'INVALID_REQUEST','Every sequence position must have exactly one explicit engineering permission')
    ensure(c['fixed_positions'],'INVALID_REQUEST','Empty FIXED mask requires unresolved T4 confirmation; this profile does not accept it')
    ensure(type(body['n_designs']) is int and 1<=body['n_designs']<=24,'INVALID_REQUEST','Engineering sample count must be 1..24 (workflow default 24)')
    ensure(type(body['sampling_temperature']) in (int,float) and math.isfinite(body['sampling_temperature'])
        and body['sampling_temperature']==0.1,'INVALID_REQUEST','This profile fixes the workflow sampling temperature at 0.1')
    ensure(type(body['seed']) is int and 1<=body['seed']<=2147483647,'INVALID_REQUEST','Explicit nonzero reproducible seed required')
    ensure(type(body['timeout_seconds']) is int and 1<=body['timeout_seconds']<=900,'INVALID_REQUEST','Deadline must be 1..900 seconds')
    return body


def sequence_id(seq):return 't01mpnn_'+sha(seq.encode())[:16]


def registered_rules():
    return dict(id='w5-n11-proteinmpnn-explicit-engineering-masks',version='0.1.0',sha256=sha(encode(dict(
        authority={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        files={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},commit=COMMIT,
        default_count=24,temperature=0.1,permission_synthesis=False,scientific_gate=False))))


def registered_profile():
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))+[HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py','docker.py','supervisor.py')]
    paths+=list((REPO/'src/t01_structure_mapping').glob('*.py'))+[REPO/'requirements/proteinmpnn.Dockerfile']
    return dict(id='w5-n11-proteinmpnn-gpu-local-development',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),
        image=IMAGE,limits=LIMITS,device='cuda:0',max_total_residues=1000,base=base_profile(),scientific_consumption=False))))


def verify_assets():
    receipt=decode(read_locked(HERE/'assets.json',131072))
    ensure(receipt['commit']==COMMIT and receipt['image']==IMAGE,'ASSET_MISSING','Pinned ProteinMPNN asset registry mismatch')
    for item in receipt['files']:
        path=no_links(REPO/item['path'])
        ensure(path.is_file() and path.stat().st_size==item['bytes'],'ASSET_MISSING','Missing ProteinMPNN asset: '+item['path'])
        ensure(sha(read_locked(path,32*1024**2))==item['sha256'],'HASH_MISMATCH','ProteinMPNN asset changed: '+item['path'])
    return receipt
