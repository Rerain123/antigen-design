"""Transactional dependency scheduling over the existing jobs/executions store.

A tick owns the controller only while scheduling/reconciling. Child insertion and
parent linkage share one transaction, fencing cancellation and crash duplicates.
"""
import copy
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from ...common import TERMINAL, RuntimeFault, decode, encode, ensure, new_id, now, sha
from ...files import publish
from ...winprocess import current_identity, alive
from . import policy

def configuration(rt):
    return {n: str(Path(getattr(rt,n)).resolve()) if getattr(rt,n) is not None else None
            for n in ('blast_database_root','homology_database_root','domains_database_root')}

def envelope(run, ref, worker, key):
    return dict(contract_version='0.1.0',run_id=run,request_id=new_id('request'),idempotency_key=key,
                tool_id=worker.TOOL,node_id=worker.NODE,run_mode='g0_probe',request_artifact=ref,
                execution_profile=worker.registered_profile(),
                rule_profile=worker.registered_rules() if hasattr(worker,'registered_rules') else None)

def submit(rt, raw, key, structure_data=None):
    body = policy.request(raw)
    ensure('configuration' not in body, 'INVALID_REQUEST', 'Internal configuration cannot be supplied')
    from ..structure import policy as sp
    ensure((body['structure'] is None) == (structure_data is None), 'INVALID_REQUEST', 'Structure metadata and bytes must be supplied together')
    if structure_data is not None:
        ensure(isinstance(structure_data,bytes) and 0 < len(structure_data) <= sp.MAX_STRUCTURE_BYTES,
               'INVALID_REQUEST', 'Structure must be 1 byte..4 MiB')
    config = configuration(rt)
    fingerprint = encode(dict(input_sha256=sha(raw),structure_sha256=sha(structure_data) if structure_data is not None else None,configuration=config))
    with rt._tx() as db:
        def action():
            run = dict(contract_version='0.1.0',run_id=new_id('run'),created_at=now())
            db.execute('INSERT INTO runs VALUES(?,?,?)',(run['run_id'],rt.scope,encode(run).decode()))
            ref = None
            if structure_data is not None:
                aid = new_id('artifact'); path = f'runs/{run["run_id"]}/inputs/{aid}.structure'
                ref = rt._artifact(aid,run['run_id'],None,None,'input',structure_data)
                ref.update(evidence_kind='LOCAL_INPUT',media_type='application/octet-stream')
                publish(rt.root,path,structure_data)
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,run['run_id'],path,encode(ref).decode()))
            staged = dict(body,structure_artifact=ref,configuration=config)
            ref = rt._stage(db,run['run_id'],encode(staged),policy.TOOL)
            req = envelope(run['run_id'],ref,policy,key)
            rt._admit(db,req)
            return rt._new_job(db,req,encode(req))
        return rt._idempotent(db,'local_workflow',key,fingerprint,action)

def worker(name):
    from ..registry import spec
    from ..wt_draft.policy import PRODUCERS
    tool = PRODUCERS.get(name, 't01.real.' + name)
    return spec(tool)

def source(rt, row):
    if not row or not row.get('job_id'): return None
    j = rt.get(row['job_id'])
    return dict(job_id=j['job_id'],artifact=next((r for r in j['artifacts'] if r['role'] in ('result','diagnostic')),None))

def verified(rt, body, name, jid):
    j = rt.get(jid)
    ensure(j['tool_id'] == worker(name).TOOL and j['run_mode'] == 'g0_probe' and not j['usable_for_pipeline'],
           'FORBIDDEN', 'Workflow child producer or qualification differs')
    request_raw = rt._request_bytes(j); req = decode(request_raw)
    ensure(req.get('protein_sequence') == body['protein_sequence'], 'OUTPUT_INVALID', 'Workflow child sequence differs')
    ensure(req.get('host_species') in (None,body['host_species']), 'OUTPUT_INVALID', 'Workflow child host differs')
    for ref in j['artifacts']: rt.artifact_bytes(jid,ref['artifact_id'])
    s = source(rt,dict(job_id=jid))
    if s['artifact']:
        with rt._db() as db: _,_,value = rt._registered_result_artifact(db,s['artifact'],worker(name).TOOL)
        ensure(value['binding'].get('input_sha256') == sha(request_raw)
               and value['binding'].get('sequence_sha256') == sha(body['protein_sequence'].encode())
               and value.get('qualification') == 'DEVELOPMENT_UNREVIEWED'
               and value.get('scientific_signoff') is None and value.get('production_status') == 'NOT_DEPLOYED',
               'OUTPUT_INVALID', 'Workflow child binding or signoff differs')
    return j

def typed(rt, rows, name):
    s = source(rt,rows.get(name))
    if s is None or s['artifact'] is None: return dict(state='not_provided',artifact=None,reason_code=None)
    j = rt.get(s['job_id'])
    return dict(state='available' if j['state']=='succeeded' else 'upstream_unavailable',
                artifact=s['artifact'],reason_code=j['error_code'])

def request_for(rt, b, rows, name):
    base = dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],timeout_seconds=30)
    if name == 'structure':
        if b['structure'] is None: return None, 'PREDICTION_SERVICE_NOT_DEPLOYED'
        return dict(b['structure'],protein_sequence=b['protein_sequence'],host_species=b['host_species'],structure_artifact=b['structure_artifact']), None
    if name in policy.OPTIONS:
        opt = b['analysis'][name]
        if opt is None:
            return None, 'ALLELE_PANEL_NOT_PROVIDED' if name=='netmhc' else 'DATABASE_NOT_PROVIDED' if name in ('blast','homology','domains') else 'NOT_REQUESTED'
        req = dict(base,**opt)
        if name=='netmhc': req['host_species']=b['host_species']
        if name in ('domains','developability'): req['structure_input']=typed(rt,rows,'structure')
        if name=='domains': req['topology_input']=typed(rt,rows,'topology')
        return req,None
    if name=='epitope_map':
        inputs={n+'_input':typed(rt,rows,n) for n in ('bepipred','netmhc','blast')}
        if inputs['blast_input']['state']=='not_provided':
            inputs['blast_input']=dict(state='not_executed',artifact=None,reason_code='WORKFLOW_BLAST_NOT_EXECUTED')
        return dict(base,**inputs),None
    if name=='glycosylation':
        n06=rows.get('epitope_map',{})
        hotspot=rt.n06_hotspot_input(n06['job_id'],b['protein_sequence']) if n06.get('state')=='succeeded' else dict(state='not_provided',hotspots=None,source=None,reason_code=None)
        return dict(base,hotspot_input=hotspot),None
    if name=='wt_draft':
        return dict(base,host_species=b['host_species'],organism=b['organism'],
                    upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    if name in ('design','rescore','protection','stability'): return None,'SCIENTIFIC_GATE_CLOSED'
    if name=='variant_report':
        return dict(base,variant_source='N11_DESIGN_AUDIT',upstream=dict(design_audit=None,foldx=None),foldx_bindings=[]),None
    if name=='codon': return None,'EXPRESSION_HOST_NOT_PROVIDED' if b['expression_host'] is None else 'NO_ELIGIBLE_SEQUENCE'
    if name=='wt_reference':
        return dict(base,upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    if name=='local_delivery':
        return dict(base,host_species=b['host_species'],expression_host=b['expression_host'],dna_bindings=[],
                    upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    raise RuntimeFault('INVALID_REQUEST','Unknown workflow node')

def _record(rt, jid, name, row):
    with rt._tx() as db:
        j=rt._job(db,jid);ex=rt._execution(db,jid)
        if j['state'] in TERMINAL:return
        ex['nodes'][name]=dict(row,node_id=policy.NODES[name])
        rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(j),j,'workflow_node_'+name)

def _create_child(rt, jid, name, req):
    w=worker(name)
    with rt._tx() as db:
        j=rt._job(db,jid);ex=rt._execution(db,jid)
        if j['stop_reason'] or j['state'] in TERMINAL:return None
        body=policy.request(rt._input(db,j['request_artifact'],j['run_id']))
        remaining=body['timeout_seconds']-(datetime.now(timezone.utc)-datetime.fromisoformat(ex['started_at'].replace('Z','+00:00'))).total_seconds()
        if remaining <= 0:
            rt._stop(db,j,'timeout');return None
        req=dict(req,timeout_seconds=min(req['timeout_seconds'],max(1,int(remaining))))
        if name in ex['nodes']:return ex['nodes'][name].get('job_id')
        ref=rt._stage(db,j['run_id'],encode(req),w.TOOL)
        request=envelope(j['run_id'],ref,w,jid+'-'+name)
        rt._admit(db,request)
        child=rt._new_job(db,request,encode(request))
        ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=child['job_id'],state='queued',origin='NEW_EXECUTION',reason_code=None)
        rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(j),j,'workflow_child_submitted')
        return child['job_id']

def stop_children(rt,jid):
    for row in rt.execution(jid).get('nodes',{}).values():
        if row.get('origin')!='NEW_EXECUTION' or not row.get('job_id'):continue
        child=rt.get(row['job_id'])
        if child['state'] not in TERMINAL:
            rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=child['job_id'],idempotency_key=jid+'-stop-'+child['job_id'])))
            rt.reconcile(child['job_id'])

def snapshot(rt,jid,verify=True):
    j=rt.get(jid);ensure(j['tool_id']==policy.TOOL,'INVALID_REQUEST','Workflow task required')
    body=policy.request(rt._request_bytes(j));ex=rt.execution(jid);rows=copy.deepcopy(ex.get('nodes',{}))
    for name,row in rows.items():
        if row.get('job_id'):
            child=verified(rt,body,name,row['job_id']) if verify else rt.get(row['job_id'])
            row.update(state=child['state'],error_code=child['error_code'],attempt_id=child['attempt_id'],
                       request_artifact=child['request_artifact'],execution_profile=child['execution_profile'],
                       rule_profile=child['rule_profile'],artifacts=child['artifacts'])
            row.update(qualification='DEVELOPMENT_UNREVIEWED',scientific_signoff=None,usable_for_pipeline=False)
    for name in policy.ORDER:
        rows.setdefault(name,dict(node_id=policy.NODES[name],job_id=None,state='not_executed',reason_code=j['error_code'] or 'PENDING_DEPENDENCIES'))
    return dict(job=j,nodes=rows,configuration=body['configuration'],sequence_sha256=sha(body['protein_sequence'].encode()),
                qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,
                scientific_gate='CLOSED',scientific_signoff=None,production_status='NOT_DEPLOYED',md='EXCLUDED')

def finish(rt,jid,error=None):
    j=rt.get(jid);ex=rt.execution(jid)
    if j['stop_reason']:
        stop_children(rt,jid)
        if any(rt.get(r['job_id'])['state'] not in TERMINAL for r in ex['nodes'].values()
               if r.get('job_id') and r.get('origin')=='NEW_EXECUTION'):return rt.get(jid)
    data=snapshot(rt,jid,verify=error is None)
    data['parent_at_assembly']=data.pop('job')
    data['report_scope']='Snapshot before terminal publication; query the parent job for current lifecycle state'
    # A stopped or integrity-failed workflow never exports a consumable package.
    files={'output/workflow.json':encode(data)}
    text=['# Local workflow engineering report','','Scientific Gate: CLOSED; DEVELOPMENT_UNREVIEWED; NOT_DEPLOYED.','',
          '| Node | Branch | State | Reason | Origin |','|---|---|---|---|---|']
    for name,row in data['nodes'].items():
        text.append('| '+ ' | '.join(str(v or '') for v in (row['node_id'],name,row['state'],row.get('reason_code') or row.get('error_code'),row.get('origin'))) +' |')
    files['output/workflow-report.md']=('\n'.join(text)+'\n').encode()
    if error is None and not j['stop_reason']:
        contents={'workflow.json':files['output/workflow.json'],'workflow-report.md':files['output/workflow-report.md']}
        delivery=ex['nodes'].get('local_delivery',{})
        if delivery.get('state')=='succeeded':
            value=rt.result(delivery['job_id'])
            ref=next(r['artifact'] for r in value['raw_artifacts'] if r['path']=='output/package.zip')
            contents['local-delivery.zip']=rt.artifact_bytes(delivery['job_id'],ref['artifact_id'])
        contents['manifest.json']=encode(dict(files=[dict(path=n,size_bytes=len(raw),sha256=sha(raw)) for n,raw in sorted(contents.items())]))
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in sorted(contents.items()):
                info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,raw)
        files['output/package.zip']=buf.getvalue()
    binding={k:j[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=j['request_artifact']['sha256'],sequence_sha256=data['sequence_sha256'])
    result=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,
                qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,
                automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',requires_review=True,
                scientific_gate='CLOSED',status='completed_with_gaps' if not error else 'unreliable',
                workflow=data,null_reason=error,warnings=[],execution=dict(error_code=error,exit_code=1 if error else 0,
                    stopped_confirmed=True,network_used=False,backend='local-workflow-controller'))
    ex.update(tree_stopped=True,dispatcher=None)
    return rt._finish_development(jid,ex,files,result)

def dispatch(rt,jid):
    with rt._tx() as db:
        before=rt._job(db,jid)
        if before['state'] in TERMINAL:return before
        body=policy.request(rt._input(db,before['request_artifact'],before['run_id']))
        ex=rt._execution(db,jid)
        owner=ex.get('dispatcher')
        if owner and alive(owner):return before
        if before['state']=='queued':
            j=copy.deepcopy(before)
            j.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
            ex=dict(nodes={},phase='scheduling',tree_stopped=False,started_at=j['started_at'])
            rt._store(db,j,before,'workflow_claimed')
        ex['dispatcher']=current_identity();rt._execution_store(db,jid,ex)
    try:
        ensure(body['configuration']==configuration(rt) and before['execution_profile']==policy.registered_profile(),
               'PROFILE_NOT_APPROVED','Workflow code or local database configuration changed')
        if body['structure_artifact'] is not None:
            with rt._db() as db:rt._structure_bytes(db,body,before['run_id'])
        for name in policy.ORDER:
            j=rt.get(jid);ex=rt.execution(jid)
            elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(ex['started_at'].replace('Z','+00:00'))).total_seconds()
            if elapsed>=body['timeout_seconds'] and not j['stop_reason']:
                with rt._tx() as db:rt._stop(db,rt._job(db,jid),'timeout')
                j=rt.get(jid)
            if j['stop_reason']:return finish(rt,jid)
            rows=ex['nodes'];row=rows.get(name)
            if row and not row.get('job_id'):continue
            if row and row.get('job_id'):
                child=verified(rt,body,name,row['job_id'])
                if child['state'] in TERMINAL:
                    if row['state']!=child['state']:_record(rt,jid,name,dict(row,state=child['state'],reason_code=child['error_code']))
                    continue
                if child['state']=='queued':rt.dispatch(child['job_id'])
                else:rt.recover(child['job_id'])
                child=rt.get(child['job_id'])
                _record(rt,jid,name,dict(row,state=child['state'],reason_code=child['error_code']))
                if child['state'] not in TERMINAL:return rt.get(jid)
                verified(rt,body,name,child['job_id']);continue
            if name in body['reuse_jobs']:
                child=verified(rt,body,name,body['reuse_jobs'][name])
                ensure(child['state']=='succeeded','INVALID_STATE','Historical reuse requires terminal success')
                _record(rt,jid,name,dict(job_id=child['job_id'],state=child['state'],origin='HISTORICAL_REUSE',reason_code=None))
                continue
            try:
                req,reason=request_for(rt,body,rows,name)
                if req is None:
                    _record(rt,jid,name,dict(job_id=None,state='skipped',reason_code=reason,origin=None));continue
                # Recheck every prior source before constructing or admitting a dependent job.
                for upstream,r in rows.items():
                    if r.get('job_id'):verified(rt,body,upstream,r['job_id'])
                child_id=_create_child(rt,jid,name,req)
                if child_id is None:return finish(rt,jid)
                rt.dispatch(child_id)
                child=rt.get(child_id)
                _record(rt,jid,name,dict(job_id=child_id,state=child['state'],reason_code=child['error_code'],origin='NEW_EXECUTION'))
                if child['state'] not in TERMINAL:return rt.get(jid)
            except RuntimeFault as exc:
                if exc.code in ('HASH_MISMATCH','FORBIDDEN','PROFILE_NOT_APPROVED','OUTPUT_INVALID'):raise
                if rt.execution(jid)['nodes'].get(name,{}).get('job_id'):raise
                _record(rt,jid,name,dict(job_id=None,state='blocked',reason_code=exc.code,detail=str(exc),origin=None))
        return finish(rt,jid)
    except RuntimeFault as exc:
        stop_children(rt,jid)
        # Keep active children tracked; subsequent recovery confirms their stop.
        active=any(rt.get(r['job_id'])['state'] not in TERMINAL for r in rt.execution(jid)['nodes'].values()
                   if r.get('job_id') and r.get('origin')=='NEW_EXECUTION')
        if active:return rt.get(jid)
        return finish(rt,jid,exc.code)
    finally:
        with rt._tx() as db:
            ex=rt._execution(db,jid);ex['dispatcher']=None;rt._execution_store(db,jid,ex)
