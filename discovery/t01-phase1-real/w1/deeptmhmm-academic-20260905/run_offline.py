"""One bounded raw execution; preserves attempts and never downloads or edits models."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
DOCKER = ['docker', '--host', 'npipe:////./pipe/dockerDesktopLinuxEngine']


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def check_assets():
    receipt = json.loads((BATCH/'package_receipt.json').read_text())
    root = ROOT/receipt['asset_root']
    for item in receipt['files']:
        path = root/item['path']
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Changed package asset: '+item['path'])
    return root, len(receipt['files'])


def run(case):
    source = BATCH/'inputs'/f'{case}.fasta'
    if not source.is_file():
        raise ValueError('Undeclared input')
    target = BATCH/'runs'/case
    if target.exists():
        raise FileExistsError('Preserve existing run; declare a new case/attempt')
    asset_root, checked = check_assets()
    build = json.loads((BATCH/'environment/build.json').read_text())
    if build['exit_code'] != 0:
        raise ValueError('Environment build failed')
    target.mkdir(parents=True)
    output = target/'output'
    output.mkdir()
    name = 't01-dtm-academic-20260905-'+case
    command = DOCKER+['create', '--pull', 'never', '--name', name,
        '--network', 'none', '--read-only', '--cap-drop', 'ALL',
        '--security-opt', 'no-new-privileges', '--pids-limit', '512',
        '--memory', '10g', '--memory-swap', '10g', '--cpus', '8', '--cpuset-cpus', '0-7',
        '--tmpfs', '/tmp:rw,noexec,nosuid,size=512m',
        '--env', 'CUDA_VISIBLE_DEVICES=-1', '--env', 'PYTHONUNBUFFERED=1',
        '--mount', f'type=bind,source={asset_root},target=/app,readonly',
        '--mount', f'type=bind,source={source},target=/input.fasta,readonly',
        '--mount', f'type=bind,source={BATCH/"container_probe.py"},target=/probe.py,readonly',
        '--mount', f'type=bind,source={output},target=/out',
        '--workdir', '/app', '--entrypoint', 'python', build['image_id'], '/probe.py']
    record = dict(case=case, command=command, assets_verified_before=checked,
                  input_sha256=digest(source), production_status='NOT_DEPLOYED')
    (target/'command.json').write_text(json.dumps(record, indent=2))
    created = subprocess.run(command, capture_output=True, text=True)
    (target/'create.stdout').write_text(created.stdout)
    (target/'create.stderr').write_text(created.stderr)
    if created.returncode:
        raise RuntimeError(created.stderr)
    container_id = created.stdout.strip()
    record['container_id'] = container_id
    started = time.monotonic()
    try:
        with (target/'stdout.txt').open('wb') as out, (target/'stderr.txt').open('wb') as err:
            try:
                execution = subprocess.run(DOCKER+['start', '--attach', container_id], stdout=out, stderr=err, timeout=900)
                record['attach_exit_code'] = execution.returncode
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                subprocess.run(DOCKER+['kill', container_id], capture_output=True, check=True)
        inspected = subprocess.run(DOCKER+['inspect', container_id], capture_output=True, text=True, check=True)
        (target/'container_inspect.json').write_text(inspected.stdout)
        state = json.loads(inspected.stdout)[0]['State']
        record.update(container_exit_code=state['ExitCode'], oom_killed=state['OOMKilled'])
    finally:
        subprocess.run(DOCKER+['rm', '-f', container_id], capture_output=True, check=True)
        record['elapsed_seconds'] = time.monotonic()-started
        _, record['assets_verified_after'] = check_assets()
        record['artifacts'] = [{'path': p.relative_to(output).as_posix(), 'bytes': p.stat().st_size, 'sha256': digest(p)}
                               for p in sorted(output.rglob('*')) if p.is_file()]
        (target/'execution.json').write_text(json.dumps(record, indent=2))
    print(json.dumps({k: v for k, v in record.items() if k not in ('artifacts', 'command')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True, choices=['short', 'coverage', 'empty', 'x-residue'])
    run(parser.parse_args().case)
