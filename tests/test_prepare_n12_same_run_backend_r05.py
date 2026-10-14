import copy
import hashlib

from scripts import prepare_n12_same_run_backend_r05 as prep


def fixture():
    base_path = 't01_phase1_real/development/esmfold2/source.py'
    base_text = (prep.ROOT / 'src' / base_path).read_text(encoding='utf-8')
    items = [dict(key='base-esmfold2-source', path=base_path)]
    data = {'base-esmfold2-source': base_text}
    oldvolume = dict(name=prep.OLD_CODE, items=copy.deepcopy(items))
    deployment = dict(
        metadata=dict(resourceVersion='10', generation=4),
        status=dict(readyReplicas=1, observedGeneration=4),
        spec=dict(template=dict(spec=dict(
            containers=[dict(name='service', image=prep.IMAGE,
                             volumeMounts=[dict(name='runtime', mountPath='/var/lib/t01')])],
            volumes=[dict(name='esmfold2-code', configMap=oldvolume)],
        ))),
    )
    oldcode = dict(metadata=dict(name=prep.OLD_CODE), immutable=True, data=data)
    return deployment, oldcode


def test_render_adds_all_same_run_sources_and_guarded_patch():
    deployment, oldcode = fixture()
    code, patch, hashes = prep.render(deployment, oldcode)
    assert code['metadata']['name'] == prep.NEW_CODE
    assert code['immutable'] is True
    final_volume = next(row['value'] for row in patch
                        if row['op'] == 'replace' and row['path'].endswith('/configMap'))
    by_path = {row['path']: row['key'] for row in final_volume['items']}
    assert set(prep.REQUIRED_PATHS) <= set(by_path)
    for path in prep.REQUIRED_PATHS:
        digest = hashlib.sha256(code['data'][by_path[path]].encode()).hexdigest()
        assert digest == hashes[path]
    assert [row['op'] for row in patch[:4]] == ['test', 'test', 'test', 'test']
    service_mounts = patch[-1]['value']
    mounted = {row.get('subPath'): row for row in service_mounts if row['name'] == 'esmfold2-code'}
    assert set(prep.OVERLAY_PATHS) == set(mounted)
    for path in prep.OVERLAY_PATHS:
        assert mounted[path] == dict(name='esmfold2-code',
                                     mountPath=prep.SERVICE_SOURCE_ROOT + '/' + path,
                                     subPath=path, readOnly=True)


def test_render_rejects_service_source_mount_collision():
    deployment, oldcode = fixture()
    path = prep.OVERLAY_PATHS[0]
    deployment['spec']['template']['spec']['containers'][0]['volumeMounts'].append(
        dict(name='other', mountPath=prep.SERVICE_SOURCE_ROOT + '/' + path))
    try:
        prep.render(deployment, oldcode)
    except ValueError as exc:
        assert 'mount collision' in str(exc)
    else:
        raise AssertionError('Service source mount collision was accepted')


def test_render_rejects_wrong_base_revision():
    deployment, oldcode = fixture()
    deployment['spec']['template']['spec']['volumes'][0]['configMap']['name'] = 'wrong'
    try:
        prep.render(deployment, oldcode)
    except ValueError as exc:
        assert 'r03' in str(exc)
    else:
        raise AssertionError('Wrong base revision was accepted')


def test_render_accepts_existing_r04_base_revision():
    deployment, oldcode = fixture()
    deployment['spec']['template']['spec']['volumes'][0]['configMap']['name'] = prep.R04_CODE
    oldcode['metadata']['name'] = prep.R04_CODE
    prep.render(deployment, oldcode)


def test_render_accepts_existing_r04b_base_revision():
    deployment, oldcode = fixture()
    deployment['spec']['template']['spec']['volumes'][0]['configMap']['name'] = prep.R04B_CODE
    oldcode['metadata']['name'] = prep.R04B_CODE
    code, patch, _ = prep.render(deployment, oldcode)
    assert code['metadata']['name'] == prep.NEW_CODE
    assert patch[-1]['path'].endswith('/volumeMounts')


def test_render_accepts_existing_r05_base_revision():
    deployment, oldcode = fixture()
    deployment['spec']['template']['spec']['volumes'][0]['configMap']['name'] = prep.NEW_CODE
    oldcode['metadata']['name'] = prep.NEW_CODE
    code, patch, _ = prep.render(deployment, oldcode)
    assert code['metadata']['name'] == prep.NEW_CODE
    assert patch[-1]['path'].endswith('/volumeMounts')


def test_render_reuses_existing_valid_service_mounts():
    deployment, oldcode = fixture()
    mounts = deployment['spec']['template']['spec']['containers'][0]['volumeMounts']
    mounts.extend(dict(name='esmfold2-code',
                       mountPath=prep.SERVICE_SOURCE_ROOT + '/' + path,
                       subPath=path, readOnly=True)
                  for path in prep.OVERLAY_PATHS[:-1])
    _, patch, _ = prep.render(deployment, oldcode)
    service_mounts = patch[-1]['value']
    mounted = [row for row in service_mounts if row['name'] == 'esmfold2-code']
    assert len(mounted) == len(prep.OVERLAY_PATHS)
