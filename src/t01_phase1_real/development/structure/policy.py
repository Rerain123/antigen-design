"""Explicit local structure input domain and fixed offline execution registration."""
import re
from pathlib import Path

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import read_locked

TOOL='t01.real.ingest_structure'
NODE='N01'
IMAGE='sha256:bb6c6b5ce1add12dc9bda3538a218568a9e80c048c12525fc130eaa970dbb9e5'
SLOT='t01p1r-structure-development-slot'
HERE=Path(__file__).parent
PROFILE=REPO/'docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json'
MAX_STRUCTURE_BYTES=4*1024**2
MAX_AA=2000  # Bounded local integration input, not a project/model maximum.
LIMITS=dict(memory=1024**3,cpus=2,cpuset='0-1',pids=64)
FIELDS={'protein_sequence','host_species','structure_name','declared_format','selection','context_chain_ids','source_declaration','timeout_seconds'}


def metadata(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)==FIELDS,'INVALID_REQUEST','Exact local structure metadata fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and 9<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','Local development sequence requires uppercase AA20, 9..2000 aa, without normalization')
    for field,limit in [('host_species',256),('structure_name',512)]:
        ensure(isinstance(value[field],str) and value[field].strip() and len(value[field])<=limit,
            'INVALID_REQUEST',field+' must be nonempty bounded metadata')
    ensure(value['declared_format'] in ('PDB','CIF','MMCIF'),'INVALID_REQUEST','Declared format must be PDB/CIF/MMCIF')
    selection=value['selection']
    ensure(isinstance(selection,dict) and set(selection)=={'model_index','chain_selector'},'INVALID_REQUEST','Explicit selection fields required')
    ensure(selection['model_index'] is None or type(selection['model_index']) is int and 0<=selection['model_index']<=9999,
        'INVALID_REQUEST','Model index must be null or a bounded nonnegative integer')
    ensure(isinstance(selection['chain_selector'],str) and 1<=len(selection['chain_selector'])<=64,'INVALID_REQUEST','Invalid author chain selector')
    context=value['context_chain_ids']
    ensure(isinstance(context,list) and 1<=len(context)<=64 and all(isinstance(c,str) and 1<=len(c)<=64 for c in context)
        and len(set(context))==len(context),'INVALID_REQUEST','Explicit unique protein context chain IDs are required')
    source=value['source_declaration']
    ensure(isinstance(source,dict) and set(source)=={'kind','note'} and source['kind'] in ('unknown','experimental','predicted')
        and (source['note'] is None or isinstance(source['note'],str) and 0<len(source['note'])<=1024),
        'INVALID_REQUEST','Source declaration requires kind unknown/experimental/predicted and optional note')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=120,'INVALID_REQUEST','Structure execution deadline must be 1..120 seconds')
    return value


def request(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)==FIELDS|{'structure_artifact'},'INVALID_REQUEST','Structure request requires registered input ArtifactRef')
    metadata(encode({k:value[k] for k in FIELDS}))
    ref=value['structure_artifact']
    ensure(isinstance(ref,dict) and set(ref)=={'artifact_id','run_id','job_id','attempt_id','role','media_type','sha256','size_bytes','evidence_kind'},
        'INVALID_REQUEST','Invalid structure ArtifactRef fields')
    local = ref['role']=='input' and ref['evidence_kind']=='LOCAL_INPUT' and ref['job_id'] is ref['attempt_id'] is None
    predicted = ref['role']=='raw' and ref['evidence_kind']=='G0_REAL_OUTPUT' and ref['job_id'] is not None and ref['attempt_id'] is not None
    ensure((local or predicted)
        and type(ref['size_bytes']) is int and 0<ref['size_bytes']<=MAX_STRUCTURE_BYTES,'FORBIDDEN','Structure must be a bounded registered local input')
    return value


def registered_profile():
    dev=HERE.parent
    paths=list(dev.rglob('*.py'))+list(dev.rglob('*.json'))+list((REPO/'src/t01_structure_mapping').glob('*.py'))
    paths += [REPO/'scripts/t01_runtime.py',REPO/'scripts/t01_development_supervisor.py',PROFILE]
    return dict(id='w1-local-structure-analysis-development',version='0.1.0',sha256=sha(encode(dict(
        files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(paths)},base_runtime=base_profile(),image=IMAGE,limits=LIMITS))))


def verify_assets():
    receipt=decode(read_locked(HERE/'sources.json',65536))
    for entry in receipt['files']:
        ensure(sha(read_locked(REPO/entry['path'],1024**2))==entry['sha256'],'HASH_MISMATCH','Pinned structure source changed: '+entry['path'])
    ensure(decode(read_locked(PROFILE))['runtime']['image_id']==IMAGE,'PROFILE_NOT_APPROVED','FreeSASA image/profile differs')
    return dict(files=receipt['files'],archive_sha256=sha(read_locked(PROFILE)))
