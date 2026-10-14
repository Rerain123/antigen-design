"""Record a read-only P4 FoldX timing and resource snapshot after r16 completes."""

import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import zipfile

import prepare_m1_p1_deploy as deploy


BASE = deploy.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922'
OUT = BASE / 'foldx-runtime-diagnosis-r01.json'
TIMELINE = '''import datetime,json,sys
from pathlib import Path
rows=json.load(sys.stdin)
result=[]
for row in rows:
    folder=Path(row['target'])/'output/native'
    def stamp(path):
        return dict(time=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat(),
                    bytes=path.stat().st_size)
    dt=datetime
    models=sorted((folder/'buildmodel').glob('target_Repair_*.pdb'),key=lambda p:p.stat().st_mtime)
    result.append(dict(batch=row['batch'],started=stamp(folder/'runtime_started.json'),
        repair_complete=stamp(folder/'repair/target_Repair.pdb'),
        models=[dict(name=p.name,**stamp(p)) for p in models],
        native_finished=stamp(folder/'runtime.json'),
        native_file_bytes=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())))
print(json.dumps(result))
'''


def kubectl(*args):
    run = subprocess.run(deploy.K + list(args), capture_output=True, check=True, timeout=110)
    return run.stdout.decode('utf-8')


def archived(batch):
    folder = BASE / batch
    row = json.loads((folder / 'stability.json').read_bytes())
    assert row['job']['state'] == 'succeeded' and row['job']['error_code'] is None
    refs = {item['path']: item['artifact'] for item in row['result']['raw_artifacts']}
    ref = refs['output/runtime.json']
    with zipfile.ZipFile(folder / 'native-evidence.zip') as archive:
        raw = archive.read('artifacts/' + ref['artifact_id'])
    assert hashlib.sha256(raw).hexdigest() == ref['sha256']
    native = json.loads(raw)
    assert native['commands']['repair']['exit_code'] == 0
    assert native['commands']['buildmodel']['exit_code'] == 0
    models = [name for name in refs if name.startswith('output/buildmodel/target_Repair_') and name.endswith('.pdb')]
    assert len(models) == 15
    return dict(batch=batch, job_id=row['job']['job_id'], started_at=row['job']['started_at'],
                finished_at=row['job']['finished_at'], native_elapsed_seconds=native['elapsed_seconds'],
                input_structure_sha256=refs['native/target.pdb']['sha256'],
                mutation_list_sha256=refs['output/buildmodel/individual_list.txt']['sha256'],
                executable_sha256=native['executable_sha256'], commands=native['commands'],
                model_count=len(models), resident_target=row['execution']['resident_target'],
                evidence=str((folder / 'stability.json').relative_to(deploy.ROOT)).replace('\\', '/'))


def main():
    assert not OUT.exists(), 'Diagnosis evidence already exists; preserve its original bytes'
    runs = [archived(batch) for batch in ('r02', 'r16')]
    assert len({run['input_structure_sha256'] for run in runs}) == 1
    assert len({run['mutation_list_sha256'] for run in runs}) == 1
    assert len({run['executable_sha256'] for run in runs}) == 1
    assert len({json.dumps(run['commands'], sort_keys=True) for run in runs}) == 1
    timelines = deploy.remote(TIMELINE, [{'batch': r['batch'], 'target': r['resident_target']} for r in runs])
    for run, timeline in zip(runs, timelines):
        assert run['batch'] == timeline['batch'] and len(timeline['models']) == run['model_count']
        times = [dt.datetime.fromisoformat(item['time']) for item in timeline['models']]
        intervals = [(b - a).total_seconds() for a, b in zip(times, times[1:])]
        run['timeline'] = timeline
        run['model_interval_median_seconds'] = statistics.median(intervals)
        run['repair_seconds'] = (dt.datetime.fromisoformat(timeline['repair_complete']['time']) -
                                 dt.datetime.fromisoformat(timeline['started']['time'])).total_seconds()
        run['buildmodel_after_repair_seconds'] = (dt.datetime.fromisoformat(timeline['native_finished']['time']) -
                                                   dt.datetime.fromisoformat(timeline['repair_complete']['time'])).total_seconds()
    deployment = json.loads(kubectl('get', 'deployment', 'antigen-design', '-o', 'json'))
    container = next(item for item in deployment['spec']['template']['spec']['containers'] if item['name'] == 'worker-foldx')
    pods = json.loads(kubectl('get', 'pods', '-o', 'json'))['items']
    pod = next(item for item in pods if item['metadata']['name'].startswith('antigen-design-'))
    status = next(item for item in pod['status']['containerStatuses'] if item['name'] == 'worker-foldx')
    assert status['restartCount'] == 0
    cgroup = {}
    for name in ('cpu.max', 'cpu.stat', 'memory.peak', 'memory.events'):
        cgroup[name] = kubectl('exec', 'deployment/antigen-design', '-c', 'worker-foldx',
                              '--', 'cat', '/sys/fs/cgroup/' + name).strip()
    value = dict(status='P4_FOLDX_RUNTIME_DIAGNOSIS_R01', captured_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                 scope='Read-only timing comparison and current FoldX container resource snapshot',
                 runs=runs, same_structure_mutations_executable_and_commands=True,
                 deployment=dict(image=container['image'], resources=container['resources']),
                 pod=dict(name=pod['metadata']['name'], start_time=pod['status']['startTime'],
                          worker_started_at=status['state']['running']['startedAt'],
                          worker_restart_count=status['restartCount']), cgroup_snapshot=cgroup,
                 cgroup_scope='Cumulative since current container start; not a per-job profile',
                 scientific_release_gate='CLOSED', usable_for_pipeline=False, production_status='NOT_DEPLOYED')
    OUT.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(OUT)
    print('r02/r16 native seconds:', *(round(run['native_elapsed_seconds'], 2) for run in runs))


if __name__ == '__main__':
    main()
