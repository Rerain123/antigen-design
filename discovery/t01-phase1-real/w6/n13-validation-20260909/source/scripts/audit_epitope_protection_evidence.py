"""Read-only N13 evidence audit, independent identity and arithmetic checks."""
import argparse
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode,encode,sha

def audit(batch):
    index=decode((batch/'index.json').read_bytes());assert index['status']=='PASS'
    for row in index['files']:
        path=batch/row['path'];assert path.resolve().is_relative_to(batch.resolve())
        raw=path.read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256'],row['path']
    artifacts=0;paired=0;predictors=0
    for case in index['cases']:
        folder=batch/'cases'/case['case'];job=decode((folder/'job.json').read_bytes())
        for ref in job['artifacts']:
            raw=(folder/'artifacts'/ref['artifact_id']).read_bytes();assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes'];artifacts+=1
        if not job['artifacts']:continue
        v=decode((folder/'result.json').read_bytes());ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert v==decode((folder/'artifacts'/ref['artifact_id']).read_bytes())
        assert not v['usable_for_pipeline'] and not v['automatic_handoff'] and v['scientific_signoff'] is None
        assert v['production_status']=='NOT_DEPLOYED'
        assert all(v['binding'][k]==job[k] for k in ('job_id','run_id','attempt_id','execution_profile'))
        if case['tool_id']=='t01.real.bepipred':
            assert job['state']=='succeeded' and v['execution']['exit_code']==0;predictors+=1
        if case['tool_id']=='t01.real.epitope_protection':
            if job['state']!='succeeded':assert v['protection'] is None;continue
            for row in v['protection']['records']:
                assert sha(row['sequence'].encode())==row['sequence_sha256']
                assert row['source_states']['variant']['sequence_sha256']==row['sequence_sha256']
                obs=row['observation'];assert obs['scientific_pass'] is None and obs['formal_structural_preservation'] is None and obs['formal_prediction_preservation'] is None
                assert obs['l3']['shape_similarity']['value'] is None and obs['l3']['functional_rmsd'] is None
                paired+=1
    report=decode((batch/'cases/real24-report-linked/result.json').read_bytes())['report']
    assert report['outcome']=='ALL_EXCLUDED' and len(report['records'])==24 and report['best_candidate'] is None
    assert all(r['n13'] and r['disposition']=='EXCLUDED' and any(e['code']=='R35_DETERIORATION_EXCEEDED' for e in r['exclusion_reasons']) for r in report['records'])
    actual=decode((batch/'cases/real-paired-n06-hotspots-unavailable/result.json').read_bytes())['protection']['records'][0]
    assert actual['source_states']['wt']['sequence_sha256']!=actual['source_states']['variant']['sequence_sha256']
    for side in ('wt','variant'):
        facts=actual['source_states'][side]
        assert facts['source_receipts']['epitope_map']['state']=='available' and facts['hotspots'] is None
        assert facts['hotspot_map_state']['status']=='review_required'
    assert actual['observation']['l1']['value'] is None and actual['observation']['l4']['value'] is None
    geometry=decode((batch/'cases/real-paired-structure-n06/result.json').read_bytes())['protection']['records'][0]
    assert geometry['source_states']['variant']['quality_condition'] is False
    assert geometry['observation']['l2']['value'] is None
    numeric=decode((batch/'numeric-fixture.json').read_bytes());assert numeric['kind']=='SYNTHETIC_CONTRACT_FIXTURE'
    assert [i for i,(a,b) in enumerate(zip(numeric['wt'],numeric['variant']),1) if a!=b]==[2]
    result=numeric['result'];assert result['l1']['value'] is False and result['l1']['identity_fraction']==2/3
    assert result['l2']['value']==0. and result['l3']['hotspot']['value']==0. and result['l4']['value']==0.
    assert predictors==2 and result['scientific_pass'] is None
    return dict(status='PASS',files_verified=len(index['files']),published_artifacts_verified=artifacts,
        pair_records_verified=paired,actual_predictors=2,original_exclusions_retained=24,scientific_protection_pass=None,
        index_sha256=sha((batch/'index.json').read_bytes()))

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    output=Path(args.output);assert not output.exists();value=audit(Path(args.batch))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(encode(value))
    print(encode(value).decode())

if __name__=='__main__':main()
