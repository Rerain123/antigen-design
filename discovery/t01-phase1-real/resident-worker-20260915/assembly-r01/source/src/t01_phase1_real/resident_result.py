"""Execution checks shared by native parsers; scientific checks stay in each parser."""
from .common import RuntimeFault, decode, sha


def image_matches(execution, expected):
    if execution.get('backend') != 'resident-process':
        return execution.get('image_id') == expected
    receipt = execution.get('resident_receipt') or {}
    return (execution.get('source_image_id') == expected
            and receipt.get('backend') == 'resident-process' and receipt.get('state') == 'succeeded'
            and receipt.get('stopped_confirmed') is True and type(receipt.get('exit_code')) is int
            and receipt['exit_code'] == 0 and receipt.get('binding') == {
                k: execution.get(k) for k in ('job_id', 'attempt_id', 'execution_identity')})


def isolation_matches(runtime, files, expected_image, legacy_cpus=None):
    if 'resident/execution.json' not in files:
        return runtime.get('network_interfaces') == [[1, 'lo']] and (
            legacy_cpus is None or runtime.get('cpu_affinity') == legacy_cpus)
    try:
        execution = decode(files['resident/execution.json'])
        request_raw = files['resident/request.json']
        request = decode(request_raw)
        receipt = execution['resident_receipt']
        observation = decode(files['resident/executor-observation.json'])
        if not image_matches(execution, expected_image): return False
        if (receipt['request_sha256'] != sha(request_raw) or receipt['binding'] != request['binding']
                or receipt['execution_id'] != request['execution_id']
                or request['command']['environment'].get('T01_SOURCE_IMAGE_ID') != expected_image
                or request['command']['environment'].get('T01_RESIDENT_OFFLINE') != '1'): return False
        for name, info in receipt['outputs'].items():
            mapped = name.replace('output/native/', 'output/', 1) if name.startswith('output/native/') else 'resident/' + name[7:]
            raw = files[mapped]
            if len(raw) != info['size_bytes'] or sha(raw) != info['sha256']: return False
        return (observation == execution['resident_observation']
                and observation['source_image_id'] == expected_image and observation['machine'] == 'x86_64'
                and observation['network_restriction'] == 'seccomp-local-sockets-only-v1'
                and runtime.get('network_interfaces') == observation['network_interfaces']
                and ('cpu_affinity' not in runtime or runtime['cpu_affinity'] == observation['cpu_affinity']))
    except (RuntimeFault, KeyError, TypeError, ValueError):
        return False
