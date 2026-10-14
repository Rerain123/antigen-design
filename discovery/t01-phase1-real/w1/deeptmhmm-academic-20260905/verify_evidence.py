"""Read-only execution evidence verification; optional full local asset hashes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def verify_files(root, entries):
    root = root.resolve()
    seen = set()
    for item in entries:
        path = (root/item['path']).resolve()
        require(path.is_relative_to(root) and path != root, 'Unsafe manifest path')
        require(path not in seen, 'Duplicate manifest entry')
        seen.add(path)
        require(path.stat().st_size == item['bytes'] and digest(path) == item['sha256'], 'Evidence hash mismatch: '+item['path'])


def verify(assets=False, manifest=None):
    if manifest is None:
        manifest = read(BATCH/'manifest.json')
    verify_files(BATCH, manifest['files'])
    actual = {p.relative_to(BATCH).as_posix() for p in BATCH.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.name != 'manifest.json'}
    require(actual == {item['path'] for item in manifest['files']}, 'Evidence inventory drift')
    receipt = read(BATCH/'package_receipt.json')
    for path, expected in receipt['expert_sources_before'].items():
        require(digest(ROOT/path) == expected, 'Expert source changed: '+path)
    verify_files(ROOT, [manifest['usage_source']])
    require(read(ROOT/receipt['usage_source'])['exact_user_reply'] == '学术自用', 'Usage scope drift')
    source_files = [item for item in receipt['files'] if not item['path'].endswith(('.pt', '.model'))]
    verify_files(BATCH/'package_sources', source_files)
    if assets:
        verify_files(ROOT/receipt['asset_root'], receipt['files'])
    build = read(BATCH/'environment/build.json')
    require(build['exit_code'] == 0, 'Failed environment build')
    method = read(BATCH/'method_summary.json')
    require(method['tool_version'] == '1.0 - Academic Version' and method['image_id'] == build['image_id'], 'Candidate identity drift')
    require(method['archive_sha256'] == receipt['archive_sha256'], 'Package identity mismatch')
    expected_assets = {item['path']: item['sha256'] for item in receipt['files'] if item['path'].endswith(('.pt', '.model'))}
    require(method['model_assets_sha256'] == expected_assets and len(expected_assets) == 8, 'Model asset identity mismatch')
    for case in ('short', 'coverage', 'empty', 'x-residue'):
        folder = BATCH/'runs'/case
        execution = read(folder/'execution.json')
        runtime = read(folder/'output/runtime.json')
        inspected = read(folder/'container_inspect.json')[0]
        require(execution['input_sha256'] == digest(BATCH/'inputs'/f'{case}.fasta'), 'Executed input differs')
        require(execution['assets_verified_before'] == execution['assets_verified_after'] == 41, 'Missing package integrity check')
        require(execution['production_status'] == 'NOT_DEPLOYED' and not execution.get('timed_out'), 'Wrong execution boundary')
        require(runtime['network_interfaces'] == [[1, 'lo']] and not runtime['cuda_available'], 'CPU/offline runtime missing')
        require(runtime['packages'] == method['runtime_packages'], 'Dependency version drift')
        require(inspected['Config']['Image'] == build['image_id'], 'Wrong container image')
        config = inspected['HostConfig']
        require(config['NetworkMode'] == 'none' and config['ReadonlyRootfs'], 'Container isolation drift')
        require(config['Memory'] == config['MemorySwap'] == 10*1024**3 and config['NanoCpus'] == 8*10**9, 'Resource limits differ')
        mounts = inspected['Mounts']
        require({m['Destination'] for m in mounts} == {'/app', '/input.fasta', '/probe.py', '/out'}, 'Unexpected mount')
        require(set(config['Tmpfs']) == {'/tmp'}, 'Unexpected temporary filesystem')
        require(all(not m['RW'] for m in mounts if m['Destination'] in {'/app', '/input.fasta', '/probe.py'}), 'Input/source writable')
        require(not inspected['State']['OOMKilled'] and inspected['State']['ExitCode'] == (1 if case == 'empty' else 0), 'Unexpected process outcome')
        verify_files(folder/'output', execution['artifacts'])
    spec = importlib.util.spec_from_file_location('academic_raw_audit', BATCH/'audit_raw.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.audit() == read(BATCH/'raw_audit.json'), 'Raw interpretation drift')
    return dict(status='PASS', batch_files=len(manifest['files']), expert_sources_unchanged=len(receipt['expert_sources_before']),
                local_assets_verified=len(receipt['files']) if assets else 'NOT_REQUESTED',
                model_execution='EXECUTED_OFFLINE_CPU', production_status='NOT_DEPLOYED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', action='store_true')
    print(json.dumps(verify(parser.parse_args().assets)))
