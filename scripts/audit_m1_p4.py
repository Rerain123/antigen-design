"""Audit fresh service-owned P4 engineering evidence without scientific promotion."""
import argparse
import io
import json
import zipfile
import hashlib
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import encode
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def read(p):return json.loads(p.read_bytes())


def audit(folder):
    batch=read(folder/'batch.json');snap=read(folder/'workflow-snapshot.json');parent=snap['job'];rows=snap['nodes']
    target=batch.get('database_kind')=='target-nr'
    expected_id='nr-20250624' if target else 'engineering-n03'
    expected_qualification='TARGET_DATABASE_UNREVIEWED' if target else 'ENGINEERING_FIXTURE'
    if target:
        registered=read(folder.parent/'nr-manifest-r01.json')['result']
        verified=read(folder.parent/'nr-hash-r01.json')['result']
        assert verified['status']=='VERIFIED_FULL_SHA256'
        assert registered['manifest_sha256']==verified['manifest_sha256']
        expected_hash='0'*64 if batch['branch']=='failure' else registered['manifest_sha256']
        assert batch['request']['analysis']['blast']['database_manifest_sha256']==expected_hash
    assert parent['job_id']==batch['job_id'] and parent['run_id']==read(folder/'submit.json')['run_id']
    records={n:read(folder/(n+'.json')) for n,r in rows.items() if r.get('job_id')}
    native=zipfile.ZipFile(folder/'native-evidence.zip');manifest=read(folder/'native-evidence-receipt.json')
    assert sha((folder/'native-evidence.zip').read_bytes())==manifest['sha256'] and native.testzip() is None
    count=0
    for n,row in records.items():
        j=row['job'];assert j['run_id']==parent['run_id'] and rows[n]['origin']=='NEW_EXECUTION'
        assert sha(encode(row['request']))==j['request_artifact']['sha256']
        assert j['state'] in ('succeeded','failed','cancelled','timed_out')
        assert not j['usable_for_pipeline']
        for ref in j['artifacts']:
            raw=native.read('artifacts/'+ref['artifact_id']);assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256'];count+=1
        if row.get('result'):
            result=row['result'];assert not result['usable_for_pipeline'] and result['production_status']=='NOT_DEPLOYED'
            ref=next(r for r in j['artifacts'] if r['role'] in ('result','diagnostic'))
            assert json.loads(native.read('artifacts/'+ref['artifact_id']))==result
            assert result['binding']['job_id']==j['job_id'] and result['binding']['run_id']==parent['run_id']
        if row['execution'].get('backend')=='resident-process':
            assert row['execution']['tree_stopped']
            if row['execution'].get('resident_target'):
                assert row['execution']['resident_receipt']['stopped_confirmed']
            else:assert not row['execution'].get('container_started')
    # Every GPU native interval is nonoverlapping within this parent. Global
    # infrastructure/other-run exclusion is independently verified by its guard.
    gpu=[]
    for row in records.values():
        if row['job']['tool_id'] in {'t01.real.'+n for n in ('proteinmpnn','esm_if1','esmfold2','thermompnn','af3')}:
            ex=row['result']['execution'];assert ex['stopped_confirmed']
            assert ex['resident_observation']['network_restriction']=='seccomp-local-sockets-only-v1'
            gpu.append((row['job']['started_at'],row['job']['finished_at'],row['job']['job_id']))
    gpu.sort();assert all(a[1]<=b[0] for a,b in zip(gpu,gpu[1:]))
    if batch['branch']=='failure':
        assert parent['state']=='failed' and parent['error_code']=='HASH_MISMATCH'
        assert rows['blast']['state']=='failed' and rows['design']['job_id'] is None and rows['local_delivery']['job_id'] is None
    else:
        assert parent['state']=='succeeded'
        download=read(folder/'download-verification.json');assert download['job_id']==parent['job_id'] and download['controlled_rest_download']
        assert sha((folder/'workflow.zip').read_bytes())==download['sha256']
        assert sha((folder/'delivery.zip').read_bytes())==download['nested_sha256']
        data=read(folder/'data.json')
        with zipfile.ZipFile(folder/'delivery.zip') as z:
            assert json.loads(z.read('data.json'))==data and z.read('report.md')==(folder/'report.md').read_bytes()
        assert data['scientific_pass'] is None and not data['automatic_handoff'] and data['production_status']=='NOT_DEPLOYED'
        database=records['blast']['result']['database']
        assert database['qualification']==expected_qualification
        assert database['database_id']==expected_id
        if target:
            assert database['manifest_sha256']==registered['manifest_sha256']
            blast=records['blast']['result']
            native=blast['execution']['resident_receipt']['outputs']
            assert 'output/native/blast.txt' in native and 'output/native/database-info.txt' in native
            assert blast['execution']['exit_code']==0 and blast['execution']['stopped_confirmed']
            assert blast['search']['search_status'] in ('hit','no_hit')
            assert blast['search']['iedb_hit'] is None and blast['search']['epitope_regions'] is None
        if batch['branch']=='wt':
            assert rows['design']['job_id'] is None and rows['design']['reason_code']=='R57_LOW_CONFIDENCE_DESIGN_SKIPPED'
            assert all(rows[n]['job_id'] is None for n in ('wt_foldx','wt_thermompnn'))
        else:
            assert records['design']['result']['generation']['generated_count']==24
            assert rows['rescore']['state']=='succeeded' and rows['protection']['state']=='succeeded'
            assert records['variant_report']['result']['report']['m1_test']
            assert all(rows[n]['state']=='succeeded' for n in ('stability','wt_foldx','wt_thermompnn','local_delivery'))
            reps=records['variant_report']['request']['m1_test']['representatives'];assert len(reps)==3
            assert all(rows['rep'+str(i)+'_prediction']['state']=='succeeded' for i in (1,2,3))
            assert data['n16']['reason_code']=='NO_QUALIFIED_CANDIDATE' and data['n16']['dna'] is None
    return dict(status='P4_'+('TARGET' if target else 'ENGINEERING')+'_'+batch['branch'].upper()+'_PASS',job_id=parent['job_id'],run_id=parent['run_id'],
        verified_artifacts=count,native_archive_artifacts=manifest['verified_artifacts'],gpu_intervals=gpu,
        database=expected_id,target_nr_accepted=target and batch['branch']!='failure',p4_m1_complete=False,
        public_report_api_called=False,scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--batch',required=True);a=ap.parse_args()
    folder=ROOT/'discovery/t01-phase1-real/m1-p4-20260922'/a.batch
    result=audit(folder);(folder/'audit-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(result['status'])


if __name__=='__main__':main()
