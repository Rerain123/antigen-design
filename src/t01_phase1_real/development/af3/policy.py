from pathlib import Path
import re

from ..esmfold2.primitives import decode, encode, ensure, sha


TOOL = 't01.real.af3'
NODE = 'N01'
HERE = Path(__file__).parent
IMAGE = 'sha256:35db7c1feb3368a7c72b0d1f60b295ed1473b562b61526db265fc0c446fd4373'
SLOT = 't01p1r-af3-development-slot'
# User input domain (<1000 aa); the original 76 aa was an acceptance example,
# not an AF3 model limit. Admission is distinct from measured native capacity.
MAX_AA = 999

# AF3's data pipeline must receive explicit HMMER paths. Relying on PATH
# allowed the r07 resident task to pass ``None`` into jackhmmer even though
# the fixed image contained HMMER. Keep this mapping in the registered
# policy so the worker and standardizer cannot drift apart.
HMMER_BINARIES = {
    'jackhmmer': '/hmmer/bin/jackhmmer',
    'nhmmer': '/hmmer/bin/nhmmer',
    'hmmalign': '/hmmer/bin/hmmalign',
    'hmmsearch': '/hmmer/bin/hmmsearch',
    'hmmbuild': '/hmmer/bin/hmmbuild',
}


def hmmer_arguments(paths=None):
    values = HMMER_BINARIES if paths is None else paths
    return tuple('--' + name + '_binary_path=' + path
                 for name, path in values.items())


def profile():
    return decode((HERE / 'profile.json').read_bytes())


def request(raw):
    body = decode(raw)
    ensure(isinstance(body, dict) and set(body) - {'mode', 'msa_source'} == {
        'protein_sequence', 'user_sequence_id', 'host_species', 'seed', 'timeout_seconds'},
        'INVALID_REQUEST', 'Exact AF3 request fields required')
    ensure(isinstance(body['protein_sequence'], str)
           and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', body['protein_sequence'])
           and 9 <= len(body['protein_sequence']) <= MAX_AA,
           'INVALID_REQUEST', 'AF3 engineering admission is bounded to 9..999 AA20 residues')
    for key in ('user_sequence_id', 'host_species'):
        ensure(isinstance(body[key], str) and 0 < len(body[key].strip()) <= 128,
               'INVALID_REQUEST', 'Explicit bounded sequence label and host required')
    ensure(type(body['seed']) is int and body['seed'] == 1,
           'INVALID_REQUEST', 'Current verified AF3 profile requires seed 1')
    ensure(type(body['timeout_seconds']) is int and 1 <= body['timeout_seconds'] <= 7200,
           'INVALID_REQUEST', 'Deadline must be 1..7200 seconds')
    if 'mode' in body:
        ensure(body['mode'] == 'msa_only' and 'msa_source' not in body,
               'INVALID_REQUEST', 'Only independent WT MSA preparation is supported')
    if 'msa_source' in body:
        src = body['msa_source']
        ensure(isinstance(src, dict) and set(src) == {'job_id', 'artifact'}
               and isinstance(src['job_id'], str) and isinstance(src['artifact'], dict)
               and src['artifact'].get('job_id') == src['job_id'] and src['artifact'].get('role') == 'result',
               'INVALID_REQUEST', 'Explicit registered WT MSA source required')
    return body


def registered_profile():
    paths = list(HERE.glob('*.py')) + list(HERE.glob('*.json'))
    paths.append(HERE.parents[1] / 'gpu_device.py')
    return dict(id='af3-v3.0.2-resident-r01', version='0.1.0', sha256=sha(encode({
        path.name: sha(path.read_bytes()) for path in sorted(paths)})))


def verify_assets():
    value = profile()
    ensure(value['scientific_gate'] == 'CLOSED' and value['source_image_id'] == IMAGE,
           'PROFILE_NOT_APPROVED', 'AF3 source identity or science gate differs')
    return {'model_and_database_verification': 'REQUIRED_IN_WORKER',
            'profile_sha256': sha((HERE / 'profile.json').read_bytes())}


def native_request(body, binding):
    value = profile()
    result = dict(contract_version='t01.structure-worker/0.1', request_id=binding['job_id'],
                engine='alphafold3', asset_profile_id=value['id'],
                inputs=dict(sequence_id='seq-' + sha(body['protein_sequence'].encode())[:16],
                            sequence=body['protein_sequence'], host_species=body['host_species'], chain_id='A'),
                parameters=dict(seed=body['seed'], num_samples=value['inference']['num_diffusion_samples'],
                                msa_mode='local', max_template_date=value['inference']['max_template_date'],
                                timeout_seconds=body['timeout_seconds']))
    if 'mode' in body: result['parameters']['mode'] = body['mode']
    if 'msa_source' in body:
        result['parameters'].update(msa_mode='wild_type_reuse', msa_source=body['msa_source'])
    return result
