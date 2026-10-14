"""Exact N10 request and immutable development profiles."""
from pathlib import Path
import math
import re
import sys

import Bio
import propka

from ...common import REPO, decode, encode, ensure, sha, profile as base_profile
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL='t01.real.developability'
NODE='N10'
HERE=Path(__file__).parent
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
AUTHORITY=[AUTHORITY_ROOT/name for name in (
    'AgentA_SOP_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md','AgentA_SKILL_v10.5_20260902.md',
    'ToolSpec_C44_CamSol重实现_v10.5.md','ToolSpec_C45_AGGRESCAN3D_v10.5.md','ToolSpec_C24_PROPKA_v10.5.md')]
DIMENSIONS=('solubility','aggregation','ph_stability','tag_exposure','expressibility','stability_ddg')


def sequence(value):
    ensure(isinstance(value,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,20000}',value),
        'INVALID_REQUEST','Exact uppercase AA20 sequence, 1..20000 aa required')


def source(value):
    ensure(isinstance(value,dict) and set(value)=={'state','artifact','reason_code'},
        'INVALID_REQUEST','Exact structure state/ref/reason required')
    ensure(value['state'] in ('not_provided','available','upstream_unavailable'),
        'INVALID_REQUEST','Invalid structure source state')
    ref=value['artifact']
    if value['state']=='not_provided':
        ensure(ref is None and value['reason_code'] is None,'INVALID_REQUEST','Absent structure must not claim a source')
        return
    ensure(isinstance(ref,dict) and set(ref)==ARTIFACT_FIELDS and ref['role'] in ('result','diagnostic')
        and ref['media_type']=='application/json' and ref['evidence_kind']=='G0_REAL_OUTPUT',
        'INVALID_REQUEST','Registered local-structure ArtifactRef required')
    ensure(isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
        and type(ref['size_bytes']) is int and 0<ref['size_bytes']<=32*1024**2,
        'INVALID_REQUEST','Invalid structure artifact digest/size')
    ensure(value['reason_code'] is None if value['state']=='available' else isinstance(value['reason_code'],str)
        and 0<len(value['reason_code'])<=128,'INVALID_REQUEST','Invalid structure reason')


def _number(value):return type(value) in (int,float) and math.isfinite(value)


def request(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)=={'protein_sequence','user_sequence_id','structure_input','target_ph',
        'target_ph_range','dimension_weights','timeout_seconds'},'INVALID_REQUEST','Exact N10 request fields required')
    sequence(value['protein_sequence'])
    ensure(isinstance(value['user_sequence_id'],str) and 0<len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','Invalid user_sequence_id')
    source(value['structure_input'])
    ensure(value['target_ph'] is None or _number(value['target_ph']),'INVALID_REQUEST','target_ph must be a finite number or null')
    ph=value['target_ph_range']
    ensure(isinstance(ph,list) and len(ph)==2 and all(_number(x) for x in ph) and ph[0]<ph[1],
        'INVALID_REQUEST','target_ph_range must be an increasing finite pair')
    width=ph[1]-ph[0]
    ensure(math.isfinite(width) and round(width/40,1)>0,
        'INVALID_REQUEST','target_ph_range must generate a positive finite 0.1-rounded grid')
    weights=value['dimension_weights']
    if weights is not None:
        ensure(isinstance(weights,dict) and set(weights)==set(DIMENSIONS) and all(_number(x) and x>=0 for x in weights.values())
            and sum(weights.values())>0,'INVALID_REQUEST','Weights require all six ordered nonnegative dimensions and positive total')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=60,
        'INVALID_REQUEST','N10 deadline 1..60 seconds required')
    return value


def sequence_id(seq):return 't01dev_'+sha(seq.encode())[:16]


def _propka_assets():
    root=Path(propka.__file__).parent
    paths=sorted(root.rglob('*.py'))+[root/'propka.cfg']
    return {path.relative_to(root).as_posix():sha(path.read_bytes()) for path in paths}


def registered_rules():
    return dict(id='w4-n10-s36a-s38-s39-s40-v105-development',version='0.2.0',sha256=sha(encode(dict(
        sources={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        code={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},
        implemented_steps=['S-36a','S-39','S-38-development','S-40-partial'],pending_steps=['S-36','S-37','S-38-GUI-benchmark'],
        unresolved=['OI-015','OI-021','OI-025','OI-027','OI-032','OI-033'],scientific_consumption=False))))


def registered_profile():
    paths=list(HERE.glob('*.py'))+[HERE.parent/name for name in ('runtime.py','registry.py','contracts.py','cli.py')]
    return dict(id='w4-n10-local-developability-partial',version='0.2.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),
        requirements_sha256=sha((REPO/'requirements/developability.txt').read_bytes()),biopython=Bio.__version__,
        propka_version=propka.__version__,propka_assets=_propka_assets(),
        python=sys.version,python_sha256=sha(Path(sys.executable).read_bytes()),base=base_profile(),
        backend='trusted-local-hybrid',network=False,overall_requires_solubility=True,
        unavailable=dict(camsol='OI-025_PARAMETERS_INCOMPLETE',aggregation='OFFICIAL_ASSET_NOT_REGISTERED'),
        propka=dict(version=propka.__version__,status='REGISTERED_DEVELOPMENT_UNREVIEWED',gui_benchmark='PENDING')))))
