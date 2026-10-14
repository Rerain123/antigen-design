from pathlib import Path
import re
from .primitives import decode, encode, ensure, sha

TOOL = 't01.real.esmfold2'
NODE = 'N01'
HERE = Path(__file__).parent
IMAGE = 'sha256:372545ebe3469a3d32269c27033d19624d713d75ca162dbe6fff5dafed44f77f'
SLOT = 't01p1r-esmfold2-development-slot'
# Resource-bounded engineering admission for HiMat sequence runs. Lengths above
# the previously observed 393-residue capacity case remain unverified in practice.
MAX_AA = 999


def profile():
    return decode((HERE / 'profile.json').read_bytes())


def request(raw):
    b = decode(raw)
    ensure(isinstance(b, dict) and set(b) == {'protein_sequence', 'user_sequence_id', 'host_species', 'seed', 'timeout_seconds'},
           'INVALID_REQUEST', 'Exact ESMFold2 request fields required')
    ensure(isinstance(b['protein_sequence'], str)
           and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', b['protein_sequence'])
           and 9 <= len(b['protein_sequence']) <= MAX_AA,
           'INVALID_REQUEST', 'ESMFold2 engineering admission is bounded to 9..999 AA20 residues')
    for k in ('user_sequence_id', 'host_species'):
        ensure(isinstance(b[k], str) and 0 < len(b[k].strip()) <= 128, 'INVALID_REQUEST', 'Explicit sequence label and host required')
    ensure(type(b['seed']) is int and b['seed'] == 1, 'INVALID_REQUEST', 'Current verified ESMFold2 profile requires seed 1')
    ensure(type(b['timeout_seconds']) is int and 1 <= b['timeout_seconds'] <= 7200, 'INVALID_REQUEST', 'Deadline must be 1..7200 seconds')
    return b


def registered_profile():
    paths = list(HERE.glob('*.py')) + list(HERE.glob('*.json'))
    paths.append(HERE.parents[1] / 'gpu_device.py')
    return dict(id='esmfold2-standard-resident-r01', version='0.1.0', sha256=sha(encode({
        p.name: sha(p.read_bytes()) for p in sorted(paths)})))


def verify_assets():
    ensure(profile()['scientific_gate'] == 'CLOSED', 'PROFILE_NOT_APPROVED', 'Science gate must remain closed')
    return {'model_assets_verification': 'REQUIRED_IN_WORKER', 'profile_sha256': sha((HERE / 'profile.json').read_bytes())}


def native_request(body, binding):
    return dict(contract_version='t01.structure-worker/0.1', request_id=binding['job_id'],
                engine='esmfold2', asset_profile_id=profile()['id'],
                inputs=dict(sequence_id='seq-' + sha(body['protein_sequence'].encode())[:16],
                            sequence=body['protein_sequence'], host_species=body['host_species'], chain_id='A'),
                parameters=dict(seed=body['seed'], num_samples=1, msa_mode='none', prepared_input=None,
                                timeout_seconds=body['timeout_seconds']))
