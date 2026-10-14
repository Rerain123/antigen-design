"""Fixed BepiPred 3.0 local CLI profile, independent of scientific acceptance."""
import hashlib
from pathlib import Path
import re

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked

TOOL='t01.real.bepipred'
NODE='N04'
IMAGE='sha256:e1aff495e254ca4da513286f4ada0e1e0a071a2ffd9e0bc8ae3d2e6c91384149'
SLOT='t01p1r-bepipred-development-slot'
LIMITS=dict(memory=10*1024**3,cpus=8,cpuset='0-7',pids=512)
MAX_AA=1022
HERE=Path(__file__).parent
PACKAGE=REPO/'var/t01-phase1-real/tool-assets/bepipred-3.0-98bedf2471e0'
MODELS=REPO/'var/t01-phase1-real/tool-assets/bepipred-esm2-650m'
PARAMETERS=dict(pred='vt_pred',add_seq_len=False,threshold=0.1512,top_fraction=0.2,rolling_window=9,plot_linear_epitope_scores=False)


def request(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)=={'protein_sequence','user_sequence_id','timeout_seconds'},'INVALID_REQUEST','Exact BepiPred sequence/alias/timeout fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and 9<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','BepiPred local development requires exact uppercase AA20, 9..1022 aa; no normalization')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,'INVALID_REQUEST','User sequence ID must be bounded metadata')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=900,'INVALID_REQUEST','Execution deadline must be 1..900 seconds')
    return value


def registered_profile():
    paths=[p for p in HERE.parent.rglob('*') if p.suffix in ('.py','.json')]
    paths += [REPO/'scripts/t01_runtime.py',REPO/'scripts/t01_development_supervisor.py']
    return dict(id='w2-bepipred3-cli-local-development',version='0.1.0',sha256=sha(encode(dict(
        files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(paths)},image=IMAGE,base_runtime=base_profile(),
        limits=LIMITS,aa_min=9,aa_max=MAX_AA,parameters=PARAMETERS,scientific_consumption=False))))


def verify_assets():
    receipt=decode(read_locked(HERE/'assets.json',131072))
    for entry in receipt['files']:
        path=no_links(REPO/entry['path'])
        ensure(path.is_file() and path.stat().st_size==entry['bytes'],'ASSET_MISSING','Missing BepiPred asset: '+entry['path'])
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            while block:=stream.read(8*1024**2):digest.update(block)
        ensure(digest.hexdigest()==entry['sha256'],'HASH_MISMATCH','Changed BepiPred asset: '+entry['path'])
    return receipt
