"""Fixed N07/S-12 request, execution and rule registrations."""
from pathlib import Path
import re
import sys

import Bio

from ...common import REPO, decode, encode, ensure, identifier, profile as base_profile, sha

TOOL='t01.real.glycosylation'
NODE='N07'
MAX_AA=20000
HERE=Path(__file__).parent
HOTSPOT_STATES=frozenset(('not_provided','upstream_unavailable','available'))
SOP=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md'
SCHEMA=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md'
SKILL=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SKILL_v10.5_20260902.md'
AUTHORITY=(SOP,SCHEMA,SKILL)


def _source(value,state):
    if state=='not_provided':
        ensure(value is None,'INVALID_REQUEST','A not_provided hotspot input cannot claim a source')
        return
    ensure(isinstance(value,dict) and set(value)=={'node_id','source_id','sha256'},
        'INVALID_REQUEST','Hotspot source must contain node_id, source_id and sha256 only')
    ensure(value['node_id']=='N06','INVALID_REQUEST','Hotspot source must be an N06 result or contract fixture')
    identifier(value['source_id'])
    digest=value['sha256']
    if state=='available':
        ensure(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),
            'INVALID_REQUEST','Available hotspot input requires its source SHA-256')
    else:
        ensure(digest is None or isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),
            'INVALID_REQUEST','Unavailable hotspot source SHA-256 must be null or lowercase hex')


def _hotspot_input(value,length):
    ensure(isinstance(value,dict) and set(value)=={'state','hotspots','source','reason_code'},
        'INVALID_REQUEST','Exact hotspot state, hotspots, source and reason_code fields required')
    state=value['state'];ensure(state in HOTSPOT_STATES,'INVALID_REQUEST','Unsupported hotspot input state')
    _source(value['source'],state)
    if state=='available':
        ensure(value['reason_code'] is None and isinstance(value['hotspots'],list) and len(value['hotspots'])<=1000,
            'INVALID_REQUEST','Available hotspots require a bounded list and no failure reason')
        previous=None;seen=set()
        for item in value['hotspots']:
            ensure(isinstance(item,dict) and set(item)=={'start','end'},
                'INVALID_REQUEST','Each hotspot requires start and end only')
            start,end=item['start'],item['end']
            ensure(type(start) is int and type(end) is int and 1<=start<=end<=length,
                'INVALID_REQUEST','Hotspot coordinates must be 1-based inclusive and inside the sequence')
            ensure(end-start+1==20,'INVALID_REQUEST','R-25 hotspot windows must be exactly 20 aa')
            pair=(start,end);ensure(pair not in seen,'INVALID_REQUEST','Duplicate hotspot interval')
            ensure(previous is None or pair>previous,'INVALID_REQUEST','Hotspot intervals must be sorted')
            seen.add(pair);previous=pair
    else:
        ensure(value['hotspots'] is None,'INVALID_REQUEST','Uncomputed hotspot input must use hotspots=null')
        if state=='not_provided':
            ensure(value['reason_code'] is None,'INVALID_REQUEST','not_provided has no upstream failure reason')
        else:
            ensure(isinstance(value['reason_code'],str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',value['reason_code']),
                'INVALID_REQUEST','upstream_unavailable requires a bounded reason code')
    return value


def request(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)=={'protein_sequence','user_sequence_id','hotspot_input','timeout_seconds'},
        'INVALID_REQUEST','Exact sequence, alias, hotspot_input and timeout fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and 1<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','N07 requires exact uppercase AA20, 1..20000 aa; no normalization')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','User sequence ID must be bounded metadata')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=60,
        'INVALID_REQUEST','Local scan deadline must be 1..60 seconds')
    _hotspot_input(value['hotspot_input'],len(seq))
    return value


def sequence_id(sequence):
    return 't01seq_'+sha(sequence.encode())


def registered_rules():
    authority={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY}
    rules=dict(authority=authority,motif='N-X-S/T (X != P)',coordinates='1-based sequon N position',
        expression_hint_threshold=3,expression_hint='真核表达优先',hotspot_window='1-based inclusive exact 20 aa',
        shielding_threshold_per_window=2,unavailable_hotspots_yield_schema_value=False,
        unavailable_hotspots_evaluation='NOT_PERFORMED',scientific_signoff=False)
    return dict(id='w3-s12-r25-r26-development',version='10.5-20260902',sha256=sha(encode(rules)))


def registered_profile():
    paths=list(HERE.glob('*.py'))
    paths += [HERE.parent/name for name in ('runtime.py','registry.py','contracts.py','cli.py')]
    paths += [REPO/'scripts/t01_runtime.py',REPO/'requirements/glycosylation.txt']
    policy=dict(files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(paths)},
        base_runtime=base_profile(),python_version=sys.version,python_executable_sha256=sha(Path(sys.executable).read_bytes()),
        biopython_version=Bio.__version__,backend='trusted-local-in-process',network=False,container=False,
        aa_min=1,aa_max=MAX_AA,max_wall_seconds=60,rule_profile=registered_rules(),scientific_consumption=False)
    return dict(id='w3-s12-biopython-local-development',version='0.1.0',sha256=sha(encode(policy)))
