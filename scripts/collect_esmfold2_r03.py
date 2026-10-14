"""Collect completed ESMFold2 r03 artifacts through a user-started read-only Pod."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys

REQUIRED = {'structure.cif', 'metrics.json', 'execution.json', 'result.json',
            'request.json', 'profile.json', 'checkpoint-loading.json'}
LIMIT = 64 * 1024**2


def validate(files, *, expected_request_id='esmfold2-engineering-003'):
    if sum(len(v) for v in files.values()) > LIMIT:
        raise ValueError('Unexpected result size')
    manifest = json.loads(files['manifest.json'])
    seen = set()
    for row in manifest['files']:
        name = row['path']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or name in seen or name == 'manifest.json':
            raise ValueError('Unsafe/duplicate result path')
        seen.add(name)
        raw = files[name]
        if len(raw) != row['size_bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Artifact integrity mismatch: ' + name)
    if seen != REQUIRED or set(files) != REQUIRED | {'manifest.json'}:
        raise ValueError('Unexpected result file set')
    result = json.loads(files['result.json'])
    if result['request_id'] != expected_request_id or result['status'] != 'predicted_engineering_unreviewed':
        raise ValueError('Wrong result identity/status')
    if result['scientific_gate'] != 'CLOSED' or result['usable_for_pipeline'] is not False:
        raise ValueError('Result unexpectedly enabled scientific use')
    if result['structure']['sha256'] != hashlib.sha256(files['structure.cif']).hexdigest():
        raise ValueError('Structure reference mismatch')
    return result


def remote():
    root = Path('/runs/engineering-r03')
    paths = list(root.rglob('*'))
    if any(p.is_symlink() for p in paths):
        raise ValueError('Symlink in result tree')
    paths = [p for p in paths if p.is_file()]
    if sum(p.stat().st_size for p in paths) > LIMIT:
        raise ValueError('Unexpected result size')
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in paths}
    validate(files)
    print(json.dumps({n: base64.b64encode(raw).decode() for n, raw in files.items()}))


def main():
    if sys.argv[1:] == ['--remote']:
        remote()
        return
    if sys.argv[1:]:
        raise SystemExit('Run without arguments')
    project = Path(__file__).resolve().parents[1]
    args = ['kubectl', '--kubeconfig', str(project / '.tmp/himat.kubeconfig'), '-n', 'him-ws']
    job = json.loads(subprocess.check_output(args + ['get', 'job', 'antigen-esmfold2-validation-r03', '-o', 'json']))
    if not any(c['type'] == 'Complete' and c['status'] == 'True' for c in job['status'].get('conditions', [])):
        raise ValueError('r03 Job is not Complete')
    print('READING_VERIFIED_R03_ARTIFACTS', flush=True)
    reply = subprocess.run(args + ['exec', '-i', 'antigen-esmfold2-results-r03', '--', 'python', '-B', '-', '--remote'],
                           input=Path(__file__).read_bytes(), stdout=subprocess.PIPE, check=True)
    files = {n: base64.b64decode(v, validate=True) for n, v in json.loads(reply.stdout).items()}
    result = validate(files)
    out = project / 'discovery/t01-phase1-real/esmfold2-target-20260917/r03'
    for name, raw in files.items():
        path = out / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('Refusing to overwrite different local evidence: ' + name)
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in files.items():
        (out / name).write_bytes(raw)
    # Preserve the cluster completion and log evidence separately from artifact manifest.
    for name, raw in [('cluster-job.json', json.dumps(job, indent=2).encode()),
                      ('cluster.log', subprocess.check_output(args + ['logs', 'job/antigen-esmfold2-validation-r03']))]:
        path = out / name
        if not path.exists():
            path.write_bytes(raw)
    print('ESMFOLD2_R03_ARTIFACTS_VERIFIED', len(files), sum(map(len, files.values())), flush=True)
    print('METRICS', json.dumps(result['metrics']), flush=True)
    print('SAVED', out, flush=True)


if __name__ == '__main__':
    main()
