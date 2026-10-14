"""Fresh resident calculations in Linux. Engineering evidence, never signoff.

The operator supplies a fresh runtime and output directory on a shared volume.
Original 24 design candidates are neither read nor recalculated.
"""
import argparse
from pathlib import Path
import time

from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import REPO, encode, sha, TERMINAL
from t01_phase1_real.development import Runtime
from structure_integration_cases import cases, metadata, UBQ
from run_developability_acceptance import request as n10_request


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else encode(value))


def mcp_workflow(rt,body,raw,output):
    import base64,json,secrets,threading,urllib.request,urllib.error,io,zipfile
    from t01_phase1_real.service_api.app import Service,ServiceConfig,Credentials,ALL_SCOPES
    from t01_phase1_real.service_api.transport import Phase1RealServiceServer,MCPApplication
    token=secrets.token_urlsafe(40)
    credentials=Credentials.from_document(dict(credentials=[dict(token=token,principal='resident-engineering',scopes=sorted(ALL_SCOPES))]))
    service=Service(ServiceConfig(runtime_root=rt.root),credentials)
    server=Phase1RealServiceServer(('127.0.0.1',0),service)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='http://127.0.0.1:'+str(server.server_port)+'/mcp'
    counter=0
    def rpc(method,params):
        nonlocal counter
        counter+=1
        request=urllib.request.Request(url,data=encode(dict(jsonrpc='2.0',id=counter,method=method,params=params)),
            headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream','Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,timeout=65) as response:value=json.load(response)
        assert 'error' not in value,value
        return value['result']
    def tool(name,args):
        value=rpc('tools/call',dict(name=MCPApplication.TOOL_PREFIX+name,arguments=args))
        assert not value.get('isError'),value
        return value['structuredContent']
    try:
        try:urllib.request.urlopen(urllib.request.Request(url,data=b'{}',headers={'Content-Type':'application/json'}))
        except urllib.error.HTTPError as exc:assert exc.code==401
        else:raise AssertionError('Missing authentication was accepted')
        write(output/'mcp-initialize.json',rpc('initialize',dict(protocolVersion='2025-06-18',capabilities={},clientInfo=dict(name='resident-engineering',version='1'))))
        tools=rpc('tools/list',{});assert len(tools['tools'])==8;write(output/'mcp-tools.json',tools)
        upload=tool('structure.upload',dict(name='1UBQ.cif',media_type='chemical/x-cif',content_base64=base64.b64encode(raw).decode()))
        write(output/'mcp-upload.json',upload)
        args=dict(request_json=encode(body).decode(),idempotency_key='resident-workflow',structure_upload_id=upload['upload_id'])
        job=tool('workflow.submit',args);write(output/'mcp-submit.json',job)
        assert tool('workflow.submit',args)['job_id']==job['job_id']
        deadline=time.monotonic()+3600
        seen=None
        while not job['terminal'] and time.monotonic()<deadline:
            job=tool('workflow.wait',dict(job_id=job['job_id'],timeout_seconds=30))
            view=tool('workflow.get',dict(job_id=job['job_id']))
            progress=str(view.get('nodes',view.get('state')))
            if progress!=seen:print('MCP progress',progress[:1600],flush=True);seen=progress
        write(output/'mcp-final.json',job)
        assert job['state']=='succeeded',job
        report=tool('workflow.report',dict(job_id=job['job_id']))
        blob=base64.b64decode(report.pop('content_base64'),validate=True)
        assert len(blob)==report['size_bytes'] and sha(blob)==report['sha256']
        def check_zip(data):
            count=0
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                assert archive.testzip() is None
                for name in archive.namelist():
                    part=archive.read(name);count+=1
                    if name.endswith('.zip'):count+=check_zip(part)
            return count
        write(output/'download.zip',blob);write(output/'report.md',report['report_markdown'].encode())
        write(output/'mcp-report.json',report)
        write(output/'mcp-verification.json',dict(status='PASS',authenticated=True,missing_auth_status=401,tool_count=8,
            idempotent=True,report_sha256=sha(blob),zip_members_recursive=check_zip(blob),actual_himat=False))
        owner_runtime=service.runtime(credentials.authenticate('Bearer '+token))
        return owner_runtime,owner_runtime.get(job['job_id'])
    finally:
        server.shutdown();server.server_close();service.shutdown();thread.join(5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',choices=['n10','workflow','gpu-foldx','databases'],required=True)
    args=parser.parse_args()
    assert not args.root.exists() and not args.output.exists()
    args.output.mkdir(parents=True)
    rt=Runtime(args.root)
    rows=[]
    def save(name,job):
        job=rt.get(job['job_id']);folder=args.output/name
        write(folder/'job.json',job);write(folder/'execution.json',rt.execution(job['job_id']))
        write(folder/'request.json',rt._request_bytes(job));write(folder/'events.json',rt.events(job['job_id']))
        value=rt.result(job['job_id']) if job['artifacts'] else None
        if value:write(folder/'result.json',value)
        for ref in job['artifacts']:
            raw=rt.artifact_bytes(job['job_id'],ref['artifact_id'])
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
            write(folder/'artifacts'/ref['artifact_id'],raw)
        row=dict(case=name,job_id=job['job_id'],state=job['state'],error_code=job['error_code'],artifacts=len(job['artifacts']))
        rows.append(row);print(encode(row).decode(),flush=True)
        assert not job['usable_for_pipeline']
        return value
    def finish(name,job):
        deadline=time.monotonic()+1800
        while job['state'] not in TERMINAL and time.monotonic()<deadline:
            job=rt.dispatch(job['job_id']) if job['state']=='queued' or job['tool_id']=='t01.real.local_workflow' else rt.reconcile(job['job_id'])
            if job['state'] not in TERMINAL:time.sleep(.3)
        value=save(name,job)
        assert job['state']=='succeeded',(name,job['state'],job['error_code'])
        return rt.get(job['job_id']),value
    if args.case=='n10':
        fixture=next(c for c in cases() if c['name']=='normal-cif')
        j,v=finish('structure',rt.submit_structure(encode(fixture['request']),'resident-n10-structure',fixture['data']))
        body=n10_request(fixture['request']['protein_sequence'],dict(state='available',artifact=next(r for r in j['artifacts'] if r['role']=='result'),reason_code=None),timeout_seconds=60)
        j,v=finish('n10',rt.submit_sequence(encode(body),'resident-n10','t01.real.developability'))
        assert v['steps']['aggregation']['execution']['status']=='executed',v['steps']['aggregation']['execution']
        assert v['steps']['aggregation']['execution']['command']['runtime']=='resident-process'
        assert v['steps']['ph_stability']['execution']['status']=='executed'
        assert v['developability']['overall_score'] is None
    elif args.case=='databases':
        import shutil
        from run_homology_acceptance import make_database
        from run_blast_acceptance import SEQ
        dbroot=Path('/var/lib/t01/databases')
        source=REPO/'discovery/t01-phase1-real/w2/blast-integration-20260907/acceptance-r03/databases/engineering-n03'
        target=dbroot/'blast/engineering-n03';shutil.copytree(source,target)
        rt=Runtime(args.root,blast_database_root=dbroot/'blast',homology_database_root=dbroot/'homology')
        body=dict(protein_sequence=SEQ,user_sequence_id='resident-engineering-database',database_id='engineering-n03',
                  database_manifest_sha256=sha((target/'manifest.json').read_bytes()),
                  thresholds=dict(identity_percent_min=70.0,query_coverage_percent_min=80.0),timeout_seconds=60)
        finish('blast',rt.submit_sequence(encode(body),'resident-blast','t01.real.blast'))
        body,folder=make_database(dbroot/'homology',database_id='resident-engineering-n08')
        finish('homology',rt.submit_sequence(encode(body),'resident-homology','t01.real.homology'))
        write(args.output/'database-origin.json',dict(qualification='ENGINEERING_FIXTURE',target_database=False,
              blast_source=str(source),blast_manifest_sha256=sha((target/'manifest.json').read_bytes()),
              homology_manifest_sha256=sha((folder/'manifest.json').read_bytes())))
    elif args.case=='gpu-foldx':
        from run_proteinmpnn_acceptance import request as mpnn_request
        from run_thermompnn_acceptance import request as thermo_request
        from run_foldx_acceptance import scan_request
        from structure_integration_cases import SEQUENCE
        raw=(REPO/'discovery/t01-phase1-real/w5/esm-if1-assets-20260908/reference.pdb').read_bytes()
        structure_body=metadata(fmt='PDB',source='unknown')
        j,v=finish('structure',rt.submit_structure(encode(structure_body),'resident-new-engineering-structure',raw))
        ref=next(r for r in j['artifacts'] if r['role']=='result')
        body=mpnn_request(SEQUENCE,ref,'resident-new-one-sample',n_designs=1,seed=31)
        j,v=finish('proteinmpnn',rt.submit_sequence(encode(body),'resident-one-sample','t01.real.proteinmpnn'))
        n11=next(r for r in j['artifacts'] if r['role']=='result')
        body=dict(protein_sequence=SEQUENCE,user_sequence_id='resident-new-one-rescore',structure_artifact=ref,
                  n11_artifact=n11,sample_numbers=[1],baseline_artifact=None,timeout_seconds=180)
        finish('esm-if1',rt.submit_sequence(encode(body),'resident-one-rescore','t01.real.esm_if1'))
        finish('thermompnn',rt.submit_sequence(encode(thermo_request(ref)),'resident-new-ssm','t01.real.thermompnn'))
        finish('foldx',rt.submit_sequence(encode(scan_request(ref)),'resident-new-positionscan','t01.real.foldx'))
    else:
        from t01_phase1_real.development.workflow import policy
        body=dict(protein_sequence=UBQ,user_sequence_id='resident fresh workflow engineering',host_species='Homo sapiens',
                  expression_host=None,organism=None,structure=None,analysis={n:None for n in policy.OPTIONS},reuse_jobs={},timeout_seconds=3600)
        meta=metadata(sequence=UBQ,host_species=body['host_species'],source_declaration=dict(kind='experimental',note='Local 1UBQ, fresh resident engineering execution'))
        body['structure']={k:v for k,v in meta.items() if k not in ('protein_sequence','host_species')}
        body['analysis'].update(topology=dict(timeout_seconds=600),bepipred=dict(timeout_seconds=900),
            netmhc=dict(mhc_i_alleles=['HLA-A02:01'],mhc_ii_alleles=['HLA-DPA10202-DPB11901'],timeout_seconds=600),
            developability=dict(target_ph=None,target_ph_range=[4.0,8.0],dimension_weights=None,timeout_seconds=60))
        raw=(REPO/'tests/fixtures/structure_mapping/real/1UBQ.cif').read_bytes()
        rt,j=mcp_workflow(rt,body,raw,args.output)
        v=save('workflow',j)
        view=rt.workflow(j['job_id']);write(args.output/'query.json',view)
        for name,row in view['nodes'].items():
            if row.get('job_id'):save('node-'+name,rt.get(row['job_id']))
        for name in ('structure','topology','bepipred','netmhc','developability','epitope_map','glycosylation','local_delivery'):
            assert view['nodes'][name]['state']=='succeeded',(name,view['nodes'][name])
        for item in v['raw_artifacts']:
            if item['path'] in ('output/workflow-report.md','output/package.zip'):
                write(args.output/Path(item['path']).name,rt.artifact_bytes(j['job_id'],item['artifact']['artifact_id']))
    write(args.output/'summary.json',dict(status='PASS',boundary='LOCAL_RESIDENT_ENGINEERING',cases=rows,
        scientific_gate='CLOSED',production_status='NOT_DEPLOYED',original_24_rerun=False))


if __name__=='__main__':main()
