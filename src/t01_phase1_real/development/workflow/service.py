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
from . import engineering

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

def prediction_source(engine):
    if engine == 'esmfold2':
        from ..esmfold2 import source
        return source
    if engine == 'af3':
        from ..af3 import source
        return source
    raise RuntimeFault('INVALID_REQUEST','Unknown prediction engine')


def worker(name, body=None, rows=None):
    from .revision_controller import CHILDREN as REVISION_CHILDREN
    if name in REVISION_CHILDREN:
        from ..registry import spec
        return spec('t01.real.'+REVISION_CHILDREN[name])
    if name=='wt_msa':
        from ..af3 import policy as af3
        return af3
    from .candidate_dna import ORDER as DNA_ORDER
    if name in DNA_ORDER:
        from ..codon import policy as codon
        return codon
    from .candidate_developability import CHILDREN as N10_CHILDREN
    if name in N10_CHILDREN:
        from ..registry import spec
        return spec('t01.real.'+('ingest_structure' if N10_CHILDREN[name]=='structure' else 'developability'))
    from .validation import CHILDREN
    if name in CHILDREN:
        from ..registry import spec
        return spec('t01.real.'+CHILDREN[name])
    if name.startswith('rep') and name.endswith('_prediction') and rows is not None:
        from .m1 import prediction_engine
        from ..registry import spec
        return spec('t01.real.'+prediction_engine(rows,name))
    from .design_rounds import NAMES
    if name in NAMES:name=name[7:]
    if name == 'design_inputs':
        from ..design_backend import policy as audit
        return audit
    from .m1 import KINDS
    if name in KINDS:
        from ..registry import spec
        return spec('t01.real.'+KINDS[name][0])
    if name == 'design':
        from ..proteinmpnn import policy as proteinmpnn
        return proteinmpnn
    if name == 'prediction':
        ensure(body is not None and body.get('prediction') is not None,
               'INVALID_REQUEST','Prediction engine context required')
        if body['prediction']['engine']=='esmfold2':
            from ..esmfold2 import policy as prediction
        else:
            from ..af3 import policy as prediction
        return prediction
    from ..registry import spec
    from ..wt_draft.policy import PRODUCERS
    tool = PRODUCERS.get(name, 't01.real.' + name)
    return spec(tool)

def source(rt, row):
    if not row or not row.get('job_id'): return None
    j = rt.get(row['job_id'])
    return dict(job_id=j['job_id'],artifact=next((r for r in j['artifacts'] if r['role'] in ('result','diagnostic')),None))

def verified(rt, body, name, jid, expected_run_id=None, rows=None):
    j = rt.get(jid)
    expected_sequence=body['protein_sequence']
    if body.get('m1_test') is not None or engineering.enabled(body):
        ensure(expected_run_id is not None and j['run_id']==expected_run_id,
               'FORBIDDEN','M1 upstream belongs to another run')
        from .m1 import sequence
        from .validation import CHILDREN,child_sequence
        expected_sequence=child_sequence(rt,rows or {},name) if name in CHILDREN else sequence(rt,body,rows or {},name)
        from .candidate_developability import CHILDREN as N10_CHILDREN,candidate
        if name in N10_CHILDREN:expected_sequence=candidate(rt,rows or {},name)['sequence']
        from .candidate_dna import ORDER as DNA_ORDER,candidate as dna_candidate
        if name in DNA_ORDER and engineering.enabled(body):expected_sequence=dna_candidate(rt,rows or {},name)[0]['sequence']
    from .revision_runtime import PREDICTIONS,sequence as revision_sequence
    if name in PREDICTIONS:expected_sequence=revision_sequence(rt,rows or {},name)
    from .revision_v2_runtime import CHILDREN as V2_CHILDREN,candidate_sequence
    if name in V2_CHILDREN and V2_CHILDREN[name]!='foldx':expected_sequence=candidate_sequence(rt,rows or {},name)
    ensure(j['tool_id'] == worker(name,body,rows).TOOL and j['run_mode'] == 'g0_probe' and not j['usable_for_pipeline'],
           'FORBIDDEN', 'Workflow child producer or qualification differs')
    request_raw = rt._request_bytes(j); req = decode(request_raw)
    ensure(req.get('protein_sequence') == expected_sequence, 'OUTPUT_INVALID', 'Workflow child sequence differs')
    ensure(req.get('host_species') in (None,body['host_species']), 'OUTPUT_INVALID', 'Workflow child host differs')
    for ref in j['artifacts']: rt.artifact_bytes(jid,ref['artifact_id'])
    s = source(rt,dict(job_id=jid))
    if s['artifact']:
        with rt._db() as db: _,_,value = rt._registered_result_artifact(db,s['artifact'],worker(name,body,rows).TOOL)
        ensure(value['binding'].get('input_sha256') == sha(request_raw)
               and value['binding'].get('sequence_sha256') == sha(expected_sequence.encode())
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


def recoverable_child_failure(body, name, child):
    """Continue declared first-version gaps, never an integrity/identity failure."""
    if name.split('_')[-1]=='netmhc':
        return child.get('error_code') not in ('HASH_MISMATCH','FORBIDDEN','PROFILE_NOT_APPROVED','OUTPUT_INVALID')
    if not engineering.enabled(body):return False
    if child.get('state') not in ('failed','timed_out'):return False
    from .candidate_dna import ORDER as DNA_ORDER
    if name in DNA_ORDER:return child.get('error_code') in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING',
        'UNSUPPORTED_EXPRESSION_HOST','HOST_PROFILE_REQUIRED','CODON_TABLE_MISSING','DEPENDENCY_MISSING')
    if child.get('error_code') not in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'):return False
    from .candidate_developability import CHILDREN as N10_CHILDREN
    if name in N10_CHILDREN:return True
    # S-28 retains the ESM decision after failed variant prediction. N10/N14
    # gaps remain missing in the internal report, never successful calculations.
    return name in ('developability','stability','wt_foldx','wt_thermompnn') or (
        name.startswith(('wt_','rep')) and
        name.split('_',1)[1] in ('prediction','developability'))


def design_applicability(rt,rows):
    row=rows.get('wt_draft') or {}
    if row.get('state')!='succeeded' or not row.get('job_id'):return None
    value=rt.result(row['job_id']);draft=value.get('draft')
    return copy.deepcopy(draft.get('gate')) if isinstance(draft,dict) else None


def design_route_reason(rt,rows):
    gate=design_applicability(rt,rows)
    if gate is None or gate.get('status')=='INPUT_INSUFFICIENT_OR_NOT_EVALUATED':
        return 'DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'
    if gate.get('status')=='NOT_SUITABLE_FOR_DESIGN':
        return 'R57_MEMBRANE_DESIGN_SKIPPED' if gate.get('design_skip_reason')=='membrane_expected_poor' \
            else 'R57_LOW_CONFIDENCE_DESIGN_SKIPPED'
    if gate.get('status')=='SUITABLE_FOR_DESIGN':return 'SCIENTIFIC_CONSUMPTION_NOT_RELEASED'
    return 'DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'


def m1_design_reason(rt, rows):
    reason=design_route_reason(rt,rows)
    if reason!='SCIENTIFIC_CONSUMPTION_NOT_RELEASED':return reason
    gate=design_applicability(rt,rows)
    # The first M1 path covers the known soluble/high-or-medium-quality domain.
    # Confirmed membrane/low-confidence variants need their specific masks later.
    if gate.get('constraints'):return 'M1_DESIGN_DOMAIN_NOT_SUPPORTED'
    if (rows.get('structure') or {}).get('state')!='succeeded':return 'STRUCTURE_UNAVAILABLE'
    return None


def m1_inputs(rt, body, rows):
    """Bound facts and explicit gaps, not automatic scientific permissions."""
    from ..wt_draft.policy import PRODUCERS
    inputs={name:dict(state=(rows.get(name) or {}).get('state','not_executed'),
        reason_code=(rows.get(name) or {}).get('reason_code'),source=source(rt,rows.get(name)))
        for name in PRODUCERS}
    draft=rt.result(rows['wt_draft']['job_id'])['draft']
    epitope=(draft['assessments']['epitope_map']['observations'] or {}).get('epitopes') or {}
    bcell=epitope.get('b_cell_epitope_map') or {}
    profile=(bcell.get('raw_score_profiles') or {}).get('ensemble_probability')
    return dict(purpose='BACKEND_EVIDENCE_ENGINEERING' if engineering.enabled(body) else 'M1_INTERNAL_TEST_ONLY',configuration=body['m1_test'],
        sequence_sha256=sha(body['protein_sequence'].encode()),
        wt_assessment=source(rt,rows.get('wt_draft')),upstream=inputs,
        assessments=draft['assessments'],
        bepipred_test_selection=dict(column='BepiPred-3.0 score',field='ensemble_probability',
            values=profile,state='available_unreviewed' if profile is not None else 'unavailable',
            source=source(rt,rows.get('epitope_map')),provisional=True,
            difference='OI-026 remains unsigned; no peak or hotspot threshold change'),
        permission_source='S27_BACKEND_AUDIT_NOT_SCIENTIFIC_SIGNOFF' if engineering.enabled(body) else 'EXPLICIT_TEST_MASKS_NOT_AUTOMATIC_SCIENTIFIC_PERMISSIONS',
        design_input_audit=source(rt,rows.get('design_inputs')),
        missing_data_policy='PRESERVE_UNKNOWN_NO_ZERO_IMPUTATION',
        scientific_release_gate='CLOSED',usable_for_pipeline=False,automatic_handoff=False)

def request_for(rt, b, rows, name):
    from .candidate_dna import ORDER as DNA_ORDER,request as dna_request
    if engineering.enabled(b) and name in DNA_ORDER:return dna_request(rt,b,rows,name)
    from .candidate_developability import CHILDREN as N10_CHILDREN,request as n10_request
    if name in N10_CHILDREN:return n10_request(rt,b,rows,name)
    from .design_rounds import NAMES, request as round_request, active
    from .m1 import FULL_TAIL
    if engineering.enabled(b) and name in NAMES:return round_request(rt,b,rows,name)
    if engineering.enabled(b) and name in FULL_TAIL[2:]:rows=active(rows)
    if engineering.enabled(b):
        if name == 'design_inputs':return engineering.request(rt,b,rows)
        b,reason=engineering.effective(rt,b,rows)
        if name=='design' and reason:return None,reason
        if name in ('wt_foldx','wt_thermompnn') and reason:return None,reason
    if b.get('m1_test') is not None or engineering.enabled(b):
        from .m1 import request_for as continuation
        if engineering.enabled(b) and rows.get('design',{}).get('state')=='succeeded':
            native=decode(rt._request_bytes(rt.get(rows['design']['job_id'])))
            b=dict(b,m1_test={k:native[k] for k in ('constraints','n_designs','sampling_temperature','seed','timeout_seconds')})
        answer=continuation(rt,b,rows,name)
        if answer is not None:return answer
    base = dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],timeout_seconds=30)
    if name == 'prediction':
        opt = b['prediction']
        return dict(base,host_species=b['host_species'],seed=opt['seed'],timeout_seconds=opt['timeout_seconds']), None
    if name == 'structure':
        if b.get('prediction') is not None:
            row = rows.get('prediction', {})
            if row.get('state') != 'succeeded': return None, 'PREDICTION_UNAVAILABLE'
            source_module=prediction_source(b['prediction']['engine'])
            job = rt.get(row['job_id'])
            with rt._db() as db:
                ref, _ = source_module.verified(rt,db,job['job_id'],b['protein_sequence'],b['host_species'],job['run_id'])
            engine=b['prediction']['engine']
            return dict(protein_sequence=b['protein_sequence'],host_species=b['host_species'],structure_artifact=ref,
                        structure_name=engine+'.cif',declared_format='MMCIF',selection=dict(model_index=0,chain_selector='A'),
                        context_chain_ids=['A'],source_declaration=dict(kind='predicted',note=engine+' job '+job['job_id']),timeout_seconds=120), None
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
        inputs['topology_input']=typed(rt,rows,'topology')
        if b.get('m1_test') is None and not any(inputs[n+'_input']['state']=='available' for n in ('bepipred','netmhc')):
            return None,'EPITOPE_PREDICTOR_INPUTS_UNAVAILABLE'
        if inputs['blast_input']['state']=='not_provided':
            inputs['blast_input']=dict(state='not_executed',artifact=None,reason_code='WORKFLOW_BLAST_NOT_EXECUTED')
        return dict(base,**inputs),None
    if name=='glycosylation':
        n06=rows.get('epitope_map',{})
        hotspot=rt.n06_hotspot_input(n06['job_id'],b['protein_sequence']) if n06.get('state')=='succeeded' else dict(state='not_provided',hotspots=None,source=None,reason_code=None)
        return dict(base,hotspot_input=hotspot),None
    if name=='wt_draft':
        return dict(base,host_species=b['host_species'],organism=b['organism'],
                    design_context=b['design_context'],
                    upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    if name=='design' and b.get('m1_test') is not None:
        reason=m1_design_reason(rt,rows)
        if engineering.enabled(b) and reason=='M1_DESIGN_DOMAIN_NOT_SUPPORTED':
            gate=design_applicability(rt,rows)
            if gate and gate['status']=='SUITABLE_FOR_DESIGN':reason=None
        if reason:return None,reason
        return dict(base,**b['m1_test'],structure_artifact=source(rt,rows['structure'])['artifact']),None
    if name in ('design','rescore','protection','stability'):
        reason=design_route_reason(rt,rows)
        return None,'DESIGN_CONSTRAINTS_NOT_REGISTERED' if reason=='SCIENTIFIC_CONSUMPTION_NOT_RELEASED' else reason
    if name=='variant_report':
        return dict(base,variant_source='N11_DESIGN_AUDIT',upstream=dict(design_audit=None,foldx=None),foldx_bindings=[]),None
    if name=='codon': return None,'EXPRESSION_HOST_NOT_PROVIDED' if b['expression_host'] is None else 'NO_ELIGIBLE_SEQUENCE'
    if name=='wt_reference':
        return dict(base,upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    if name=='local_delivery':
        from .candidate_dna import bindings
        return dict(base,host_species=b['host_species'],expression_host=b['expression_host'],
                    dna_bindings=bindings(rt,b,rows) if engineering.enabled(b) else [],
                    upstream={n:source(rt,rows.get(n)) for n in worker(name).PRODUCERS}),None
    raise RuntimeFault('INVALID_REQUEST','Unknown workflow node')

def _record(rt, jid, name, row):
    if name in ('design','retry1_design','retry2_design') and row.get('state')=='succeeded' and row.get('job_id'):
        generation=rt.result(row['job_id'])['generation']
        row=dict(row,generation_status=generation['status'],generated_count=len(generation['records']))
        if generation['status']=='not_generated_no_designable_positions':
            row.update(reason_code='NO_DESIGNABLE_POSITIONS',detail='全部位点固定；原生候选生成未执行，候选数为 0')
    with rt._tx() as db:
        j=rt._job(db,jid);ex=rt._execution(db,jid)
        if j['state'] in TERMINAL:return
        if name in ('wt_foldx','wt_thermompnn') and ex['nodes'].get(name,{}).get('scan_scope') is not None:
            row=dict(row,scan_scope=ex['nodes'][name]['scan_scope'])
        ex['nodes'][name]=dict(row,node_id=policy.NODES[name],recorded_at=now())
        rt._execution_store(db,jid,ex);rt._store(db,copy.deepcopy(j),j,'workflow_node_'+name)

def reusable_wt_netmhc(rt,body,rows,run_id,req):
    if rows.get('netmhc',{}).get('state')!='succeeded':return None
    original=verified(rt,body,'netmhc',rows['netmhc']['job_id'],run_id,rows)
    ensure(original['run_id']==run_id,'FORBIDDEN','WT reuse must remain in the current run')
    original_request=decode(rt._request_bytes(original))
    if {k:v for k,v in original_request.items() if k!='timeout_seconds'}=={k:v for k,v in req.items() if k!='timeout_seconds'}:
        return original['job_id']
    return None


def _create_child(rt, jid, name, req):
    with rt._tx() as db:
        j=rt._job(db,jid);ex=rt._execution(db,jid)
        if j['stop_reason'] or j['state'] in TERMINAL:return None
        body=policy.request(rt._input(db,j['request_artifact'],j['run_id']))
        prior=ex['nodes'].get(name,{})
        if prior and prior.get('state')!='ready':return prior.get('job_id')
        w=worker(name,body,ex['nodes'])
        from .confirmation import elapsed
        remaining=body['timeout_seconds']-elapsed(ex)
        if name.split('_')[-1]=='netmhc' and req.get('panel_mode'):
            # Give N05 an independent execution budget and retain time for S-18 degradation.
            # Integrity failures still halt through recoverable_child_failure.
            remaining-=min(300,max(1,int(body['timeout_seconds']*.1)))
            req=dict(req,timeout_seconds=min(req['timeout_seconds'],900))
            if remaining<=0:
                ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=None,state='skipped',
                    origin=None,reason_code='N05_DOWNSTREAM_TIME_RESERVE',
                    detail='N05 not executed: retaining time for WARNING+continue and report delivery')
                rt._execution_store(db,jid,ex)
                rt._store(db,copy.deepcopy(j),j,'workflow_n05_budget_unavailable')
                return None
        if remaining <= 0:
            rt._stop(db,j,'timeout');return None
        if engineering.enabled(body) and name in ('wt_foldx','wt_thermompnn'):
            # Keep the two bounded local assemblies reachable after a scan timeout.
            reserve=60
            if remaining<=reserve:
                ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=None,state='skipped',origin=None,
                    reason_code='N17_DOWNSTREAM_TIME_RESERVE',remaining_seconds=remaining,reserve_seconds=reserve)
                rt._execution_store(db,jid,ex)
                rt._store(db,copy.deepcopy(j),j,'workflow_n17_budget_unavailable')
                return None
            remaining-=reserve
        from .revision_runtime import CHILDREN as REVISION_RUNTIME_CHILDREN,stage_remaining
        if name in REVISION_RUNTIME_CHILDREN:
            stage_time=stage_remaining(ex,body,name)
            if stage_time is not None:
                if stage_time<=0:
                    ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=None,state='skipped',origin=None,reason_code='SKIPPED_BUDGET')
                    rt._execution_store(db,jid,ex);return None
                remaining=min(remaining,stage_time)
        req=dict(req,timeout_seconds=min(req['timeout_seconds'],max(1,int(remaining))))
        if name=='local_delivery':req['workflow_job_id']=jid
        if name=='variant_report' and engineering.enabled(body):req['n14_source']=dict(workflow_job_id=jid)
        from .revision_controller import reserve_child
        if not reserve_child(ex,body,name,req):
            ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=None,state='skipped',origin=None,reason_code='SKIPPED_BUDGET')
            rt._execution_store(db,jid,ex)
            return None
        ref=rt._stage(db,j['run_id'],encode(req),w.TOOL)
        request=envelope(j['run_id'],ref,w,jid+'-'+name)
        rt._admit(db,request)
        child=rt._new_job(db,request,encode(request))
        ex['nodes'][name]=dict(node_id=policy.NODES[name],job_id=child['job_id'],state='queued',origin='NEW_EXECUTION',reason_code=None)
        if name in ('wt_foldx','wt_thermompnn'):
            from .m1 import scan_scope
            from .design_rounds import active
            scope_rows=active(ex['nodes']) if engineering.enabled(body) else ex['nodes']
            effective_body,_=engineering.effective(rt,body,scope_rows)
            if engineering.enabled(body) and scope_rows.get('design',{}).get('state')=='succeeded':
                native=decode(rt._request_bytes(rt.get(scope_rows['design']['job_id'])))
                effective_body=dict(effective_body,m1_test={k:native[k] for k in ('constraints','n_designs','sampling_temperature','seed','timeout_seconds')})
            fact,reason=scan_scope(rt,effective_body,scope_rows)
            ensure(reason is None and fact['positions']==req['scan_positions'],
                   'OUTPUT_INVALID','N17 submitted scope differs from complete scope')
            ex['nodes'][name]['scan_scope']=fact
        if prior.get('confirmation'):ex['nodes'][name]['confirmation']=prior['confirmation']
        if name=='design' and (body.get('m1_test') is not None or engineering.enabled(body)):
            body,_=engineering.effective(rt,body,ex['nodes'])
            ex['nodes'][name]['internal_test_input']=m1_inputs(rt,body,ex['nodes'])
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
    if verify:
        from .validation import NAMES,verified_fact
        for name in NAMES:
            if rows.get(name,{}).get('state')=='succeeded':verified_fact(rt,jid,name)
    if verify and rows.get('preselection',{}).get('state')=='succeeded':
        from .m1 import preselection
        ensure(rows['preselection'].get('origin')=='INTERNAL_FACT' and
            rows['preselection'].get('fact')==preselection(rt,body,rows),
            'OUTPUT_INVALID','N12 internal preselection differs from verified producers')
    for name,row in rows.items():
        if row.get('job_id'):
            child=verified(rt,body,name,row['job_id'],j['run_id'],rows) if verify else rt.get(row['job_id'])
            row.update(state=child['state'],error_code=child['error_code'],attempt_id=child['attempt_id'],
                       request_artifact=child['request_artifact'],execution_profile=child['execution_profile'],
                       rule_profile=child['rule_profile'],artifacts=child['artifacts'])
            row.update(qualification='DEVELOPMENT_UNREVIEWED',scientific_signoff=None,usable_for_pipeline=False)
            if verify and row.get('scan_scope') is not None:
                fact=row['scan_scope'];req=decode(rt._request_bytes(child))
                ensure(name in ('wt_foldx','wt_thermompnn') and
                       sha(encode({k:v for k,v in fact.items() if k!='scope_sha256'}))==fact['scope_sha256'] and
                       fact['positions']==req['scan_positions'] and
                       req['scope_source']['source_id'].endswith('scope_sha256='+fact['scope_sha256']),
                       'OUTPUT_INVALID','N17 recorded coverage differs from submitted request')
    for name in policy.order(body):
        rows.setdefault(name,dict(node_id=policy.NODES[name],job_id=None,state='not_executed',reason_code=j['error_code'] or 'PENDING_DEPENDENCIES'))
    gate=design_applicability(rt,rows) if verify else None
    from .design_rounds import summary as rounds_summary
    from .revision_controller import enabled as revised,verified_fact as revision_fact
    revision=revision_fact(rt,jid,body) if verify and revised(body) else copy.deepcopy(ex.get('revision_state'))
    return dict(job=j,nodes=rows,configuration=body['configuration'],sequence_sha256=sha(body['protein_sequence'].encode()),
                expert_revision=revision,
                design_rounds=rounds_summary(rt,rows) if verify and engineering.enabled(body) else None,
                pending_confirmation=copy.deepcopy(ex.get('pending_confirmation')),
                continuation=copy.deepcopy(ex.get('continuation')),
                internal_test=dict(selected=body.get('m1_test') is not None or engineering.enabled(body),
                    eligible_for_n11=verify and m1_design_reason(rt,rows) is None and (
                        engineering.effective(rt,body,rows)[1] is None if engineering.enabled(body) else body.get('m1_test') is not None),
                    scope='BACKEND_EVIDENCE_ENGINEERING' if engineering.enabled(body) else 'M1_P1_P3_SAME_RUN' if body.get('m1_test') is not None else None),
                qualification='DEVELOPMENT_UNREVIEWED',usable_for_pipeline=False,automatic_handoff=False,
                design_applicability_gate=gate,scientific_gate='CLOSED',scientific_release_gate='CLOSED',
                scientific_signoff=None,production_status='NOT_DEPLOYED',md='EXCLUDED')

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
          '| Node | Branch | State | Reason | Origin | Detail |','|---|---|---|---|---|---|']
    for name,row in data['nodes'].items():
        text.append('| '+ ' | '.join(str(v or '') for v in (row['node_id'],name,row['state'],row.get('reason_code') or row.get('error_code'),row.get('origin'),str(row.get('detail') or '').replace('|','/').replace('\n',' '))) +' |')
    if data.get('expert_revision'):
        revision=data['expert_revision']
        text+=['','## Expert revision / engineering facts','',
               'Contract: '+revision['shared_contract_version'],
               'Formal acceptance: '+revision['acceptance_status'],
               'Proposals are nomination-only; full sequences, provenance and task budgets are in workflow.json.',
               '', '| Candidate | Mutations | Disposition | S28 | FoldX execution / mean / valid repeats | Acceptance |', '|---|---|---|---|---|---|']
        for record in revision['formal_records']:
            text.append('| '+' | '.join((record['candidate_id'],str(len(record['mutations'])),record['disposition'],
                record['validation']['check_status'],str((record.get('foldx') or {}).get('execution_status','NOT_RUN'))+' / '+
                str((record.get('foldx') or {}).get('mean'))+' / '+str((record.get('foldx') or {}).get('valid_count',0)),record['acceptance_status']))+' |')
        if revision.get('runtime_policy_status')=='pending_calibration':
            text+=['','v2 thresholds: pending_calibration. Provisional task acceptance: '+revision['provisional_acceptance_status'],
                'Scores are comparable only within the same dimension, mode and evidence group; no global rank.',
                '', '| Candidate | Supplier | N13 / legacy L1 identity | L4 | Comparison before / after penalty | Acceptance score / provisional |', '|---|---|---|---|---|---|']
            for r in revision['formal_records']:
                text.append('| '+' | '.join((r['candidate_id'],str(r.get('evidence_supplier')),
                    str(r.get('protection',{}).get('check_status'))+' / '+str(r.get('protection',{}).get('l1_identity_pass')),
                    str(r.get('l4',{}).get('check_status')),str(r.get('unpenalized_score'))+' / '+str(r.get('comparison_score')),
                    str(r.get('acceptance_score'))+' / '+str(r.get('provisional_acceptance_status'))))+' |')
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
    result=dict(contract_version='0.2.0',tool_id=policy.TOOL,binding=binding,
                qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,
                automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',requires_review=True,
                scientific_gate='CLOSED',status='completed_with_gaps' if not error else 'unreliable',
                workflow=data,null_reason=error,warnings=[],execution=dict(error_code=error,exit_code=1 if error else 0,
                    stopped_confirmed=True,network_used=False,backend='local-workflow-controller'))
    if ex.get('controller_upgrade'):
        result['execution']['controller_upgrade']=copy.deepcopy(ex['controller_upgrade'])
    ex.update(tree_stopped=True,dispatcher=None)
    return rt._finish_development(jid,ex,files,result)

from ...service_api.replay_cache import traversal


@traversal
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
        if ex.get('fatal_error'):raise RuntimeFault(ex['fatal_error'],'Previously recorded workflow failure')
        from ...service_api.controller_recovery import accepted
        ensure(body['configuration']==configuration(rt) and accepted(before,ex,policy.registered_profile()),
               'PROFILE_NOT_APPROVED','Workflow code or local database configuration changed')
        if body['structure_artifact'] is not None:
            with rt._db() as db:rt._structure_bytes(db,body,before['run_id'])
        refresh = True
        verified_facts = {}
        for name in policy.order(body):
            # One dispatcher owns this traversal. Completed/absent branches do
            # not mutate its execution snapshot. Reload after a mutating step,
            # not once per reserved slot (the snapshot can exceed 15 MiB).
            # The small job row stays live on every iteration for cancellation.
            j=rt.get(jid)
            if refresh:
                ex=rt.execution(jid)
                refresh=False
            from .confirmation import elapsed
            if elapsed(ex)>=body['timeout_seconds'] and not j['stop_reason']:
                with rt._tx() as db:rt._stop(db,rt._job(db,jid),'timeout')
                j=rt.get(jid)
            if j['stop_reason']:return finish(rt,jid)
            if ex.get('pending_confirmation'):return j
            from .revision_controller import STAGE as REVISION_STAGE,tick as revision_tick
            if name==REVISION_STAGE:
                refresh=True
                if not revision_tick(rt,jid,body):return rt.get(jid)
                continue
            from .validation import NAMES as VALIDATIONS,tick
            if name in VALIDATIONS:
                refresh=True
                if not tick(rt,jid,body,name,verified_facts):return rt.get(jid)
                continue
            rows=ex['nodes'];row=rows.get(name)
            if row and not row.get('job_id') and row.get('state')!='ready':continue
            if row and row.get('job_id'):
                child=verified(rt,body,name,row['job_id'],j['run_id'],rows)
                if child['state'] in TERMINAL:
                    if row['state']!=child['state']:
                        _record(rt,jid,name,dict(row,state=child['state'],reason_code=child['error_code']))
                        refresh=True
                    if child['state']!='succeeded' and not recoverable_child_failure(body,name,child):
                        raise RuntimeFault(child['error_code'] or 'OUTPUT_INVALID','Workflow child did not succeed: '+name)
                    continue
                refresh=True
                if child['state']=='queued':rt.dispatch(child['job_id'])
                else:rt.recover(child['job_id'])
                child=rt.get(child['job_id'])
                _record(rt,jid,name,dict(row,state=child['state'],reason_code=child['error_code']))
                if child['state'] not in TERMINAL:return rt.get(jid)
                verified(rt,body,name,child['job_id'],j['run_id'],rows)
                if child['state']!='succeeded' and not recoverable_child_failure(body,name,child):
                    raise RuntimeFault(child['error_code'] or 'OUTPUT_INVALID','Workflow child did not succeed: '+name)
                continue
            refresh=True
            if name in body['reuse_jobs']:
                child=verified(rt,body,name,body['reuse_jobs'][name])
                ensure(child['state']=='succeeded','INVALID_STATE','Historical reuse requires terminal success')
                _record(rt,jid,name,dict(job_id=child['job_id'],state=child['state'],origin='HISTORICAL_REUSE',reason_code=None))
                continue
            try:
                if name=='preselection':
                    if rows.get('design_audit',{}).get('state')!='succeeded':
                        _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='DESIGN_NOT_EXECUTED'))
                    else:
                        from .m1 import preselection
                        if engineering.enabled(body):
                            from .design_rounds import summary
                            if summary(rt,rows)['exhausted']:
                                raise RuntimeFault('TOOL_FAILED','All 136 generated designs rejected after three expert rounds')
                        fact=preselection(rt,body,rows)
                        _record(rt,jid,name,dict(job_id=None,state='succeeded',origin='INTERNAL_FACT',
                            reason_code=None,fact=fact))
                    continue
                from . import candidate_developability
                if name in candidate_developability.CHILDREN:
                    req,reason=candidate_developability.request(rt,body,rows,name,verified_facts=verified_facts)
                else:req,reason=request_for(rt,body,rows,name)
                if name=='design' and reason=='T4_EMPTY_FIXED_CONFIRMATION_REQUIRED':
                    from .confirmation import pause
                    pause(rt,jid)
                    return rt.get(jid)
                if req is None:
                    state='unavailable' if body.get('m1_test') is not None and name in ('blast','homology','domains') else 'skipped'
                    skipped=dict(job_id=None,state=state,reason_code=reason,origin=None)
                    if reason=='N11_MASK_EXPORT_BLOCKED':
                        skipped['detail']=rt.result(rows['design_inputs']['job_id'])['audit']['mask_conversion_error']
                    _record(rt,jid,name,skipped);continue
                if name=='wt_netmhc':
                    reused=reusable_wt_netmhc(rt,body,rows,j['run_id'],req)
                    if reused:
                        _record(rt,jid,name,dict(job_id=reused,state='succeeded',
                            reason_code=None,origin='SAME_RUN_REUSE'))
                        continue
                from .candidate_developability import CHILDREN as N10_CHILDREN,reuse as n10_reuse
                if name in N10_CHILDREN:
                    reused=n10_reuse(rt,body,rows,name,req,j['run_id'])
                    if reused:
                        _record(rt,jid,name,dict(job_id=reused,state='succeeded',reason_code=None,origin='SAME_RUN_REUSE'))
                        continue
                if name.startswith('rep') and name.endswith('_prediction'):
                    from .m1 import prediction_validation
                    validation=prediction_validation(rows,name)
                    if validation is not None and validation['selected'] is not None:
                        prediction=validation['engines'][validation['selected']]['source']['job_id']
                        verified(rt,body,name,prediction,j['run_id'],rows)
                        _record(rt,jid,name,dict(job_id=prediction,state='succeeded',
                            reason_code=None,origin='S28_SELECTED_PREDICTION'))
                        continue
                # Recheck every prior source before constructing or admitting a dependent job.
                for upstream,r in rows.items():
                    if r.get('job_id'):verified(rt,body,upstream,r['job_id'],j['run_id'],rows)
                child_id=_create_child(rt,jid,name,req)
                if child_id is None:
                    if rt.execution(jid)['nodes'].get(name,{}).get('reason_code') in ('N05_DOWNSTREAM_TIME_RESERVE','N17_DOWNSTREAM_TIME_RESERVE'):continue
                    return finish(rt,jid)
                rt.dispatch(child_id)
                child=rt.get(child_id)
                _record(rt,jid,name,dict(rt.execution(jid)['nodes'][name],state=child['state'],reason_code=child['error_code']))
                if child['state'] not in TERMINAL:return rt.get(jid)
                if rt.get(jid)['stop_reason']:return finish(rt,jid)
                if child['state']!='succeeded' and not recoverable_child_failure(body,name,child):
                    raise RuntimeFault(child['error_code'] or 'OUTPUT_INVALID','Workflow child did not succeed: '+name)
            except RuntimeFault as exc:
                if body.get('m1_test') is not None:raise
                if exc.code not in ('INVALID_REQUEST','ASSET_MISSING'):raise
                if rt.execution(jid)['nodes'].get(name,{}).get('job_id'):raise
                _record(rt,jid,name,dict(job_id=None,state='blocked',reason_code=exc.code,detail=str(exc),origin=None))
                if name=='stability' and str(exc)=='Request exceeds tool capacity':raise
        return finish(rt,jid)
    except RuntimeFault as exc:
        with rt._tx() as db:
            ex=rt._execution(db,jid);ex['fatal_error']=exc.code;ex['fatal_detail']=str(exc);rt._execution_store(db,jid,ex)
        stop_children(rt,jid)
        # Keep active children tracked; subsequent recovery confirms their stop.
        active=any(rt.get(r['job_id'])['state'] not in TERMINAL for r in rt.execution(jid)['nodes'].values()
                   if r.get('job_id') and r.get('origin')=='NEW_EXECUTION')
        if active:return rt.get(jid)
        return finish(rt,jid,exc.code)
    finally:
        with rt._tx() as db:
            ex=rt._execution(db,jid);ex['dispatcher']=None;rt._execution_store(db,jid,ex)
