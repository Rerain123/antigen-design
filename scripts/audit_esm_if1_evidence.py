"""Read-only N12 inventory, pinned source, native losses and baseline provenance audit."""
import argparse
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.esm_if1 import policy
from t01_phase1_real.development.esm_if1.result import validate_observation
from t01_phase1_real.development.esm_if1.rules import evaluate
from t01_phase1_real.development.proteinmpnn.result import parse as parse_mpnn


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();batch=Path(args.batch).absolute();index=decode((batch/'index.json').read_bytes())
    assert index['status']=='PASS' and not Path(args.output).exists()
    failures=[]
    for item in index['files']:
        path=batch/item['path']
        if not path.is_file() or path.stat().st_size!=item['bytes'] or sha(path.read_bytes())!=item['sha256']:failures.append(item['path'])
    snapshots=[p for p in (batch/'source').rglob('*') if p.is_file()]
    changed=[p.relative_to(batch/'source').as_posix() for p in snapshots if p.read_bytes()!=(REPO/p.relative_to(batch/'source')).read_bytes()]
    assert not failures and not changed,(failures,changed)
    assert index['profile']==policy.registered_profile() and decode((batch/'rules.json').read_bytes())==policy.registered_rules()
    assert decode((batch/'assets.json').read_bytes())==policy.verify_assets()
    artifacts=0;native=[];peaks=[];baselines={};reused=[];n11=[]
    for case in index['cases']:
        folder=batch/'cases'/case['case'];job=decode((folder/'job.json').read_bytes())
        assert all(job[k]==case[k] for k in ('job_id','state','error_code','tool_id'))
        for ref in job['artifacts']:
            raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];artifacts+=1
        if not job['artifacts']:continue
        value=decode((folder/'result.json').read_bytes())
        result_ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert value==decode((folder/'artifacts'/result_ref['artifact_id']).read_bytes())
        assert not value['usable_for_pipeline'] and not value['automatic_handoff'] and value['scientific_signoff'] is None
        files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
        if job['tool_id']=='t01.real.proteinmpnn' and value['generation']:
            assert parse_mpnn(decode(files['input.json']),files)==value['generation'];n11.append(case['case'])
        if job['tool_id']!=policy.TOOL:continue
        assert job['execution_profile']==policy.registered_profile() and value['formal_candidates'] is None and value['validation'] is None
        assert value['scientific_gate']=='NOT_EVALUATED' and value['structure_recheck']['status']=='NOT_EXECUTED' and value['mutation_burden'] is None
        if not value['scoring']:continue
        assert all(sha(files[n])==h for n,h in value['source_receipt']['prepared_hashes'].items())
        observed=validate_observation(decode(files['input.json']),files)
        assert value['scoring']==observed and value['baseline']==observed['baseline']
        baseline=observed['baseline'];runtime=decode(files['output/runtime.json'])
        assert value['engineering_rules']==(evaluate(baseline['score'],observed['records']) if baseline else None)
        if baseline:
            if observed['baseline_status']=='computed_once':
                assert baseline['origin_job_id']==job['job_id'];baselines[job['job_id']]=baseline
            else:
                braw=files['input/baseline-result.json'];bresult=decode(braw)
                bref=decode(files['input.json'])['baseline_artifact']
                assert sha(braw)==bref['sha256'] and len(braw)==bref['size_bytes'] and bresult['baseline']==baseline
                reused.append((case['case'],baseline))
        native.append(dict(case=case['case'],baseline_status=observed['baseline_status'],baseline_score=baseline and baseline['score'],
            baseline_model_calls=runtime['baseline_model_calls'],variant_model_calls=runtime['variant_model_calls'],
            scored_count=sum(r['score'] is not None for r in observed['records'])))
        peaks.append(runtime['gpu_peak_allocated_bytes'])
    for name,baseline in reused:assert baselines[baseline['origin_job_id']]==baseline,name
    report=dict(status='PASS',batch=str(batch),index_sha256=sha((batch/'index.json').read_bytes()),files_verified=len(index['files']),
        artifacts_verified=artifacts,source_files_verified=len(snapshots),case_count=len(index['cases']),guard_count=len(index['guards']),
        native_results_reparsed=native,n11_results_reparsed=n11,baseline_origins_verified=len(baselines),baseline_reuses_verified=len(reused),
        max_observed_gpu_peak_allocated_bytes=max(peaks),inventory_failures=failures,source_snapshot_changes=changed,
        current_execution_and_rule_profiles_match=True,scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,
        production_status='NOT_DEPLOYED',complete_n12=False,
        note='Audit uses preserved published bytes; deliberately damaged fresh acceptance runtime copies remain negative evidence.')
    with Path(args.output).open('xb') as stream:stream.write(encode(report))
    print(encode(report).decode())


if __name__=='__main__':main()
