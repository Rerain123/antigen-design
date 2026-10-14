"""The target nr mount must be read-only in both N03 admission and execution."""
import sys
from t01_phase1_real.common import REPO

sys.path.insert(0, str(REPO / 'scripts'))
import prepare_m1_p4_nr_deploy as deploy


def test_target_mount_and_code_patch_preserve_existing_worker_root():
    live = dict(metadata=dict(resourceVersion='5', uid='deployment-uid'), spec=dict(
        replicas=1, strategy=dict(type='Recreate'), template=dict(spec=dict(
            containers=[
                dict(name='service', volumeMounts=[
                    dict(name='runtime', mountPath='/var/lib/t01'),
                    dict(name='m1-p4-code', mountPath='/app/src/t01_phase1_real/development/blast/policy.py'),
                    dict(name='m1-p4-code', mountPath='/app/src/t01_phase1_real/development/blast/prebuilt.py')]),
                dict(name='worker-blast', volumeMounts=[
                    dict(name='runtime', mountPath='/t01/databases/blast', readOnly=True)])],
            volumes=[dict(name='runtime', emptyDir={}), dict(name='m1-p4-code', configMap=dict(name='old'))]))))
    operations = deploy.patch(live)
    assert [op['op'] for op in operations[:2]] == ['test', 'test']
    replacements = {op['path']: op['value'] for op in operations if op['op'] == 'replace'}
    service = replacements['/spec/template/spec/containers/0/volumeMounts']
    worker = replacements['/spec/template/spec/containers/1/volumeMounts']
    assert sum(row['mountPath'] == deploy.SERVICE_MOUNT for row in service) == 1
    assert sum(row['mountPath'] == deploy.WORKER_MOUNT for row in worker) == 1
    assert any(row['mountPath'] == '/t01/databases/blast' for row in worker)
    for row in service + worker:
        if row['name'] == deploy.VOLUME:
            assert row['subPath'] == deploy.SUBPATH and row['readOnly'] is True
    assert all(sum(row['mountPath'] == '/app/src/t01_phase1_real/' + name for row in service) == 1
               for name in deploy.FILES)
    volumes = replacements['/spec/template/spec/volumes']
    target = next(row for row in volumes if row['name'] == deploy.VOLUME)
    assert target['persistentVolumeClaim'] == dict(claimName='antigen-n03-nr', readOnly=True)
