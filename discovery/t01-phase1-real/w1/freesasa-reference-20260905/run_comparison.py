"""Run the numerical study in the existing, pinned local Docker image; never overwrite evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

BATCH = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    root = BATCH.parents[3]
    if not output.is_relative_to(root):
        raise SystemExit('Output must be a new directory inside this project')
    endpoint = subprocess.check_output(['docker', 'context', 'inspect', '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if endpoint != 'npipe:////./pipe/dockerDesktopLinuxEngine':
        raise SystemExit('Expected the inspected local Docker Desktop engine')
    image_id = json.loads((BATCH.parent/'freesasa-s09-20260905/environment/docker.json').read_text())['image_id']
    inspected = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image_id], text=True))[0]
    assert inspected['Id'] == image_id and inspected['Os'] == 'linux' and inspected['Architecture'] == 'amd64'
    output.mkdir(exist_ok=False)
    name = 't01-freesasa-reference-' + uuid.uuid4().hex[:12]
    command = ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only', '--cap-drop', 'ALL',
               '--security-opt', 'no-new-privileges', '--cpus', '2', '--memory', '1g', '--pids-limit', '64',
               '--mount', f'type=bind,source={BATCH / "inputs"},target=/input,readonly',
               '--mount', f'type=bind,source={BATCH / "compare_reference.py"},target=/compare_reference.py,readonly',
               '--mount', f'type=bind,source={BATCH / "reference_spec.json"},target=/reference_spec.json,readonly',
               '--mount', f'type=bind,source={output},target=/out', image_id, 'python', '-B', '/compare_reference.py',
               '--input', '/input/1UBQ.pdb', '--reference-spec', '/reference_spec.json', '--output-dir', '/out/result']
    start = datetime.now(timezone.utc).isoformat(); timer = time.perf_counter()
    timed_out = False
    try:
        process = subprocess.run(command, capture_output=True, timeout=240)
        stdout, stderr, code = process.stdout, process.stderr, process.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20)
    (output/'stdout.txt').write_bytes(stdout); (output/'stderr.txt').write_bytes(stderr)
    record = {'command':command, 'docker_endpoint':endpoint, 'image_id':image_id, 'started_at':start,
              'finished_at':datetime.now(timezone.utc).isoformat(), 'elapsed_seconds':time.perf_counter()-timer,
              'exit_code':code, 'timed_out':timed_out, 'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scientific_approval':None, 'production_status':'NOT_DEPLOYED'}
    (output/'execution.json').write_text(json.dumps(record, indent=2)+'\n')
    print(stdout.decode(errors='replace')); print(stderr.decode(errors='replace'))
    print(json.dumps({'exit_code':code, 'timed_out':timed_out}))
    raise SystemExit(code if code is not None else 124)


if __name__ == '__main__':
    main()
