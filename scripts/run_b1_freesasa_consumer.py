"""Run prepared B1 cases in the pre-existing pinned FreeSASA image, strictly offline."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import uuid

from check_b1_freesasa_consumer import BATCH, SOURCES, ROOT, fingerprint, read, write_json
from prepare_b1_freesasa import PROFILE
from t01_structure_mapping.probe import sha


def run(batch, output, docker_config=None):
    batch, output = batch.resolve(), output.resolve()
    if not batch.is_relative_to(ROOT) or not output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Use an existing project case batch and a new project output directory')
    profile = read(PROFILE)
    image = profile['runtime']['image_id']
    docker = ['docker'] + (['--config', str(docker_config.resolve())] if docker_config else [])
    docker += ['--host', 'npipe:////./pipe/dockerDesktopLinuxEngine']
    inspection = subprocess.run(docker + ['image', 'inspect', '--format', '{{json .Id}} {{json .Os}} {{json .Architecture}}', image],
                                capture_output=True, timeout=20, check=True)
    assert inspection.stdout.decode().strip() == f'"{image}" "linux" "amd64"'
    output.mkdir(parents=True)
    (output / 'image-inspect.stdout').write_bytes(inspection.stdout)
    (output / 'image-inspect.stderr').write_bytes(inspection.stderr)
    name = 't01-b1-sasa-' + uuid.uuid4().hex[:12]
    command = docker + ['run', '--rm', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--cpus', '2', '--memory', '1g', '--pids-limit', '64',
        '--mount', f'type=bind,source={batch},target=/cases,readonly',
        '--mount', f'type=bind,source={ROOT / "src/t01_structure_mapping"},target=/code/src/t01_structure_mapping,readonly',
        '--mount', f'type=bind,source={ROOT / "scripts/run_b1_freesasa_worker.py"},target=/worker.py,readonly',
        '--mount', f'type=bind,source={PROFILE},target=/profile.json,readonly',
        '--mount', f'type=bind,source={output},target=/out', image, 'python', '-B', '/worker.py']
    sources = [fingerprint(ROOT / p) for p in SOURCES] + [fingerprint(PROFILE)]
    record = dict(command=command, started_at=datetime.now(timezone.utc).isoformat(), image_id=image,
        sources=sources, plan_sha256=sha((batch / 'expected_cases.json').read_bytes()), production_status='NOT_DEPLOYED')
    # Record intent before starting a process; even interrupted runs retain their provenance.
    write_json(output / 'invocation.json', record)
    timer, timed_out = time.perf_counter(), False
    try:
        result = subprocess.run(command, capture_output=True, timeout=60)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        cleanup = subprocess.run(docker + ['rm', '--force', name], capture_output=True, timeout=20)
        (output / 'timeout-cleanup.stdout').write_bytes(cleanup.stdout)
        (output / 'timeout-cleanup.stderr').write_bytes(cleanup.stderr)
    (output / 'stdout.txt').write_bytes(stdout)
    (output / 'stderr.txt').write_bytes(stderr)
    write_json(output / 'execution.json', dict(record, elapsed_seconds=time.perf_counter() - timer, exit_code=code, timed_out=timed_out))
    print(stdout.decode(errors='replace'), end='')
    print(stderr.decode(errors='replace'), end='')
    return code if code is not None else 124


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=BATCH)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--docker-config', type=Path)
    args = parser.parse_args()
    raise SystemExit(run(args.batch, args.output_dir, args.docker_config))
