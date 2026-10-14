"""N06 request, source-reference shape and registered rule/profile identity."""
import re
from pathlib import Path

from ...common import REPO, decode, encode, ensure, identifier, profile as base_profile, sha

TOOL='t01.real.epitope_map'
NODE='N06'
MAX_AA=20000
HERE=Path(__file__).parent
SOURCE_STATES=frozenset(('available','upstream_unavailable','not_provided'))
ARTIFACT_FIELDS={'artifact_id','run_id','job_id','attempt_id','role','media_type','sha256','size_bytes','evidence_kind'}
SOP=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md'
SCHEMA=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_Schema_v10.5_20260902.md'
TOOLSPEC=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_A1_NetMHCpan_v10.5.md'
AUTHORITY=(SOP,SCHEMA,TOOLSPEC)


def _artifact(value,state):
    if state=='not_provided':
        ensure(value is None,'INVALID_REQUEST','not_provided source cannot claim an artifact')
        return
    ensure(isinstance(value,dict) and set(value)==ARTIFACT_FIELDS,'INVALID_REQUEST','Source requires an exact ArtifactRef')
    for name in ('artifact_id','run_id','job_id','attempt_id'):identifier(value[name])
    ensure(value['role']==('result' if state=='available' else 'diagnostic')
        and value['media_type']=='application/json' and value['evidence_kind']=='G0_REAL_OUTPUT',
        'INVALID_REQUEST','Source ArtifactRef role/media/evidence differs from its state')
    ensure(isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256'])
        and type(value['size_bytes']) is int and 0<value['size_bytes']<=32*1024**2,
        'INVALID_REQUEST','Source ArtifactRef digest/size is invalid')


def _source(value):
    ensure(isinstance(value,dict) and set(value)=={'state','artifact','reason_code'},
        'INVALID_REQUEST','Each upstream input requires exact state, artifact and reason_code fields')
    state=value['state'];ensure(state in SOURCE_STATES,'INVALID_REQUEST','Unsupported upstream input state')
    _artifact(value['artifact'],state)
    if state=='available':ensure(value['reason_code'] is None,'INVALID_REQUEST','Available source has no failure reason')
    elif state=='not_provided':ensure(value['reason_code'] is None,'INVALID_REQUEST','not_provided source has no failure reason')
    else:ensure(isinstance(value['reason_code'],str) and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',value['reason_code']),
        'INVALID_REQUEST','Unavailable source requires a bounded reason code')
    return value


def request(raw):
    value=decode(raw)
    expected={'protein_sequence','user_sequence_id','bepipred_input','netmhc_input','blast_input','timeout_seconds'}
    ensure(isinstance(value,dict) and set(value)==expected,'INVALID_REQUEST','Exact N06 sequence/source/BLAST/deadline fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and 15<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','N06 requires exact uppercase AA20, 15..20000 aa; no normalization')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','User sequence ID must be bounded metadata')
    _source(value['bepipred_input']);_source(value['netmhc_input'])
    blast=value['blast_input']
    ensure(blast=={'state':'not_executed','reason_code':'OI_028_TARGET_DATABASE_NOT_AVAILABLE'},
        'INVALID_REQUEST','N03 is not executed until the OI-028 target database is approved')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=60,
        'INVALID_REQUEST','N06 local calculation deadline must be 1..60 seconds')
    return value


def sequence_id(sequence):return 't01seq_'+sha(sequence.encode())


def registered_rules():
    authority={path.relative_to(REPO).as_posix():sha(path.read_bytes()) for path in AUTHORITY}
    rules=dict(authority=authority,coordinates='1-based inclusive',t_cell_hit_mapping='native peptide start/end',
        residue_rank='minimum percent_rank among covering peptides',rank_direction='1-minmax; lower native rank is better',
        presentation_hotspot='residues covered by SB hits from >=2 distinct alleles; merge intervals separated by <=10 residues',
        native_bind_level_recomputed=False,bepipred_raw_columns_bound=True,bepipred_peak_selection='OI-026_REVIEW_REQUIRED',
        evidence_weights='OI-007_REVIEW_REQUIRED',density_per_residue=None,b_cell_antigenic_hotspots=None,
        blast='NOT_EXECUTED_OI-028',scientific_signoff=False)
    return dict(id='w2-s19-bounded-map-development',version='10.5-20260902',sha256=sha(encode(rules)))


def registered_profile():
    paths=list(HERE.glob('*.py'))
    paths += [HERE.parent/name for name in ('runtime.py','registry.py','contracts.py','cli.py')]
    paths += [REPO/'scripts/t01_runtime.py']
    profile=dict(files={path.relative_to(REPO).as_posix():sha(path.read_bytes()) for path in sorted(paths)},
        base_runtime=base_profile(),backend='trusted-local-in-process',network=False,container=False,
        aa_min=15,aa_max=MAX_AA,max_wall_seconds=60,rule_profile=registered_rules(),scientific_consumption=False)
    return dict(id='w2-n06-local-map-development',version='0.1.0',sha256=sha(encode(profile)))
