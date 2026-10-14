"""Record verified release facts without changing scientific assets."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EV = HERE / 'deployment-r02'
def read(path): return json.loads(path.read_bytes())
def write(path, value): path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

deployment = read(EV/'deployment-verification.json')
assert deployment['status'] == 'PASS' and len(deployment['containers']) == 10
before = read(EV/'previous-task-before.json')
assert before == read(EV/'previous-task-after.json')
publications = [read(EV/(label+'-report-publication.json')) for label in ('old','new')]
assert all(p['status'] == 'PASS' and p['scientific_state_unchanged'] and len(p['attachments']) == 4 for p in publications)
commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert commit == read(EV/'regression.json')['commit']
remote = subprocess.check_output(['git','ls-remote','origin','refs/heads/test'],cwd=ROOT,text=True).split()[0]
assert commit == remote
cluster = read(EV/'test-auto-deployment.json')
api_pod = next(p for p in cluster['pods'] if any(c['name']=='service' for c in p['containers']))
value = dict(status='COMPLETE', verified_at=datetime.now(timezone.utc).isoformat(),
    commit=commit, remote_branch='origin/test',
    deployment_method='test push triggered automatic API image deployment; committed source snapshot synchronized to ten workloads',
    source_files=deployment['files'], source_sha256=deployment['source_sha256'],
    api_generation=deployment['generations']['antigen-design'], ready_workloads=10,
    api_image=api_pod['containers'][0]['image_id'],
    job_count=before['job_count'], jobs_and_executions_unchanged=True, new_scientific_jobs=0,
    tests=dict(prior_full_passed=3418,prior_full_skipped=17,final_affected_passed=145,
               single_final_full_run=False,real_export='export-probe.json'),
    reports=[dict(name=p['report_name'],publication_status=p['publication_status'],
                  attachments_verified=4,html=next(a for a in p['attachments'] if a['fileName'].endswith('.html'))) for p in publications],
    limitations=['No browser visual screenshot: local file URL access was denied.',
                 'Original raw scientific fixtures were kept local, not pushed.'])
write(EV/'closeout.json',value)
for name in ('implementation.json','export-implementation.json'):
    path=HERE/name; item=read(path)
    item.update(status='DEPLOYED_AND_VERIFIED',online_deployed=True,committed=True,pushed=True,
                deployed_commit=commit,deployment_receipt='deployment-r02/closeout.json')
    write(path,item)
path=ROOT/'docs/project/STATUS.md';text=path.read_text(encoding='utf-8')
old='修复98a24c8已推送test，第二阶段线上同步和正式查询核验进行中，尚不声明RustFS附件交付完成；证据见reports/report-fix-20261014/export-probe.json及export-fix-tests.xml。'
new='修复98a24c8已推送origin/test并完成自动镜像更新及十服务源码同步：API generation189、9个Worker各generation11，全部Ready、零重启，272份源码逐字节与Git一致，2428个任务及执行记录hash不变。新旧两任务正式HiMat查询均成功：新版HTML与本地已核验版本hash一致，旧32/新6个唯一候选及逐项结果保留，整体验收字样已移除；各四个RustFS附件均HEAD和匿名实际下载hash通过，原科学结果包不变、新科学任务0。原始附件顺序调整使ZIP新hash变化，但每项内容及来源manifest均核验；旧对象按版本key保留。见[最终上线核验](../../reports/report-fix-20261014/deployment-r02/closeout.json)、[新报告发布](../../reports/report-fix-20261014/deployment-r02/new-report-publication.json)、[旧报告发布](../../reports/report-fix-20261014/deployment-r02/old-report-publication.json)、[真实导出验证](../../reports/report-fix-20261014/export-probe.json)及[最终145项回归](../../reports/report-fix-20261014/export-fix-tests.xml)。此前全量回归早于最终导出修复，最终以受影响回归及线上真实导出核验补齐。'
assert old in text
path.write_text(text.replace(old,new),encoding='utf-8')
print(json.dumps(dict(status=value['status'],commit=commit,api_generation=value['api_generation'],reports=len(publications)),ensure_ascii=False))
