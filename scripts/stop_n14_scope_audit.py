"""User-requested stop before high-mutation scope audit. Never restart."""
import json
import prepare_m1_p1_deploy as common
from stop_pcv2_n14_performance import REMOTE
from version_bundle import encode

OUT=common.ROOT/'reports/n14-scope-audit-20260928'
SOURCE='t01p1r-job-71bf9c1321884d4bbc0d9607be7429d0'
if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    code=REMOTE.replace('user-n14-performance-stop-20260928','user-n14-scope-audit-stop-20260928')
    value=common.remote(code,dict(source=SOURCE))
    name='stop.json' if not (OUT/'stop.json').exists() else 'stop-confirmation.json'
    (OUT/name).write_bytes(encode(value))
    print(json.dumps(dict(checked_at=value['checked_at'],parent_state=value['parent']['state'],
        child_state=value['child']['state'],tree_stopped=value['execution'].get('tree_stopped'))))
