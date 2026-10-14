"""Bridge the existing business Runtime to statically registered resident workers."""
import os
from pathlib import Path

from .common import RuntimeFault, TERMINAL, decode, encode, ensure, sha
from .files import read_locked, within
from .resident_process import Command, prepare, cancel, inventory, verify_inputs, safe_path, encoded


def enabled():
    return bool(os.environ.get('T01_RESIDENT_CONFIG_FILE'))


def configuration():
    path = Path(os.environ['T01_RESIDENT_CONFIG_FILE'])
    ensure(path.is_absolute(), 'INVALID_REQUEST', 'Absolute resident configuration required')
    raw = read_locked(path, 65536)
    value = decode(raw)
    ensure(isinstance(value, dict) and set(value) == {'version', 'runtime_volume_root', 'tools'}
           and value['version'] == '0.1.0' and isinstance(value['tools'], dict),
           'INVALID_REQUEST', 'Exact resident configuration v0.1.0 required')
    ensure(Path(value['runtime_volume_root']).is_absolute(), 'INVALID_REQUEST', 'Absolute shared volume required')
    return value, sha(raw)


def key(tool_id):
    return 'structure' if tool_id == 't01.real.ingest_structure' else tool_id.rsplit('.', 1)[1].replace('_', '-')


def registered(entry, tool, source_image):
    ensure(isinstance(entry, dict) and set(entry) == {'root', 'command', 'source_image_id'},
           'ASSET_MISSING', 'Resident tool registration is missing')
    row = entry['command']
    ensure(isinstance(row, dict) and set(row) == {'tool', 'argv', 'environment', 'memory_bytes'}
           and isinstance(row['argv'], list) and isinstance(row['environment'], dict),
           'INVALID_REQUEST', 'Invalid fixed resident command')
    command = Command(row['tool'], tuple(row['argv']), tuple(sorted(row['environment'].items())), row['memory_bytes'])
    command.document()
    ensure(command.tool == tool and entry['source_image_id'] == source_image
           and row['environment'].get('T01_SOURCE_IMAGE_ID') == source_image
           and row['environment'].get('T01_RESIDENT_OFFLINE') == '1',
           'PROFILE_NOT_APPROVED', 'Resident command must bind the source image and offline guard')
    return command


def inputs_for(rt, job):
    folder = within(rt.root, rt.attempt_path(job))
    files = {}
    for path in sorted(folder.rglob('*')):
        relative = path.relative_to(folder).as_posix()
        if relative.split('/')[0] in ('output', 'published'): continue
        safe_path(folder, relative)
        if path.is_file(): files[relative] = read_locked(path, 32 * 1024 ** 2)
    ensure(files and len(files) <= 128 and sum(map(len, files.values())) <= 128 * 1024 ** 2,
           'OUTPUT_INVALID', 'Resident input inventory exceeds bounds')
    return files


def reconcile(rt, job_id):
    from .development.registry import spec
    from .winprocess import initialization_lock
    with initialization_lock('t01-resident-' + sha((str(rt.root) + ':' + job_id).encode())):
        job = rt.get(job_id)
        if job['state'] in TERMINAL: return job
        ex = rt.execution(job_id)
        worker = spec(job['tool_id'])
        binding = {k: job[k] for k in ('job_id', 'attempt_id', 'execution_identity')}
        try:
            config, fingerprint = configuration()
            ensure(ex.get('resident_config_sha256', fingerprint) == fingerprint,
                   'PROFILE_NOT_APPROVED', 'Resident configuration changed during this attempt')
            command = registered(config['tools'].get(key(job['tool_id'])), key(job['tool_id']), worker.IMAGE)
            if 'resident_target' not in ex:
                ensure(not ex.get('fault'), 'INVALID_REQUEST', 'Resident execution does not accept development fault injection')
                worker.verify_assets()
                ensure(job['execution_profile'] == worker.registered_profile(),
                       'PROFILE_NOT_APPROVED', 'Tool implementation changed since admission')
                body = worker.request(rt._request_bytes(job))
                if key(job['tool_id']) in ('blast', 'homology'):
                    root = rt.blast_database_root if key(job['tool_id']) == 'blast' else rt.homology_database_root
                    database = worker.verify_database(root, body)
                    database.pop('mount_path')
                    ex['database_receipt'] = database
                root = Path(config['tools'][key(job['tool_id'])]['root'])
                volume = Path(config['runtime_volume_root']).resolve()
                ensure(root.is_absolute() and root.resolve().is_relative_to(volume)
                       and rt.root.resolve().is_relative_to(volume),
                       'FORBIDDEN', 'Runtime and resident spool must share the configured volume')
                execution_id = sha(encode(binding))[:32]
                ex.update(backend='resident-process', phase='resident_stage_intent',
                          resident_target=str(root / execution_id), resident_config_sha256=fingerprint)
                with rt._tx() as db: rt._execution_store(db, job_id, ex)
            target = Path(ex['resident_target'])
            # Stage is replayable after dispatcher interruption. No new identity
            # is allocated, and a committed request is never overwritten.
            request_path = target / 'request.json'
            if not request_path.exists():
                body = worker.request(rt._request_bytes(job))
                prepare(target.parent, target.name, binding, command, inputs_for(rt, job), body['timeout_seconds'],
                        cancel_requested=bool(rt.get(job_id)['stop_reason']))
            request_raw = read_locked(request_path, 1024 ** 2)
            request = decode(request_raw)
            ensure(ex.get('resident_request_sha256', sha(request_raw)) == sha(request_raw),
                   'OUTPUT_INVALID', 'Committed resident request changed')
            ensure(request['binding'] == binding and request['command'] == command.document()
                   and request['execution_id'] == target.name, 'OUTPUT_INVALID', 'Resident request identity differs')
            ex.update(resident_request_sha256=sha(request_raw), phase='resident_observing')
            with rt._tx() as db: rt._execution_store(db, job_id, ex)
            job = rt.get(job_id)
            if job['stop_reason']: cancel(target)
            if not (target / 'execution.json').exists(): return rt.get(job_id)
            receipt = decode(read_locked(target / 'execution.json', 1024 ** 2))
            ensure(receipt['backend'] == 'resident-process' and receipt['binding'] == binding
                   and receipt['execution_id'] == target.name and receipt['request_sha256'] == sha(request_raw),
                   'OUTPUT_INVALID', 'Resident execution receipt identity differs')
            if receipt['stopped_confirmed'] is not True: return rt.get(job_id)
            ensure(receipt['state'] in ('succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'),
                   'OUTPUT_INVALID', 'Invalid resident terminal state')
            ex['resident_receipt'] = receipt
            error = {'succeeded': None, 'failed': 'TOOL_FAILED', 'cancelled': 'CANCELLED',
                     'timed_out': 'TIMEOUT', 'interrupted': 'INTERRUPTED'}[receipt['state']]
            if receipt['state'] in ('cancelled', 'timed_out'):
                with rt._tx() as db:
                    current = rt._job(db, job_id)
                    if not current['stop_reason']: rt._stop(db, current, 'cancel' if receipt['state'] == 'cancelled' else 'timeout')
                job = rt.get(job_id)
            verify_inputs(target, request)
            ensure(receipt['outputs'] == inventory(target), 'OUTPUT_INVALID', 'Resident output inventory changed')
            files = inputs_for(rt, job)
            files['resident/request.json'] = request_raw
            for name in receipt['outputs']:
                raw = read_locked(safe_path(target, name), 32 * 1024 ** 2)
                destination = name.replace('output/native/', 'output/', 1) if name.startswith('output/native/') else 'resident/' + name[7:]
                ensure(destination not in files, 'OUTPUT_INVALID', 'Resident artifact path collision')
                files[destination] = raw
            return finish(rt, job, ex, files, error)
        except (RuntimeFault, OSError, ValueError, KeyError, TypeError) as exc:
            ex['resident_diagnostic'] = str(exc)
            with rt._tx() as db: rt._execution_store(db, job_id, ex)
            if ex.get('resident_receipt', {}).get('stopped_confirmed') is True:
                return finish(rt, job, ex, {}, 'OUTPUT_INVALID')
            if ex.get('resident_target'):
                # A committed request might already be executing. Never infer
                # stop from an absent/corrupt receipt or changed configuration.
                target = Path(ex['resident_target'])
                if (target / 'request.json').exists(): cancel(target)
                return rt._unknown(job_id, str(exc))
            return finish(rt, job, ex, {}, getattr(exc, 'code', 'ASSET_MISSING'))


def finish(rt, job, ex, files, error):
    from .development.registry import spec, result
    files = dict(files)
    receipt = ex.get('resident_receipt')
    observation = decode(files['resident/executor-observation.json']) if 'resident/executor-observation.json' in files else None
    actual = dict(job_id=job['job_id'], attempt_id=job['attempt_id'], execution_identity=job['execution_identity'],
                  backend='resident-process', exit_code=receipt.get('exit_code') if receipt else None,
                  error_code=error, stopped_confirmed=True, diagnostic=ex.get('resident_diagnostic') or error,
                  source_image_id=spec(job['tool_id']).IMAGE, resident_receipt=receipt,
                  resident_config_sha256=ex.get('resident_config_sha256'), resident_observation=observation,
                  database_receipt=ex.get('database_receipt'), source_receipt=ex.get('source_receipt'))
    files['resident/execution.json'] = encode(actual)
    built = result(job, spec(job['tool_id']).request(rt._request_bytes(job)), files, actual)
    ex.update(tree_stopped=True, phase='collected')
    return rt._finish_development(job['job_id'], ex, files, built)
