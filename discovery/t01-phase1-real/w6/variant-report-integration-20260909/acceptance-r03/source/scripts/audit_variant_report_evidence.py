"""Read-only evidence verification with independent R35/FoldX arithmetic checks."""
import argparse
import math
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode,encode,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    batch=Path(a.batch).absolute();output=Path(a.output).absolute();assert not output.exists()
    index=decode((batch/'index.json').read_bytes());assert index['status']=='PASS'
    for item in index['files']:
        path=batch/item['path'];assert path.resolve().is_relative_to(batch)
        raw=path.read_bytes();assert len(raw)==item['bytes'] and sha(raw)==item['sha256'],item['path']
    artifacts=0
    for case in index['cases']:
        folder=batch/'cases'/case['case'];job=decode((folder/'job.json').read_bytes())
        for ref in job['artifacts']:
            raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];artifacts+=1
        if job['artifacts']:
            value=decode((folder/'result.json').read_bytes())
            ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
            assert value==decode((folder/'artifacts'/ref['artifact_id']).read_bytes())
            assert all(value['binding'][k]==job[k] for k in ('job_id','run_id','attempt_id','request_id','execution_profile','rule_profile'))
            assert not value['usable_for_pipeline'] and not value['automatic_handoff']
            assert value['qualification']=='DEVELOPMENT_UNREVIEWED' and value['production_status']=='NOT_DEPLOYED'
            if case['state']!='succeeded':assert value['report'] is None
    report=decode((batch/'cases/real-24-all-excluded/result.json').read_bytes())['report']
    assert report['outcome']=='ALL_EXCLUDED' and report['best_candidate'] is None and len(report['records'])==24
    assert len({r['sample_number'] for r in report['records']})==24
    for row in report['records']:
        assert row['disposition']=='EXCLUDED' and row['esm_if1']['delta_pct'] < -20
        assert any(r['code']=='R35_DETERIORATION_EXCEEDED' for r in row['exclusion_reasons'])
        assert sha(row['sequence'].encode())==row['sequence_sha256'] and row['foldx'] is None
        assert row['scientific_ranking'] is None and row['missing_conditions']
    folder=batch/'cases/real-foldx-three-bound';value=decode((folder/'result.json').read_bytes())
    report=value['report'];assert len(report['records'])==3
    raw={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
    req=decode(raw['input/foldx-request.json']);wt=req['protein_sequence']
    native=next(data for name,data in raw.items() if name.startswith('input/foldx-native/output/buildmodel/Dif_'))
    table=native.decode().splitlines();header=next(i for i,line in enumerate(table) if line.startswith('Pdb\t'))
    columns=table[header].split('\t');energy=columns.index('total energy');native_values={}
    for line in table[header+1:]:
        if not line.strip():continue
        parts=line.split('\t');_,index_number,run=parts[0].rsplit('_',2)
        native_values.setdefault(int(index_number),[]).append(float(parts[energy]))
    by_id={r['id']:r for r in report['records']}
    for i,declared in enumerate(req['variants'],1):
        row=by_id[declared['variant_id']];chars=list(wt)
        for mutation in declared['mutations']:
            assert wt[mutation['position']-1]==mutation['wt'];chars[mutation['position']-1]=mutation['mut']
        assert row['sequence']==''.join(chars) and sha(row['sequence'].encode())==row['sequence_sha256']
        values=native_values[i];assert len(values)==5
        mean=sum(values)/5;std=math.sqrt(sum((x-mean)**2 for x in values)/5)
        assert abs(mean-row['foldx']['ddg_foldx'])<1e-12 and abs(std-row['foldx']['std'])<1e-12
        assert row['stability_state']=='BOUND_UNREVIEWED' and not row['scientific_eligible']
    fixture=decode((batch/'ranking-fixture.json').read_bytes())
    assert fixture['result']['score_groups']==[dict(score=.89,ids=['a','b'])]
    assert abs(.5*.8+.1*.5+.3*1.3+.1*(1-6/12)-.89)<1e-12
    result=dict(status='PASS',batch=str(batch),index_sha256=sha((batch/'index.json').read_bytes()),
        files_verified=len(index['files']),published_artifacts_verified=artifacts,
        r35_exclusions_verified=24,foldx_variants_verified=3,foldx_native_runs_verified=15,
        fixture_hand_calculation=.89,scientific_release=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(encode(result))
    print(encode(result).decode())

if __name__=='__main__':main()
