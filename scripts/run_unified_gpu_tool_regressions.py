"""Run resumable, serial target regressions for the three migrated GPU tools.

The remote payload creates one retained engineering run, prepares one verified
structure, then executes ProteinMPNN, ESM-IF1 and ThermoMPNN strictly in that
order.  Fixed scope/idempotency keys make an interrupted kubectl connection
safe to resume without duplicating any task.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from structure_integration_cases import cases


KUBECTL = 'C:/Program Files/Docker/Docker/resources/bin/kubectl.exe'
SCOPE = 'unified-gpu-tool-regressions-r01'
OUT = ROOT / 'discovery/t01-phase1-real/unified-gpu-worker-20260920/regressions-r01'


def fixture():
    return next(row for row in cases() if row['name'] == 'rsa-out-of-domain')


def remote_payload() -> str:
    case = fixture()
    structure_request = json.dumps(case['request'], ensure_ascii=False, sort_keys=True)
    structure_data = base64.b64encode(case['data']).decode()
    sequence = case['request']['protein_sequence']
    return f'''import base64
import json
import time
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import TERMINAL, RuntimeFault, decode, encode, ensure
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.proteinmpnn import policy as proteinmpnn
from t01_phase1_real.development.esm_if1 import policy as esm_if1
from t01_phase1_real.development.thermompnn import policy as thermompnn

SCOPE = {SCOPE!r}
SEQUENCE = {sequence!r}
STRUCTURE_REQUEST = json.loads({structure_request!r})
STRUCTURE_DATA = base64.b64decode({structure_data!r})
rt = Runtime(Path('/var/lib/t01/runtime'), scope=SCOPE)
run_id = rt.create_run(SCOPE)['run_id']

def settle(name, job, timeout):
    job_id = job['job_id']
    current = rt.get(job_id)
    if current['state'] == 'queued':
        rt.dispatch(job_id)
    deadline = time.monotonic() + timeout
    next_report = 0.0
    while True:
        current = rt.reconcile(job_id)
        if current['state'] in TERMINAL:
            break
        if time.monotonic() >= next_report:
            print('REGRESSION_PROGRESS', name, current['state'], flush=True)
            next_report = time.monotonic() + 20
        if time.monotonic() >= deadline:
            raise RuntimeError(name + ' did not become terminal before the acceptance deadline')
        time.sleep(2)
    print('REGRESSION_TERMINAL', name, current['state'], current.get('error_code'), flush=True)
    ensure(current['state'] == 'succeeded', current.get('error_code') or 'TOOL_FAILED',
           name + ' representative regression did not succeed')
    ensure(current['run_id'] == run_id and current['usable_for_pipeline'] is False,
           'OUTPUT_INVALID', name + ' escaped the retained unqualified run')
    if current.get('attempt_id'):
        execution = rt.execution(job_id)
        ensure(execution.get('tree_stopped') is True,
               'OUTPUT_INVALID', name + ' did not confirm process-tree stop')
    return current

def result_ref(job):
    ref = next((row for row in job['artifacts'] if row['role'] == 'result'), None)
    ensure(ref is not None and ref['run_id'] == run_id and ref['job_id'] == job['job_id'],
           'OUTPUT_INVALID', 'Successful upstream has no same-run result ArtifactRef')
    return ref

def runtime_from_result(job, value):
    row = next((row for row in value['raw_artifacts'] if row['path'] == 'output/runtime.json'), None)
    ensure(row is not None, 'OUTPUT_INVALID', 'Representative result has no native runtime receipt')
    return decode(rt.artifact_bytes(job['job_id'], row['artifact']['artifact_id']))

def summary(name, job):
    value = rt.result(job['job_id'])
    execution = rt.execution(job['job_id'])
    receipt = execution.get('resident_receipt') or {{}}
    runtime = runtime_from_result(job, value)
    ensure(execution.get('backend') == 'resident-process'
           and receipt.get('state') == 'succeeded'
           and receipt.get('stopped_confirmed') is True,
           'OUTPUT_INVALID', name + ' has no successful stopped resident receipt')
    ensure(runtime.get('gpu_available') is True
           and runtime.get('gpu_name') == 'NVIDIA A100-SXM-64GB',
           'OUTPUT_INVALID', name + ' did not execute on the registered A100 64GB target')
    metrics = {{}}
    if name == 'proteinmpnn':
        generation = value['generation']
        ensure(generation['generated_count'] == 24 and generation['engine_runtime']['tool_invoked'] is True,
               'OUTPUT_INVALID', 'ProteinMPNN representative generation differs')
        metrics = {{'generated_count': generation['generated_count']}}
    elif name == 'esm-if1':
        scoring = value['scoring']
        ensure(len(scoring['records']) == 1 and scoring['records'][0]['score'] is not None,
               'OUTPUT_INVALID', 'ESM-IF1 representative score differs')
        metrics = {{'scored_count': 1, 'baseline_status': scoring['baseline_status']}}
    else:
        scan = value['scan']
        ensure(scan['native_prediction_count'] == 20 * len(SEQUENCE)
               and scan['engine_runtime']['tool_invoked'] is True,
               'OUTPUT_INVALID', 'ThermoMPNN representative scan differs')
        metrics = {{'native_prediction_count': scan['native_prediction_count'],
                   'selected_prediction_count': scan['selected_prediction_count']}}
    return {{
        'name': name,
        'job': {{key: job.get(key) for key in (
            'job_id', 'run_id', 'state', 'error_code', 'started_at', 'finished_at',
            'scientific_disposition', 'usable_for_pipeline')}},
        'execution': {{
            'backend': execution.get('backend'),
            'tree_stopped': execution.get('tree_stopped'),
            'resident_config_sha256': execution.get('resident_config_sha256'),
            'resident_request_sha256': execution.get('resident_request_sha256'),
            'resident_execution_id': receipt.get('execution_id'),
            'resident_state': receipt.get('state'),
            'resident_stopped_confirmed': receipt.get('stopped_confirmed'),
            'source_image_id': execution.get('source_image_id'),
        }},
        'runtime': {{key: runtime.get(key) for key in (
            'python', 'torch', 'cuda', 'gpu_available', 'gpu_name', 'gpu_capability',
            'network_interfaces', 'python_exit_code', 'tool_invoked')}},
        'metrics': metrics,
        'result_artifact': result_ref(job),
        'all_artifacts': job['artifacts'],
    }}

structure_job = rt.submit_structure_in_run(
    run_id, encode(STRUCTURE_REQUEST), SCOPE + '-structure', STRUCTURE_DATA)
structure_job = settle('structure', structure_job, 300)
structure_ref = result_ref(structure_job)

mpnn_body = dict(
    protein_sequence=SEQUENCE,
    user_sequence_id='Unified GPU ProteinMPNN target regression',
    structure_artifact=structure_ref,
    constraints=dict(
        purpose='ENGINEERING_EXPLICIT_MASKS',
        source_id='Unified GPU target regression',
        fixed_positions=[1, len(SEQUENCE)],
        restricted_positions=[dict(position=2, allowed_residues=''.join(sorted(set(SEQUENCE[1] + 'A'))))],
        open_positions=list(range(3, len(SEQUENCE))),
    ),
    n_designs=24,
    sampling_temperature=0.1,
    seed=17,
    timeout_seconds=300,
)
mpnn_job = rt.submit_sequence_in_run(
    run_id, encode(mpnn_body), SCOPE + '-proteinmpnn', proteinmpnn.TOOL)
mpnn_job = settle('proteinmpnn', mpnn_job, 900)
mpnn_ref = result_ref(mpnn_job)

esm_body = dict(
    protein_sequence=SEQUENCE,
    user_sequence_id='Unified GPU ESM-IF1 target regression',
    structure_artifact=structure_ref,
    n11_artifact=mpnn_ref,
    sample_numbers=[1],
    baseline_artifact=None,
    timeout_seconds=300,
)
esm_job = rt.submit_sequence_in_run(
    run_id, encode(esm_body), SCOPE + '-esm-if1', esm_if1.TOOL)
esm_job = settle('esm-if1', esm_job, 900)

thermo_body = dict(
    protein_sequence=SEQUENCE,
    user_sequence_id='Unified GPU ThermoMPNN target regression',
    structure_artifact=structure_ref,
    scan_positions=list(range(1, len(SEQUENCE) + 1)),
    excluded_positions=[2, 8],
    scope_source=dict(purpose='ENGINEERING_EXPLICIT_SCAN_SCOPE', source_id='Unified GPU target regression'),
    timeout_seconds=300,
)
thermo_job = rt.submit_sequence_in_run(
    run_id, encode(thermo_body), SCOPE + '-thermompnn', thermompnn.TOOL)
thermo_job = settle('thermompnn', thermo_job, 900)

jobs = [mpnn_job, esm_job, thermo_job]
ensure(all(jobs[index]['finished_at'] <= jobs[index + 1]['started_at'] for index in range(2)),
       'OUTPUT_INVALID', 'GPU representative tasks overlapped')
rows = [summary('proteinmpnn', mpnn_job), summary('esm-if1', esm_job), summary('thermompnn', thermo_job)]
result = dict(
    status='UNIFIED_GPU_THREE_TOOL_SERIAL_REGRESSION_PASS',
    scope=SCOPE,
    run_id=run_id,
    structure_job_id=structure_job['job_id'],
    tools=rows,
    serial_order=[row['name'] for row in rows],
    gpu_name='NVIDIA A100-SXM-64GB',
    scientific_gate='CLOSED',
    usable_for_pipeline=False,
    automatic_handoff=False,
    production_status='NOT_DEPLOYED',
)
print('UNIFIED_GPU_REGRESSION_RESULT ' + json.dumps(result, sort_keys=True), flush=True)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    payload = remote_payload()
    compile(payload, 'unified-gpu-regressions-remote', 'exec')
    if args.check:
        print('UNIFIED_GPU_REGRESSION_PAYLOAD_CHECK_PASS')
        print('fixture_sha256=' + hashlib.sha256(fixture()['data']).hexdigest())
        return

    command = [
        KUBECTL, '--kubeconfig', str(ROOT / '.tmp/himat.kubeconfig'),
        '--request-timeout=90s', '-n', 'him-ws', 'exec', '-i',
        'deployment/antigen-design', '-c', 'service', '--',
        'python', '-u', '-B', '-X', 'utf8', '-',
    ]
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write(payload.encode())
    process.stdin.close()
    marker = 'UNIFIED_GPU_REGRESSION_RESULT '
    document = None
    for raw in iter(process.stdout.readline, b''):
        line = raw.decode(errors='replace').rstrip()
        if line.startswith(marker):
            document = json.loads(line[len(marker):])
            print('UNIFIED_GPU_REGRESSION_RESULT_RECEIVED', flush=True)
        else:
            print(line, flush=True)
    returncode = process.wait(timeout=30)
    if returncode != 0 or document is None:
        raise RuntimeError(
            'Cluster regression interrupted or failed; rerun this exact command to resume retained jobs')
    if document['status'] != 'UNIFIED_GPU_THREE_TOOL_SERIAL_REGRESSION_PASS':
        raise RuntimeError('Remote regression did not return PASS')
    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / 'latest.json'
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('UNIFIED_GPU_THREE_TOOL_SERIAL_REGRESSION_PASS')
    print('SAVED', output)


if __name__ == '__main__':
    main()
