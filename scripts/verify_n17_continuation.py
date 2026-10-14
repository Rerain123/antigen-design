"""Read-only replay of a real completed workflow's scan skips, no model submissions."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode,sha

OUT=common.ROOT/'reports/n17-continuation-20260927'
REMOTE=r'''
import copy,json,sys
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development.local_delivery.n17 import facts
from t01_phase1_real.service_api.user_report import render
p=json.load(sys.stdin)
owner=Principal('himat-t01-test',frozenset(['query']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
parent=rt.get(p['job_id']);original=rt.execution(parent['job_id']);rows=original['nodes']
request=decode(rt._request_bytes(parent))
with rt._db() as db:count=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
ref=rt.get(rows['wt_reference']['job_id']);raw=rt._request_bytes(ref)
value=rt.result(ref['job_id'])
class ReadOnly:
    def __getattr__(self,name):
        if name in ('_tx','dispatch','recover','control','submit_workflow','submit_sequence','_new_job','_store'):
            raise AssertionError('Mutation forbidden')
        return getattr(rt,name)
result=facts(ReadOnly(),parent,request,rows,{'input/wt_reference-request.json':raw},{'wt_reference':value})
assert all(r['state']=='skipped' and r['reason_code']=='NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION' for r in result['engines'].values())
data={'wt_reference':value['reference'],'n17_execution':result}
html=render(data,preview_note='真实归档输入只读回放：本轮未执行扫描，不替换原报告。')
assert '结构覆盖范围内没有允许扫描的位点' in html.decode()
assert rt.get(parent['job_id'])==parent and rt.execution(parent['job_id'])==original
with rt._db() as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==count
print(json.dumps(dict(status='PASS',mode='READ_ONLY_REAL_WORKFLOW_SKIP_REPLAY',workflow_job_id=parent['job_id'],
    scan_terminals=result,report_data=data,html_sha256=sha(html),archived_state_unchanged=True,new_jobs=0,model_invocations=0)))
'''


def main():
    original=json.loads((common.ROOT/'reports/n05-duration-20260926/host-flow-final-r02.json').read_bytes())
    result=common.remote(REMOTE,dict(job_id=original['job_id']))
    from t01_phase1_real.service_api.user_report import render
    html=render(result['report_data'],preview_note='真实归档输入只读回放：本轮未执行扫描，不替换原报告。')
    assert sha(html)==result['html_sha256']
    (OUT/'real-skip-replay.json').write_bytes(encode(result)+b'\n')
    (OUT/'real-skip-replay.html').write_bytes(html)
    print(json.dumps({k:result[k] for k in ('status','mode','new_jobs','model_invocations')}))


if __name__=='__main__':main()
