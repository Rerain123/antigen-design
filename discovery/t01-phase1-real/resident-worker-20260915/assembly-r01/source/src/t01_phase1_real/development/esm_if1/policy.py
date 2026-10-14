"""Pinned ESM-IF1 GPU scoring over registered N11 records and WT backbone."""
from pathlib import Path
import re
from ...common import REPO,decode,encode,ensure,sha,profile as base_profile
from ...files import read_locked,no_links
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL='t01.real.esm_if1'
NODE='N12'
HERE=Path(__file__).parent
PACKAGE=REPO/'var/t01-phase1-real/tool-assets/esm-if1-2b369911bb5b'
COMMIT='2b369911bb5b4b0dda914521b9475cad1656b2ac'
MODEL='esm_if1_gvp4_t16_142M_UR50'
IMAGE='sha256:926d4619df9759cd2417dcc9056b7bd648dca1d2adf15631aaad2e84a88d39cc'
SLOT='t01p1r-esm-if1-development-slot'
LIMITS=dict(memory=6*1024**3,cpus=2,cpuset='0-1',pids=128)
PARAMETERS=dict(scoring='official_get_sequence_loss_full_target_mean',backbone_context='all_protein_chains',
    padding_length=10,precision='float32',eval_mode=True,seed=17,tf32=False)
AUTHORITY_ROOT=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'


def artifact(ref):
    ensure(isinstance(ref,dict) and set(ref)==ARTIFACT_FIELDS and ref['role']=='result' and ref['media_type']=='application/json'
        and ref['evidence_kind']=='G0_REAL_OUTPUT' and isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256'])
        and type(ref['size_bytes']) is int and 0<ref['size_bytes']<=32*1024**2,'INVALID_REQUEST','Exact registered result ArtifactRef required')


def request(raw):
    body=decode(raw)
    ensure(isinstance(body,dict) and set(body)=={'protein_sequence','user_sequence_id','structure_artifact','n11_artifact',
        'sample_numbers','baseline_artifact','timeout_seconds'},'INVALID_REQUEST','Exact N12 engineering request required')
    ensure(isinstance(body['protein_sequence'],str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,1000}',body['protein_sequence']),
        'INVALID_REQUEST','Exact WT AA20 sequence 1..1000 required')
    ensure(isinstance(body['user_sequence_id'],str) and 0<len(body['user_sequence_id'])<=512,'INVALID_REQUEST','Bounded input label required')
    for key in ('structure_artifact','n11_artifact'):artifact(body[key])
    if body['baseline_artifact'] is not None:artifact(body['baseline_artifact'])
    selected=body['sample_numbers'];ensure(isinstance(selected,list) and len(selected)<=24
        and all(type(n) is int and 1<=n<=24 for n in selected) and len(selected)==len(set(selected)),
        'INVALID_REQUEST','Unique original N11 sample numbers required; empty list explicitly means no scoring')
    ensure(type(body['timeout_seconds']) is int and 1<=body['timeout_seconds']<=900,'INVALID_REQUEST','Deadline 1..900 seconds required')
    return body


def sequence_id(seq):return 't01if1_'+sha(seq.encode())[:16]


def registered_rules():
    return dict(id='w5-n12-esm-if1-relative-r35-engineering',version='0.1.0',sha256=sha(encode(dict(
        sources={name:sha((AUTHORITY_ROOT/name).read_bytes()) for name in ('ToolSpec_C18_ESM-IF1_v10.5.md','AgentA_SOP_v10.5_20260902.md')},
        rules=sha((HERE/'rules.py').read_bytes()),thresholds=[.10,.15,.20],science_enabled=False))))


def registered_profile():
    paths=[*HERE.glob('*.py'),*HERE.glob('*.json'),*[HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py','docker.py','supervisor.py')],
        *list((HERE.parent/'proteinmpnn').glob('*.py')),*list((HERE.parent/'proteinmpnn').glob('*.json')),
        *list((REPO/'src/t01_structure_mapping').glob('*.py')),REPO/'requirements/esm_if1.Dockerfile']
    return dict(id='w5-n12-esm-if1-gpu-local-development',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},image=IMAGE,parameters=PARAMETERS,
        limits=LIMITS,rules=registered_rules(),base=base_profile()))))


def verify_assets():
    receipt=decode(read_locked(HERE/'assets.json',262144))
    ensure(receipt['commit']==COMMIT and receipt['image']==IMAGE and receipt['model']==MODEL,'ASSET_MISSING','Pinned ESM-IF1 registry differs')
    for item in receipt['files']:
        path=no_links(REPO/item['path'])
        ensure(path.is_file() and path.stat().st_size==item['bytes'],'ASSET_MISSING','Missing ESM-IF1 asset: '+item['path'])
        # Weights are larger than ordinary output artifacts; stream without relaxing artifact read limits.
        import hashlib
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(8*1024**2),b''):digest.update(chunk)
        ensure(digest.hexdigest()==item['sha256'],'HASH_MISMATCH','Changed ESM-IF1 asset: '+item['path'])
    return receipt
