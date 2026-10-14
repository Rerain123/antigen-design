"""N03 rollout must preserve the paused P2 surface and unrelated mounts."""
import importlib.util
from pathlib import Path
import sys

ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import prepare_iedb_n03_deploy as deploy


def test_overlay_retains_live_check_without_reverting_new_submission():
    local='class HiMatIntegration:\n    def submit_sequence(self):\n        return "iedb"\n    def check(self):\n        return "p2"\n'
    live='class HiMatIntegration:\n    def submit_sequence(self):\n        return "nr"\n    def check(self):\n        return "live"\n'
    ns={};exec(deploy.keep_live_check(local,live),ns);obj=ns['HiMatIntegration']()
    assert obj.submit_sequence()=='iedb' and obj.check()=='live'


def test_overlay_binds_helper_to_worker_and_preserves_gpu():
    gpu=dict(name='worker-unified-gpu',volumeMounts=[dict(mountPath='/backend',name='old')])
    live=dict(metadata=dict(uid='uid',resourceVersion='revision'),spec=dict(replicas=1,strategy=dict(type='Recreate'),
        template=dict(spec=dict(volumes=[],containers=[dict(name='service',volumeMounts=[]),
            dict(name='worker-blast',volumeMounts=[dict(mountPath='/t01/databases/blast',name='runtime',readOnly=True)]),gpu]))))
    cm,patch=deploy.render(live,{n:b'content' for n in deploy.FILES})
    assert not any('/containers/2/' in op['path'] for op in patch)
    mounts=next(op['value'] for op in patch if op['path'].endswith('/containers/1/volumeMounts'))
    assert any(m['mountPath'].endswith('/blast/iedb.py') and m['readOnly'] for m in mounts)
    assert mounts[0]==dict(mountPath='/t01/databases/blast',name='runtime',readOnly=True)
