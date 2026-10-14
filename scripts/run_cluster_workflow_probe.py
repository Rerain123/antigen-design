"""User-operated real engineering workflow against the deployed control plane.

start is idempotent for the retained local batch record; status and download do
not start computation. Credentials stay inside the service container. A batch
uses either an uploaded structure or a new explicit local prediction; it does
not rerun historical design candidates or register databases.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
OUT_ROOT=Path(os.environ.get('T01_CLUSTER_PROBE_ROOT', str(ROOT/'.tmp')))
OUT=OUT_ROOT/'cluster-workflow-probe-r01'
FIXTURE=ROOT/'tests/fixtures/structure_mapping/real/1UBQ.cif'
K=['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),
   '--request-timeout=90s','-n','him-ws']
PREFIX='t01_phase1_real_service_v01.tool.'
SEQUENCE='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
INPUT_MODES=('provided','esmfold2','af3')
PREDICTION_TIMEOUT_SECONDS={'esmfold2':600,'af3':2400}

REMOTE=r'''
import base64, hashlib, json, os, sys, urllib.request, urllib.error
from pathlib import Path
def main():
    task=json.load(sys.stdin)
    path=os.environ.get('T01_REAL_SERVICE_CREDENTIALS_FILE')
    doc=json.loads(Path(path).read_bytes()) if path else json.loads(os.environ['T01_REAL_SERVICE_CREDENTIALS_JSON'])
    needed={'query','submit','upload','download','control'}
    rows=[r for r in doc['credentials'] if needed.issubset(r['scopes'])]
    if task.get('owner'):
        rows=[r for r in rows if hashlib.sha256(r['principal'].encode()).hexdigest()==task['owner']]
    if len(rows)!=1:
        print(json.dumps({'probe_error':'Expected one matching operator credential; review principal selection'}));return
    row=rows[0]
    owner=hashlib.sha256(row['principal'].encode()).hexdigest()
    headers={'Authorization':'Bearer '+row['token'],'Content-Type':'application/json','Accept':'application/json'}
    if task['action']=='rpc':
        data=json.dumps(task['payload']).encode()
        request=urllib.request.Request('http://127.0.0.1:18083/mcp',data=data,headers=headers)
    else:
        import re
        if not re.fullmatch(r't01p1r-job-[a-f0-9]{32}',task['job_id']):raise ValueError('Invalid job')
        request=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+task['job_id']+'/report',headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=65) as response:
            raw=response.read(48*1024*1024+1)
            if len(raw)>48*1024*1024:raise ValueError('Response too large')
        result=json.loads(raw) if task['action']=='rpc' else {'content_base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest()}
        print(json.dumps({'owner':owner,'result':result}))
    except urllib.error.HTTPError as exc:
        print(json.dumps({'probe_error':'Service HTTP '+str(exc.code)}))
try:
    main()
except Exception:
    print(json.dumps({'probe_error':'Remote request failed; inspect service/worker status. Credentials were not displayed.'}))
'''


def sha(raw):return hashlib.sha256(raw).hexdigest()


def save(name,value):
    path=OUT/name
    tmp=path.with_suffix(path.suffix+'.pending')
    tmp.write_text(json.dumps(value,ensure_ascii=True,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def request_document(input_mode='provided'):
    if input_mode not in INPUT_MODES:raise ValueError('Unknown input mode')
    body=dict(protein_sequence=SEQUENCE,
        user_sequence_id=(
            'cluster fresh analysis engineering 1UBQ' if input_mode=='provided'
            else f'AF3 local adapter acceptance 1UBQ {input_mode}' if input_mode=='af3'
            else 'first N01-N18 engineering chain ESMFold2 1UBQ'),
        host_species='Homo sapiens',
        expression_host=None if input_mode=='provided' else 'Escherichia coli K-12 W3110',
        organism=None if input_mode=='provided' else 'Homo sapiens',
        structure=dict(structure_name='1UBQ.cif',declared_format='MMCIF',
            source_declaration=dict(kind='experimental',note='UNCHANGED_LOCAL_REAL_INPUT; 1UBQ.cif; fresh cluster engineering test'),
            selection=dict(model_index=0,chain_selector='AUTO'),context_chain_ids=['A'],timeout_seconds=60)
            if input_mode=='provided' else None,
        analysis=dict(topology=dict(timeout_seconds=600),blast=None,bepipred=dict(timeout_seconds=900),
            netmhc=dict(mhc_i_alleles=['HLA-A02:01'],mhc_ii_alleles=['HLA-DPA10202-DPB11901'],timeout_seconds=600),
            homology=None,domains=None,
            developability=dict(target_ph=None,target_ph_range=[4.0,8.0],dimension_weights=None,timeout_seconds=60)),
        reuse_jobs={},timeout_seconds=3600)
    if input_mode in ('esmfold2','af3'):
        body['prediction']=dict(
            engine=input_mode,
            seed=1,
            timeout_seconds=PREDICTION_TIMEOUT_SECONDS[input_mode],
        )
    return body


def input_mode(batch):
    prediction=batch['request'].get('prediction')
    return prediction['engine'] if prediction is not None else 'provided'


def remote(task):
    run=subprocess.run(K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',REMOTE],
        input=json.dumps(task).encode(),capture_output=True,timeout=100)
    if run.returncode:raise RuntimeError('kubectl connection failed. Retry the same command; do not delete batch.json.')
    value=json.loads(run.stdout)
    if 'probe_error' in value:raise RuntimeError(value['probe_error'])
    return value


def rpc(batch,method,params):
    value=remote({'action':'rpc','owner':batch.get('owner'),'payload':{'jsonrpc':'2.0','id':1,'method':method,'params':params}})
    if not batch.get('owner'):
        batch['owner']=value['owner'];save('batch.json',batch)
    result=value['result']
    if 'error' in result:raise RuntimeError('MCP error: '+json.dumps(result['error']))
    return result['result']


def tool(batch,name,arguments):
    result=rpc(batch,'tools/call',{'name':PREFIX+name,'arguments':arguments})
    if result.get('isError'):raise RuntimeError('Tool error: '+json.dumps(result.get('structuredContent',{})))
    return result['structuredContent']


def start(batch):
    mode=input_mode(batch)
    if mode=='provided' and sha(FIXTURE.read_bytes())!=batch['input_sha256']:
        raise RuntimeError('Input changed since this batch was created')
    if mode in ('esmfold2','af3') and batch.get('upload_id'):
        raise RuntimeError(f'{mode} batch must not carry an uploaded structure')
    rpc(batch,'initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'antigen-cluster-probe','version':'1'}})
    if mode=='provided' and not batch.get('upload_id'):
        meta=batch['request']['structure']
        upload=tool(batch,'structure.upload',{'name':meta['structure_name'],
            'media_type':'chemical/x-pdb' if meta['declared_format']=='PDB' else 'chemical/x-cif',
            'content_base64':base64.b64encode(FIXTURE.read_bytes()).decode()})
        if upload['sha256']!=batch['input_sha256']:raise RuntimeError('Uploaded input hash differs')
        batch['upload_id']=upload['upload_id'];save('batch.json',batch)
    args={'request_json':json.dumps(batch['request']),'idempotency_key':batch['idempotency_key']}
    if mode=='provided':args['structure_upload_id']=batch['upload_id']
    job=tool(batch,'workflow.submit',args)
    batch['job_id']=job['job_id'];save('batch.json',batch);save('submit.json',job)
    repeated=tool(batch,'workflow.submit',args)
    if repeated['job_id']!=job['job_id']:raise RuntimeError('Idempotency verification failed')
    print('SUBMITTED',job['job_id'],'state='+job['state']);print('IDEMPOTENCY_PASS')
    print('Run status next. Computation runs on the server after this command exits.')


def status(batch):
    if not batch.get('job_id'):raise RuntimeError('Run start first; interrupted submissions can be resumed with start')
    value=tool(batch,'workflow.get',{'job_id':batch['job_id']})
    save('status.json',value)
    print('JOB',value['job_id'],'STATE',value['state'],'ERROR',value.get('error_code'))
    for name,row in value.get('nodes',{}).items():
        print(name,row.get('state'),row.get('reason_code') or '')
    print('TERMINAL',value.get('terminal'),'REPORT_READY',value.get('report_ready'))
    failed=[name for name,row in value.get('nodes',{}).items() if row.get('state') in ('failed','timed_out','cancelled')]
    if failed:
        print('ATTENTION: unsuccessful nodes:', ', '.join(failed))
        print('Workflow completion/report availability does not mean all scientific nodes passed.')
    return value


def verify_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist())>256*1024**2:raise RuntimeError('ZIP expanded size exceeds probe limit')
        if archive.testzip() is not None:raise RuntimeError('ZIP CRC verification failed')
        return len(archive.infolist())


def download(batch):
    current=status(batch)
    if current['state']!='succeeded':raise RuntimeError('Report is not ready; retain failure status for investigation')
    report=tool(batch,'workflow.report',{'job_id':batch['job_id']})
    if 'content_base64' in report:
        raw=base64.b64decode(report.pop('content_base64'),validate=True)
    else:
        value=remote({'action':'download','owner':batch['owner'],'job_id':batch['job_id']})['result']
        raw=base64.b64decode(value['content_base64'],validate=True)
    if sha(raw)!=report['sha256'] or len(raw)!=report['size_bytes']:raise RuntimeError('Report bytes/hash mismatch')
    members=verify_zip(raw)
    (OUT/'report.zip').write_bytes(raw)
    (OUT/'report.md').write_text(report['report_markdown'],encoding='utf-8')
    save('report-receipt.json',report)
    mode=input_mode(batch)
    save('verification.json',dict(status='DOWNLOAD_VERIFIED',job_id=batch['job_id'],sha256=sha(raw),bytes=len(raw),zip_members=members,
        input_mode=mode,sequence_sha256=sha(batch['request']['protein_sequence'].encode()),actual_himat=False,
        original_24_rerun=False,scientific_gate='CLOSED',scope='FIRST_N01_N18_ENGINEERING_CHAIN_WITH_ESMFOLD2'
            if mode=='esmfold2' else 'FIRST_N01_N18_ENGINEERING_CHAIN_WITH_AF3'
            if mode=='af3' else 'ANALYSIS_ONLY; GPU/FoldX and full A3D execution require separate cases'))
    print('REPORT_DOWNLOADED_AND_VERIFIED',OUT/'report.zip')


def main():
    global OUT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','start','status','download'])
    parser.add_argument('--batch', default='r01', help='Separate retained batch, e.g. r02; never deletes an earlier batch')
    parser.add_argument('--input-mode',choices=INPUT_MODES,default='provided',
        help='Used only when creating a new batch; prediction modes submit no structure upload')
    parser.add_argument('--probe-root', type=Path, default=None,
        help='Explicit local batch root; avoids shell environment-name quoting issues')
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'r[0-9]{2,4}', args.batch):raise ValueError('Batch must be r followed by 2 to 4 digits')
    root = args.probe_root if args.probe_root is not None else OUT_ROOT
    OUT=root/('cluster-workflow-probe-'+args.batch)
    action=args.action
    OUT.mkdir(parents=True,exist_ok=True)
    if action=='prepare':
        if not (OUT/'batch.json').exists():
            request=request_document(args.input_mode)
            value=dict(idempotency_key=('cluster-first-chain-' if args.input_mode=='esmfold2' else 'cluster-analysis-')+uuid4().hex,
                input_mode=args.input_mode,sequence_sha256=sha(request['protein_sequence'].encode()),request=request)
            if args.input_mode=='provided':value['input_sha256']=sha(FIXTURE.read_bytes())
            save('batch.json',value)
        retained=json.loads((OUT/'batch.json').read_bytes())
        print('PREPARED',OUT,'mode='+input_mode(retained),'; no server task submitted.');return
    if not (OUT/'batch.json').exists():raise RuntimeError('Run prepare first')
    batch=json.loads((OUT/'batch.json').read_bytes())
    {'start':start,'status':status,'download':download}[action](batch)


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,KeyError,subprocess.TimeoutExpired,zipfile.BadZipFile) as exc:
        print('STOP:',exc);raise SystemExit(1)
