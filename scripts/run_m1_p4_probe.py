"""Fresh service-owned P4 runs; controlled REST download, no public publication."""
import argparse
import base64
import io
import json
import zipfile
import prepare_m1_p1_deploy as deploy
import run_cluster_workflow_probe as probe
import run_m1_p1_probe as p1

ROOT=deploy.ROOT
BASE=ROOT/'discovery/t01-phase1-real/m1-p4-20260922'
COLLECT=r'''
import json,sys,base64,gzip,io,zipfile,hashlib
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.common import decode
task=json.load(sys.stdin)
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+task['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
job=rt.get(task['job_id']);snapshot=rt.workflow(job['job_id']);records={};native=io.BytesIO();manifest=[]
archive=zipfile.ZipFile(native,'w',zipfile.ZIP_DEFLATED)
def keep(j,ref):
    raw=rt.artifact_bytes(j['job_id'],ref['artifact_id'])
    if job['state'] in ('succeeded','failed','cancelled','timed_out'):
        path='artifacts/'+ref['artifact_id'];archive.writestr(path,raw)
        manifest.append(dict(path=path,artifact=ref,sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw)))
for name,row in snapshot['nodes'].items():
    if not row.get('job_id'):continue
    j=rt.get(row['job_id']);assert j['run_id']==job['run_id']
    r=dict(job=j,request=decode(rt._request_bytes(j)),execution=rt.execution(j['job_id']))
    if j['state'] in ('succeeded','failed','cancelled','timed_out') and j['artifacts']:r['result']=rt.result(j['job_id'])
    for ref in j['artifacts']:keep(j,ref)
    records[name]=r
for ref in job['artifacts']:keep(job,ref)
archive.writestr('manifest.json',json.dumps(dict(files=manifest)));archive.close()
value=dict(snapshot=snapshot,records=records,parent_execution=rt.execution(job['job_id']),
    verified_artifacts=len(manifest),native_archive=base64.b64encode(native.getvalue()).decode() if manifest else None)
print(json.dumps(dict(gzip_base64=base64.b64encode(gzip.compress(json.dumps(value).encode())).decode())))
'''


def main():
    import gzip,re
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['prepare','start','status','collect','download','cancel'])
    ap.add_argument('--batch',default='r01');ap.add_argument('--branch',choices=['design','wt','failure','cancel'],default='design')
    ap.add_argument('--database',choices=['engineering','target-nr'],default='engineering')
    a=ap.parse_args();assert re.fullmatch(r'r[0-9]{2,4}',a.batch)
    out=BASE/a.batch;probe.OUT=out;probe.FIXTURE=out/'1UBQ-m1-test.pdb'
    if a.action=='prepare':
        b,case=p1.request();b['user_sequence_id']='M1 P4 fresh service '+a.branch
        if a.database=='target-nr':
            registered=json.loads((BASE/'nr-manifest-r01.json').read_bytes())['result']
            verified=json.loads((BASE/'nr-hash-r01.json').read_bytes())['result']
            assert verified['status']=='VERIFIED_FULL_SHA256'
            assert registered['manifest_sha256']==verified['manifest_sha256']
            b['analysis']['blast'].update(database_id='nr-20250624',
                database_manifest_sha256=registered['manifest_sha256'],timeout_seconds=7200)
        b['m1_test']['constraints']['source_id']='M1 P4 explicit engineering masks: fixed termini, restricted 2, open 3..75; unknown annotations preserved'
        b['timeout_seconds']=28800
        if a.branch=='wt':
            case=next(c for c in p1.cases() if c['name']=='original-1ubq-pdb')
            b['protein_sequence']=case['request']['protein_sequence']
            b['structure']={k:v for k,v in case['request'].items() if k not in ('protein_sequence','host_species')}
        if a.branch=='failure':b['analysis']['blast']['database_manifest_sha256']='0'*64
        out.mkdir(parents=True,exist_ok=False);probe.FIXTURE.write_bytes(case['data'])
        probe.save('batch.json',dict(idempotency_key='m1-p4-20260922-'+a.batch,branch=a.branch,
            database_kind=a.database,
            input_mode='provided',request=b,input_sha256=probe.sha(case['data']),sequence_sha256=probe.sha(b['protein_sequence'].encode())))
        probe.save('input-provenance.json',dict(original=case['expected'].get('reference'),fixture=case['name'],
            derivative_sha256=probe.sha(case['data']),
            database_identity='TARGET_DATABASE_UNREVIEWED / nr-20250624' if a.database=='target-nr'
                else 'ENGINEERING_FIXTURE / engineering-n03',
            scientific_reference=False,historical_results_used=False,formal_database_connected=False,
            target_database_connected=a.database=='target-nr'))
        print('PREPARED',out);return
    batch=json.loads((out/'batch.json').read_bytes())
    if a.action=='start':probe.start(batch)
    elif a.action=='status':probe.status(batch)
    elif a.action=='cancel':
        probe.save('cancel.json',probe.tool(batch,'workflow.cancel',dict(job_id=batch['job_id'],idempotency_key=batch['idempotency_key']+'-stop')))
    elif a.action=='collect':
        value=json.loads(gzip.decompress(base64.b64decode(deploy.remote(COLLECT,batch)['gzip_base64'])))
        probe.save('workflow-snapshot.json',value['snapshot']);probe.save('parent-execution.json',value['parent_execution'])
        for name,row in value['records'].items():probe.save(name+'.json',row)
        if value['native_archive']:
            raw=base64.b64decode(value['native_archive'],validate=True)
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                assert z.testzip() is None
                for row in json.loads(z.read('manifest.json'))['files']:
                    data=z.read(row['path']);assert len(data)==row['size_bytes'] and probe.sha(data)==row['sha256']==row['artifact']['sha256']
            (out/'native-evidence.zip').write_bytes(raw)
            probe.save('native-evidence-receipt.json',dict(verified_artifacts=value['verified_artifacts'],sha256=probe.sha(raw),bytes=len(raw)))
        print('COLLECTED',len(value['records']),value['snapshot']['job']['state'])
    else:
        value=probe.status(batch);assert value['state']=='succeeded'
        receipt=probe.remote(dict(action='download',owner=batch['owner'],job_id=batch['job_id']))['result']
        raw=base64.b64decode(receipt['content_base64'],validate=True);assert probe.sha(raw)==receipt['sha256']
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            assert z.testzip() is None
            for item in json.loads(z.read('manifest.json'))['files']:assert probe.sha(z.read(item['path']))==item['sha256']
            nested=z.read('local-delivery.zip')
        with zipfile.ZipFile(io.BytesIO(nested)) as z:
            assert z.testzip() is None
            for item in json.loads(z.read('manifest.json'))['files']:assert probe.sha(z.read(item['path']))==item['sha256']
            data=json.loads(z.read('data.json'))
            (out/'report.md').write_bytes(z.read('report.md'));probe.save('data.json',data)
            (out/'manifest.json').write_bytes(z.read('manifest.json'))
        (out/'workflow.zip').write_bytes(raw);(out/'delivery.zip').write_bytes(nested)
        probe.save('download-verification.json',dict(job_id=batch['job_id'],run_id=value['run_id'],
            sha256=probe.sha(raw),size_bytes=len(raw),nested_sha256=probe.sha(nested),
            controlled_rest_download=True,public_report_api_called=False,formal_database_connected=False,
            target_database_connected=batch.get('database_kind')=='target-nr',
            scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED'))
        print('CONTROLLED_DOWNLOAD_VERIFIED',out)


if __name__=='__main__':main()
