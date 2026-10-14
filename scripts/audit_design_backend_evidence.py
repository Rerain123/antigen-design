"""Read-only file, publication, native-mask and deterministic S27/S28 audit."""
import argparse
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.development.design_backend import policy
from t01_phase1_real.development.design_backend.compute import evaluate
from t01_phase1_real.development.proteinmpnn import policy as mpnn


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();batch=Path(args.batch).absolute();output=Path(args.output)
    assert not output.exists();index=decode((batch/'index.json').read_bytes());assert index['status']=='PASS'
    for item in index['files']:
        data=(batch/item['path']).read_bytes();assert len(data)==item['bytes'] and sha(data)==item['sha256'],item['path']
    snapshots=[p for p in (batch/'source').rglob('*') if p.is_file()]
    for path in snapshots:assert path.read_bytes()==(REPO/path.relative_to(batch/'source')).read_bytes(),str(path)
    assert index['profile']==policy.registered_profile() and decode((batch/'rules.json').read_bytes())==policy.registered_rules()
    scales=decode((policy.HERE/'scales.json').read_bytes())
    for receipt in scales['source_receipts'].values():
        raw=(REPO/receipt['path']).read_bytes();assert sha(raw)==receipt['sha256'] and len(raw)==receipt['bytes']
    from t01_phase1_real.development.design_backend.burden import compute
    numeric=decode((batch/'numeric-fixtures.json').read_bytes())
    for row in numeric:
        assert row['kind']=='SYNTHETIC_NUMERIC_GEOMETRY_FIXTURE'
        assert row['result']==compute(row['wt'],row['record'],row['geometry'],row['domains'],row['hotspots'],'general',scales)
    artifact_count=0;recomputed=[]
    for case in index['cases']:
        folder=batch/'cases'/case['case'];job=decode((folder/'job.json').read_bytes())
        assert all(job[k]==case[k] for k in ('job_id','tool_id','state','error_code'))
        for ref in job['artifacts']:
            data=(folder/'artifacts'/ref['artifact_id']).read_bytes();assert len(data)==ref['size_bytes'] and sha(data)==ref['sha256']
            artifact_count+=1
        if not job['artifacts']:continue
        value=decode((folder/'result.json').read_bytes());ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert value==decode((folder/'artifacts'/ref['artifact_id']).read_bytes())
        assert value['scientific_signoff'] is None and not value['usable_for_pipeline'] and not value['automatic_handoff']
        if job['tool_id']!=policy.TOOL:continue
        assert job['execution_profile']==policy.registered_profile() and value['design_permissions'] is value['mutation_burden'] is value['validation'] is None
        if value['audit'] is None:continue
        files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
        observation=decode(files['output/observation.json'])
        assert observation['input_hashes']=={k:sha(v) for k,v in files.items() if k.startswith('input/')}
        calculated=evaluate(decode(files['input.json']),files)
        assert calculated==value['audit']==observation['result']==decode(files['output/design-audit.json'])
        assert not calculated['model_invoked'] and not calculated['automatic_generation'] and not calculated['n12_disposition_changed']
        recomputed.append(dict(case=case['case'],burden_records=len(calculated['burden_records'] or []),
            fixed_count=len(calculated['permissions']['fixed_positions']),restricted_count=len(calculated['permissions']['restricted_positions']),
            open_count=len(calculated['permissions']['open_positions']),mask_export=calculated['n11_request_draft'] is not None))
    probe=decode((batch/'mask-probe/output/mask-probe.json').read_bytes())
    assert probe['generation_invocations']==0 and probe['model_loaded'] is False and probe['network_interfaces']==[[1,'lo']]
    for name,digest in probe['input_hashes'].items():assert sha((batch/'mask-probe/native'/name).read_bytes())==digest
    assets=decode((mpnn.HERE/'assets.json').read_bytes())
    assert probe['source_hashes']=={r['package_path']:r['sha256'] for r in assets['files']}
    native=batch/'mask-probe/native';body=decode((native/'request.json').read_bytes());conversion=decode((native/'conversion.json').read_bytes())
    target=conversion['target_chain'];order=probe['chain_order'];alphabet='ACDEFGHIKLMNPQRSTVWYX'
    for chain in order:
        start=sum(len(conversion['chain_sequences'][c]) for c in order[:order.index(chain)])
        for p in range(1,len(conversion['chain_sequences'][chain])+1):
            i=start+p-1;assert probe['chain_mask'][i]==int(chain==target)
            if chain==target:
                assert probe['position_mask'][i]==int(p not in body['constraints']['fixed_positions'])
                row=next((r for r in body['constraints']['restricted_positions'] if r['position']==p),None)
                if row:assert {a for a,v in zip(alphabet,probe['omit_mask'][i]) if v==0}==set(row['allowed_residues'])
    report=dict(status='PASS',batch=str(batch),index_sha256=sha((batch/'index.json').read_bytes()),files_verified=len(index['files']),
        artifacts_verified=artifact_count,source_snapshots_verified=len(snapshots),case_count=len(index['cases']),guard_count=len(index['guards']),
        deterministic_results_recomputed=recomputed,numeric_fixtures_recomputed=len(numeric),native_mask_featurizer_verified=True,new_candidate_generations=0,
        current_profile_matches=True,scientific_signoff=None,formal_design=False,formal_burden=False,formal_validation=False,
        usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED')
    with output.open('xb') as stream:stream.write(encode(report))
    print(encode(report).decode())


if __name__=='__main__':main()
