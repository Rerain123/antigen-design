"""Run only the official SDK's local-mode rejection in an isolated container; no model job."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
BASE = 'python@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84'
WHEEL = BATCH/'public_sources/pybiolib-1.4.457-py3-none-any.whl'
DOCKER = ['docker', '--host', 'npipe:////./pipe/dockerDesktopLinuxEngine']
INNER = r'''
import importlib.metadata, json, os, subprocess, sys
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
                '--disable-pip-version-check', '--target', '/tmp/sdk', '/input/sdk.whl'], check=True)
sys.path.insert(0, '/tmp/sdk')
print(json.dumps({'sdk_version':importlib.metadata.version('pybiolib'),
                  'network_interfaces':os.listdir('/sys/class/net'),
                  'operation':'SDK_LOCAL_MODE_NEGATIVE_PROBE', 'model_execution':'NOT_RUN'}), flush=True)
import biolib
sys.argv = ['biolib', 'run', '--local', 'DTU/DeepTMHMM:1.0.57']
biolib.call_cli()
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise SystemExit('Use a new output directory within this project')
    metadata = json.loads((BATCH/'public_sources/pybiolib-pypi.json').read_text())
    asset = next(row for row in metadata['urls'] if row['filename'] == WHEEL.name)
    digest = hashlib.sha256(WHEEL.read_bytes()).hexdigest()
    if digest != asset['digests']['sha256']:
        raise SystemExit('SDK wheel does not match PyPI')
    output.mkdir(parents=True)
    records = []

    def run(label, args, timeout=60):
        started = time.monotonic()
        result = subprocess.run(DOCKER+args, capture_output=True, timeout=timeout)
        (output/(label+'.stdout')).write_bytes(result.stdout)
        (output/(label+'.stderr')).write_bytes(result.stderr)
        records.append({'label':label, 'command':DOCKER+args, 'exit_code':result.returncode,
                        'elapsed_seconds':time.monotonic()-started})
        return result

    image = run('image', ['image', 'inspect', '--format', '{{json .Id}}', BASE])
    if image.returncode:
        raise SystemExit('Pinned base image unavailable; see raw image probe')
    name = 't01-w1-deeptmhmm-sdk-'+uuid.uuid4().hex[:12]
    # Bind just the wheel, with its original valid wheel basename; no project inputs or credentials.
    inner = INNER.replace('/input/sdk.whl', '/input/'+WHEEL.name)
    create = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
              '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', '2',
              '--memory', '1g', '--pids-limit', '128', '--tmpfs', '/tmp:rw,size=536870912',
              '--env', 'HOME=/tmp', '--mount', f'type=bind,source={WHEEL},target=/input/{WHEEL.name},readonly',
              '--entrypoint', 'python', BASE, '-u', '-c', inner]
    created = run('create', create)
    if created.returncode:
        raise SystemExit('Cannot create isolated SDK probe; see raw create error')
    container_id = created.stdout.decode().strip()
    timed_out = False
    state = None
    try:
        try:
            run('start', ['start', '--attach', container_id], timeout=60)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            (output/'start.stdout').write_bytes(error.stdout or b'')
            (output/'start.stderr').write_bytes(error.stderr or b'')
            records.append({'label':'start', 'command':DOCKER+['start','--attach',container_id],
                            'exit_code':None, 'timed_out':True})
            run('kill', ['kill', container_id])
        inspect = run('inspect', ['inspect', '--format',
            '{{json .State}}\n{{json .HostConfig.NetworkMode}}\n{{json .Image}}', container_id])
        if inspect.returncode == 0:
            parts = inspect.stdout.decode().splitlines()
            state = json.loads(parts[0])
            network = json.loads(parts[1])
            image_id = json.loads(parts[2])
    finally:
        run('remove', ['rm', '--force', container_id])
    stderr = (output/'start.stderr').read_text(errors='replace')
    expected = bool(state and state['ExitCode'] == 1 and not state['OOMKilled'] and not timed_out
                    and network == 'none' and 'with --local is no longer supported' in stderr)
    report = {'recorded_at':datetime.now(timezone.utc).isoformat(), 'records':records,
              'scope':'LOCAL_DEVELOPMENT_SDK_NEGATIVE_PROBE', 'image_id':json.loads(image.stdout),
              'wheel_sha256':digest, 'network_mode':network if state else None,
              'container_state':state, 'timed_out':timed_out,
              'result':'EXPECTED_LOCAL_MODE_REJECTION' if expected else 'UNEXPECTED_RESULT',
              'model_execution':'NOT_RUN', 'production_status':'NOT_DEPLOYED'}
    (output/'execution.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['result','model_execution','network_mode','timed_out']}))
    return 0 if expected else 1


if __name__ == '__main__':
    raise SystemExit(main())
