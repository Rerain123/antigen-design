"""Independent read-only workflow archive and nested package verification."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import zipfile
from audit_local_delivery_evidence import audit as audit_jobs

def sha(raw):return hashlib.sha256(raw).hexdigest()

def package(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist();assert len(names)==len(set(names))
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in names)
        rows=json.loads(z.read('manifest.json'))['files']
        assert len(rows)==len({r['path'] for r in rows})
        assert set(names)=={r['path'] for r in rows}|{'manifest.json'}
        for row in rows:
            data=z.read(row['path']);assert sha(data)==row['sha256'] and len(data)==row['size_bytes']
        data=json.loads(z.read('workflow.json'))
        assert not data['usable_for_pipeline'] and not data['automatic_handoff']
        assert data['scientific_gate']=='CLOSED' and data['production_status']=='NOT_DEPLOYED'
        assert data['md']=='EXCLUDED'
        if 'local-delivery.zip' in names:
            with zipfile.ZipFile(io.BytesIO(z.read('local-delivery.zip'))) as nested:
                report=json.loads(nested.read('data.json'))
                from audit_local_delivery_evidence import package as verify_delivery
                verify_delivery(z.read('local-delivery.zip'),report)
        return data

def audit(root):
    base=audit_jobs(root);index=json.loads((root/'index.json').read_bytes());flows=[]
    for case in index['cases']:
        folder=root/'cases'/case['case'];j=json.loads((folder/'job.json').read_bytes())
        if j['tool_id']!='t01.real.local_workflow':continue
        result=json.loads((folder/'result.json').read_bytes());view=json.loads((folder/'query.json').read_bytes())
        assert view['job']==j and result['scientific_gate']=='CLOSED'
        children=[r['job_id'] for r in view['nodes'].values() if r.get('job_id')]
        assert len(children)==len(set(children))
        for name,row in view['nodes'].items():
            if not row.get('job_id'):continue
            child=json.loads((root/'cases'/(case['case']+'--'+name)/'job.json').read_bytes())
            assert row['job_id']==child['job_id'] and row['state']==child['state'] and row['artifacts']==child['artifacts']
            if row['origin']=='NEW_EXECUTION':assert child['run_id']==j['run_id']
            else:assert row['origin']=='HISTORICAL_REUSE'
        assert view['nodes']['design']['reason_code']=='SCIENTIFIC_GATE_CLOSED'
        ref=next(r['artifact'] for r in result['raw_artifacts'] if r['path']=='output/package.zip')
        packaged=package((folder/'artifacts'/ref['artifact_id']).read_bytes())
        assert packaged['nodes']==view['nodes']
        flows.append(dict(case=case['case'],children=len(children),new_executions=sum(r.get('origin')=='NEW_EXECUTION' for r in view['nodes'].values())))
    fresh=json.loads((root/'cases/fresh-structure-predictors-report/query.json').read_bytes())
    for n in ('structure','topology','bepipred'):
        assert fresh['nodes'][n]['origin']=='NEW_EXECUTION' and fresh['nodes'][n]['state']=='succeeded'
        value=json.loads((root/'cases'/('fresh-structure-predictors-report--'+n)/'result.json').read_bytes())
        ex=value['execution']
        assert ex['exit_code']==0 and ex['stopped_confirmed'] is True
        assert len(ex['container_id'])==64 and ex['image_id'].startswith('sha256:')
        recorded=json.loads((root/'cases'/('fresh-structure-predictors-report--'+n)/'execution.json').read_bytes())
        assert recorded['container_started'] is True and recorded['tree_stopped'] is True
        assert recorded['container_id']==ex['container_id']
    retained=json.loads((root/'cases/historical-24-retained-exclusions--local_delivery/result.json').read_bytes())['delivery']
    assert retained['outcome']=='ALL_EXCLUDED' and retained['variant_report']['summary']['excluded']==24
    assert all(r['disposition']=='EXCLUDED' and r['exclusion_reasons'] for r in retained['variant_report']['records'])
    base.update(workflows=flows,new_real_model_execution=True,original_24_exclusions_preserved=True)
    return base

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);a=p.parse_args()
    print(json.dumps(audit(a.archive),ensure_ascii=False,indent=2))
