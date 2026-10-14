"""Fixed local development registration, separate from scientific qualification."""
import hashlib
from pathlib import Path
import re

from ..common import REPO, decode, encode, ensure, profile as base_profile, sha
from ..files import no_links, read_locked

TOOL = 't01.real.deeptmhmm'
NODE = 'N02'
LIMITS = dict(memory=10*1024**3,cpus=8,cpuset='0-7',pids=512)
IMAGE = 'sha256:7f85781fadf8c89ddbafced691d05006caf6881b06aa5b9bae4bd531393bcd72'
SLOT = 't01p1r-deeptmhmm-development-slot'
PACKAGE = REPO/'var/t01-phase1-real/tool-assets/deeptmhmm-academic-1.0-0a7a6c5d009e'
HERE = Path(__file__).parent
MAX_AA = 1023  # Explicit local resource coverage cap, not a biological/model maximum.


def request(raw):
    value = decode(raw)
    ensure(isinstance(value, dict) and set(value)=={'protein_sequence','user_sequence_id','timeout_seconds'},
           'INVALID_REQUEST','Expected protein_sequence, user_sequence_id and timeout_seconds only')
    seq = value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq),
           'INVALID_REQUEST','Development input requires exact uppercase AA20; no whitespace, X or * substitution')
    ensure(9<=len(seq)<=MAX_AA,'INVALID_REQUEST','Development length must be 9..1023 aa; this is a local coverage/resource cap')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,
           'INVALID_REQUEST','User sequence ID must be bounded metadata')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=900,
           'INVALID_REQUEST','Timeout must be an integer between 1 and 900 seconds')
    return value


def sequence_id(seq):
    return 't01seq_'+sha(seq.encode())


def registered_profile():
    sources={p.name:sha(p.read_bytes()) for p in sorted(HERE.glob('*')) if p.is_file()}
    for name in ['t01_runtime.py','t01_development_supervisor.py']:
        sources[name]=sha((REPO/'scripts'/name).read_bytes())
    return dict(id='w1-deeptmhmm-academic1-local-development',version='0.1.0',
        sha256=sha(encode(dict(sources=sources,base_runtime=base_profile(),image=IMAGE,aa_min=9,aa_max=MAX_AA,
            memory=10*1024**3,cpus=8,max_processes=512,max_wall_seconds=900,parallel_models=1,scientific_consumption=False))))


def asset_receipt():
    return decode(read_locked(HERE/'assets.json',65536))


def verify_assets():
    receipt=asset_receipt()
    for entry in receipt['files']:
        p=no_links(PACKAGE/entry['path'])
        ensure(p.is_file() and p.stat().st_size==entry['bytes'],'ASSET_MISSING','Missing pinned asset: '+entry['path'])
        h=hashlib.sha256()
        with p.open('rb') as stream:
            for block in iter(lambda: stream.read(8*1024*1024),b''): h.update(block)
        ensure(h.hexdigest()==entry['sha256'],'HASH_MISMATCH','Changed pinned asset: '+entry['path'])
    return receipt
