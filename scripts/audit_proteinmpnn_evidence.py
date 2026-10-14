"""Read-only independent W5 evidence inventory, source snapshot and native-result audit."""
import argparse
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.proteinmpnn import policy
from t01_phase1_real.development.proteinmpnn.result import parse


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();batch=Path(args.batch).absolute();index=decode((batch/'index.json').read_bytes())
    assert index['status']=='PASS' and not Path(args.output).exists()
    failures=[]
    for item in index['files']:
        path=batch/item['path']
        if not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path.read_bytes())!=item['sha256']:failures.append(item['path'])
    source_files=[p for p in (batch/'source').rglob('*') if p.is_file()]
    changed=[p.relative_to(batch/'source').as_posix() for p in source_files if p.read_bytes()!=(REPO/p.relative_to(batch/'source')).read_bytes()]
    assert not failures and not changed,(failures,changed)
    assert index['profile']==policy.registered_profile() and decode((batch/'rules.json').read_bytes())==policy.registered_rules()
    assert decode((batch/'assets.json').read_bytes())==policy.verify_assets()
    count=0;native=[];peaks=[]
    for case in index['cases']:
        folder=batch/'cases'/case['case'];job=decode((folder/'job.json').read_bytes())
        assert job['job_id']==case['job_id'] and job['state']==case['state'] and job['error_code']==case['error_code']
        for ref in job['artifacts']:
            raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];count+=1
        if not job['artifacts']:continue
        value=decode((folder/'result.json').read_bytes())
        result_ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert value==decode((folder/'artifacts'/result_ref['artifact_id']).read_bytes())
        assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['scientific_signoff'] is None
        if job['tool_id']!=policy.TOOL:continue
        assert job['execution_profile']==policy.registered_profile() and value['formal_candidates'] is None and value['scientific_gate']=='NOT_EVALUATED'
        if not value['generation']:continue
        files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
        body=decode(files['input.json']);generated=parse(body,files)
        assert generated==value['generation']
        native.append(dict(case=case['case'],generated_count=generated['generated_count'],tool_invoked=generated['engine_runtime']['tool_invoked']))
        peaks.append(generated['engine_runtime']['gpu_peak_allocated_bytes'])
    report=dict(status='PASS',index_sha256=sha((batch/'index.json').read_bytes()),batch=str(batch),
        files_verified=len(index['files']),source_files_verified=len(source_files),artifacts_verified=count,
        case_count=len(index['cases']),guard_count=len(index['guards']),native_results_reparsed=native,
        source_snapshot_changes=changed,inventory_failures=failures,current_execution_and_rule_profiles_match=True,
        max_observed_gpu_peak_allocated_bytes=max(peaks),scientific_signoff=None,usable_for_pipeline=False,
        automatic_handoff=False,production_status='NOT_DEPLOYED',
        note='Recorded pre-tamper artifacts are audited; deliberately damaged acceptance runtime copies remain negative evidence.')
    with Path(args.output).open('xb') as stream:stream.write(encode(report))
    print(encode(report).decode())


if __name__=='__main__':main()
