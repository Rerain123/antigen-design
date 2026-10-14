"""Read-only verification of this preparation batch; never claims DeepTMHMM was executed."""
import hashlib
import importlib.util
import json
from pathlib import Path
import zipfile

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(value, message):
    if not value:
        raise ValueError(message)


def verify_files(directory, entries):
    directory = directory.resolve()
    seen = set()
    for row in entries:
        path = (directory/row['path']).resolve()
        require(path.is_relative_to(directory) and path != directory, 'Unsafe manifest path')
        require(path not in seen, 'Duplicate manifest path')
        seen.add(path)
        data = path.read_bytes()
        require(len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],
                'Evidence hash mismatch: '+row['path'])


def verify():
    manifest = read(BATCH/'manifest.json')
    verify_files(BATCH, manifest['files'])
    actual = {p.relative_to(BATCH).as_posix() for p in BATCH.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.name != 'manifest.json'}
    require(actual=={r['path'] for r in manifest['files']}, 'Evidence inventory drift')
    environment = read(BATCH/'environment/environment.json')
    for path, expected in environment['expert_sources_before'].items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected, 'Expert source changed: '+path)
    adoption = ROOT/manifest['user_source']['path']
    require(hashlib.sha256(adoption.read_bytes()).hexdigest()==manifest['user_source']['sha256'], 'User source changed')
    require(read(adoption)['exact_user_reply']=='学术自用', 'Usage scope changed')
    pypi = read(BATCH/'public_sources/pybiolib-pypi.json')
    wheel = next(r for r in pypi['urls'] if r['filename'].endswith('.whl'))
    wheel_path = BATCH/'public_sources'/wheel['filename']
    require(hashlib.sha256(wheel_path.read_bytes()).hexdigest()==wheel['digests']['sha256'], 'SDK differs from PyPI')
    with zipfile.ZipFile(wheel_path) as archive:
        for path in (BATCH/'public_sources/sdk_sources').rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                require(path.read_bytes()==archive.read(path.relative_to(BATCH/'public_sources/sdk_sources').as_posix()), 'SDK extraction changed')
    execution = read(BATCH/'sdk-offline/execution.json')
    require(execution['model_execution']=='NOT_RUN' and execution['production_status']=='NOT_DEPLOYED', 'SDK mistaken for model execution')
    require(execution['result']=='EXPECTED_LOCAL_MODE_REJECTION' and execution['network_mode']=='none', 'Missing offline SDK rejection')
    require(execution['container_state']['ExitCode']==1 and not execution['timed_out'] and not execution['container_state']['OOMKilled'], 'Unexpected SDK failure')
    require(execution['wheel_sha256']==wheel['digests']['sha256'], 'Executed SDK drift')
    require(all(r['exit_code']==0 for r in execution['records'] if r['label'] in ('create','inspect','remove')), 'Probe lifecycle failure')
    stdout = (BATCH/'sdk-offline/start.stdout').read_text()
    detail = next(json.loads(line) for line in stdout.splitlines() if line.startswith('{'))
    require(detail['network_interfaces']==['lo'] and detail['sdk_version']=='1.4.457', 'Runtime evidence differs')
    metadata = read(BATCH/'public_sources/app-metadata.json')
    require(metadata['app_version']['app_uri']=='DTU/DeepTMHMM:1.0.57', 'Advertised app version drift')
    require('forms.cloud.microsoft' in metadata['app_version']['description'], 'Missing official package-request route')
    spec = importlib.util.spec_from_file_location('deeptmhmm_public_audit', BATCH/'audit_sources.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    result = read(BATCH/'source-audit/audit.json')
    require(result['model_execution']=='NOT_RUN' and result['production_status']=='NOT_DEPLOYED', 'Published data mistaken for local run')
    for key, name, width in [('annotation','DeepTMHMM.3line',3),('crossval','DeepTMHMM.crossval.top',4)]:
        rows = audit.records((BATCH/'public_sources'/name).read_text(), width)
        require(result[key]==audit.corpus_summary(rows), 'Corpus audit drift: '+key)
    source_lines = (BATCH/'public_sources/DeepTMHMM.3line').read_bytes().splitlines(keepends=True)
    for row in result['selected_annotation_cases']:
        raw = (BATCH/'source-audit/inputs'/(row['case']+'.3line')).read_bytes()
        require(raw==b''.join(source_lines[row['source_line']-1:row['source_line']+2]), 'Selected source bytes differ')
        parsed = audit.records(raw.decode(), 3)[0]
        require(row['inspection']==audit.inspect_labels(parsed['sequence'], parsed['label_rows'][0]), 'Case inspection drift')
    return {'status':'PASS', 'batch_files':len(manifest['files']),
            'expert_sources_unchanged':len(environment['expert_sources_before']),
            'model_execution':'NOT_RUN', 'production_status':'NOT_DEPLOYED'}


if __name__ == '__main__':
    print(json.dumps(verify()))
