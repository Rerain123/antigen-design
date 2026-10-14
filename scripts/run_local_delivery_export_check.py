"""Final current-profile 24-exclusion export check; adds new task, preserves old artifacts."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from t01_phase1_real.common import REPO,decode,encode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.local_delivery import policy
from t01_phase1_real.development.wt_reference import policy as reference
from run_variant_report_acceptance import write

def main():
    base=REPO/'discovery/t01-phase1-real/w7/local-delivery-integration-20260910'
    target=base/'export-check-r01';assert not target.exists();target.mkdir(parents=True)
    body=decode((base/'acceptance-r01/requests/real24-all-excluded-delivery.json').read_bytes())
    rt=Runtime(REPO/'var/t01-phase1-real/local-delivery-20260910-acceptance-r01/design')
    j=rt.submit_sequence(encode(body),'final-export-check-r01',policy.TOOL);rt.dispatch(j['job_id']);j=rt.get(j['job_id']);v=rt.result(j['job_id'])
    assert j['state']=='succeeded' and v['delivery']['outcome']=='ALL_EXCLUDED'
    folder=target/'cases/real24-all-excluded-delivery'
    write(folder/'job.json',j);write(folder/'result.json',v);write(folder/'request.json',body)
    for r in j['artifacts']:write(folder/'artifacts'/r['artifact_id'],rt.artifact_bytes(j['job_id'],r['artifact_id']))
    for row in v['raw_artifacts']:
        if row['path'] in ('output/package.zip','output/report.md','output/data.json','output/manifest.json'):
            write(folder/Path(row['path']).name,rt.artifact_bytes(j['job_id'],row['artifact']['artifact_id']))
    for package in ('local_delivery','wt_reference'):
        for p in (policy.HERE.parent/package).glob('*.py'):write(target/'source'/package/p.name,p.read_bytes())
    for name in ('runtime.py','registry.py','contracts.py','cli.py'):write(target/'source'/name,(policy.HERE.parent/name).read_bytes())
    for name in ('run_local_delivery_export_check.py','audit_local_delivery_evidence.py'):write(target/'source/scripts'/name,(REPO/'scripts'/name).read_bytes())
    write(target/'index.json',dict(cases=[dict(case='real24-all-excluded-delivery',job_id=j['job_id'],runtime_root=str(rt.root),state=j['state'],error_code=None)],guards=[],
        original_24_exclusions_preserved=True,profiles={p.TOOL:dict(execution=p.registered_profile(),rules=p.registered_rules()) for p in (policy,reference)},
        files=[dict(path=p.relative_to(target).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(target.rglob('*')) if p.is_file()]))
    print('Final current-profile 24-exclusion export sealed',flush=True)

if __name__=='__main__':main()
