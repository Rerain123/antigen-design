"""Run from the derived FreeSASA image with the repository mounted read-only.

Two new real structure tasks are calculated in one resident worker lifetime.
The archived fixture supplies only the original input, never computed outputs.
"""
import json
import base64
import os
from pathlib import Path
import subprocess
import sys
import time

from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import REPO, encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.structure import policy
from t01_phase1_real.resident_process import Command, encoded


def main():
    root = Path('/tmp/resident-native')
    root.mkdir()
    spool = root / 'spool'
    spool.mkdir()
    cmd = Command('structure', ('/usr/local/bin/python', '-B', '/worker/worker.py'), (
        ('MPLCONFIGDIR', '/tmp/matplotlib'), ('OPENBLAS_NUM_THREADS', '1'), ('T01_RESIDENT_SLOT', '/run/t01-slot'),
        ('T01_RESIDENT_OFFLINE', '1'), ('T01_SOURCE_IMAGE_ID', policy.IMAGE)), 1024**3)
    worker_config = root / 'worker.json'
    worker_config.write_bytes(encoded(dict(version='0.1.0', commands=[cmd.document()])))
    controller_config = root / 'controller.json'
    controller_config.write_bytes(encode(dict(version='0.1.0', runtime_volume_root=str(root), tools={
        'structure': dict(root=str(spool), command=cmd.document(), source_image_id=policy.IMAGE)})))
    os.environ['T01_RESIDENT_CONFIG_FILE'] = str(controller_config)
    rt = Runtime(root / 'runtime')
    fixture = REPO / 'discovery/t01-phase1-real/w1/structure-integration-20260906/acceptance-r02/cases/normal-cif'
    old = json.loads((fixture / 'result.json').read_bytes())
    # Read ONLY original request and local input structure.
    refs = {r['path']: r['artifact']['artifact_id'] for r in old['raw_artifacts']}
    request = json.loads((fixture / 'artifacts' / refs['input.json']).read_bytes())
    request.pop('structure_artifact')
    data = (fixture / 'artifacts' / refs['input.structure']).read_bytes()
    worker = subprocess.Popen([sys.executable, '-B', '-m', 't01_phase1_real.resident_worker',
        '--root', str(spool), '--config', str(worker_config)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    results = []
    try:
        for index in range(2):
            job = rt.submit_structure(encode(request), 'resident-native-' + str(index), data)
            rt.dispatch(job['job_id'])
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                assert worker.poll() is None, 'Resident worker exited unexpectedly'
                job = rt.reconcile(job['job_id'])
                if job['state'] in ('succeeded', 'failed', 'cancelled', 'timed_out'): break
                time.sleep(.1)
            result = rt.result(job['job_id']) if job['state'] in ('succeeded','failed') else None
            if job['state'] != 'succeeded':
                target = Path(rt.execution(job['job_id'])['resident_target'])
                raise AssertionError(dict(state=job['state'], diagnostic=result['execution'] if result else None,
                    stderr=(target / 'output/stderr.txt').read_text() if (target / 'output/stderr.txt').exists() else None))
            assert result['analysis']['freesasa']['status'] == 'executed', result
            assert not result['usable_for_pipeline'] and result['scientific_signoff'] is None
            assert result['execution']['backend'] == 'resident-process'
            results.append(dict(job=job, result=result, raw_artifacts={r['path']:
                base64.b64encode(rt.artifact_bytes(job['job_id'],r['artifact']['artifact_id'])).decode()
                for r in result['raw_artifacts']}))
        assert results[0]['job']['attempt_id'] != results[1]['job']['attempt_id']
        totals = [r['result']['analysis']['freesasa']['total_sasa_a2'] for r in results]
        assert totals[0] == totals[1] and totals[0] > 0
        print(json.dumps(dict(status='PASS', boundary='LOCAL_REAL_STRUCTURE_RUNTIME_RESIDENT',
                              worker_pid=worker.pid, tasks=results), ensure_ascii=False), flush=True)
    finally:
        worker.terminate()
        stdout, stderr = worker.communicate(timeout=10)
        print(stdout.decode(), file=sys.stderr)
        print(stderr.decode(), file=sys.stderr)


if __name__ == '__main__': main()
