"""v2 source replay, pre-generation freeze and N13/L4/N10/FoldX consumers."""
from ...common import TERMINAL,RuntimeFault,decode,encode,ensure,sha
from . import revision_v2 as rules,revision_contract as c,revision_budget as budget

KINDS={'structure':'ingest_structure','developability':'developability','bepipred':'bepipred','netmhc':'netmhc','epitope_map':'epitope_map','foldx':'foldx'}
CHILDREN={f'z{r}_s{s}_{kind}':tool for r,n in enumerate((24,48,64)) for s in range(1,n+1) for kind,tool in KINDS.items()}


def key(index,r,kind):return f'z{index}_s{r["sample_number"]}_{kind}'


def kind(name):return name.split('_',2)[2]


def stage(name):return 'foldx' if kind(name)=='foldx' else 'l4' if kind(name) in ('bepipred','netmhc','epitope_map') else 'analysis'


def candidate_sequence(rt,rows,name):
    from .revision_runtime import sequence
    return sequence(rt,rows,'rx'+name[1:])


def side(rt,run,seq,refs):
    from ..epitope_protection.source import registered,side_enrich,same_run_receipts,facts
    from ..epitope_protection.policy import SIDE_PRODUCERS
    body=dict(protein_sequence=seq,upstream=refs)
    with rt._db() as db:
        files,values,receipts=registered(rt,db,body,producers=SIDE_PRODUCERS,enricher=side_enrich)
    same_run_receipts(receipts,run)
    from ...service_api.replay_cache import pure
    return pure(facts,body,files,values,receipts)


def wt_inputs(rt,jid,body):
    from .service import source,verified
    from .candidate_developability import verified_value
    rows=rt.execution(jid)['nodes'];run=rt.get(jid)['run_id']
    refs={n:source(rt,rows.get(n)) for n in ('structure','epitope_map','domains')}
    w=side(rt,run,body['protein_sequence'],refs)
    if body['revision_config']['policies']['model_roles']['model_role_policy']==rules.SINGLE_MODEL_POLICY:
        w['prediction_engine']=structure_engine(rt,refs['structure'])
    n=rows.get('developability',{});value=None;ref=source(rt,n)
    if n.get('state')=='succeeded':
        verified(rt,body,'developability',n['job_id'],run,rows)
        with rt._db() as db:value=verified_value(rt,db,ref,body['protein_sequence'],run)
    summary=(value or {}).get('developability',{})
    frozen=rules.freeze(summary.get('dimensions',{}),ref,summary.get('dimension_weights'))
    return dict(wt_side=w,frozen=frozen,wt_refs=refs)


def structure_engine(rt,ref):
    """Read producer identity only after side() has verified the structure chain.

    Free-text source declarations and request engine preferences are not provenance.
    Uploaded/unknown origins cannot authorize a predicted-structure comparison.
    """
    if not ref:return None
    job=rt.get(ref['job_id'])
    if job.get('tool_id')!='t01.real.ingest_structure':return None
    origin=decode(rt._request_bytes(job)).get('structure_artifact')
    if not origin:return None
    producer=rt.get(origin['job_id'])
    return {'t01.real.af3':'af3','t01.real.esmfold2':'esmfold2'}.get(producer.get('tool_id'))


def freeze(rt,jid,body):
    current=wt_inputs(rt,jid,body)
    with rt._tx() as db:
        ex=rt._execution(db,jid);old=ex.get('revision_v2_frozen')
        if old is not None:ensure(old==current,'OUTPUT_INVALID','v2 frozen WT targets or dimensions changed')
        else:
            ensure(not any(n.startswith(('proposal','formal')) for n in ex['nodes']),
                   'OUTPUT_INVALID','v2 dimensions must freeze before generation')
            ex['revision_v2_frozen']=current;rt._execution_store(db,jid,ex)
    return current


def verified_freeze(rt,jid,body):
    value=rt.execution(jid).get('revision_v2_frozen')
    if value is None:return None
    ensure(value==wt_inputs(rt,jid,body),'OUTPUT_INVALID','v2 frozen upstream changed')
    return value


def geom(record,data):
    from ..design_backend.burden import compute
    audit=data['audit']
    row=dict(sequence=record['sequence'],sample_number=record['sample_number'],mutations=[dict(position=m['position'],wt_residue=m['wt'],mut_residue=m['mut'],source='ProteinMPNN') for m in record['mutations']])
    g=compute(data['snapshot']['original_wt_seq'],row,audit['geometry'],audit['domain_intervals'],audit['epitope_hotspot_intervals'],'general',data['scales'])
    dims=g['engineering_thresholds']['per_dimension_exceeded'];names=['spatial_clustering','functional_proximity','epitope_proximity','epistasis_risk']
    excluded=[]
    if audit['domain_intervals']==[]:
        names.remove('functional_proximity');excluded.append('functional_proximity')
    status='FAIL' if any(dims[k] is True for k in names) else 'NOT_ASSESSED' if any(dims[k] is None for k in names) else 'PASS'
    record['geometry_check']=c.check(status,observation=g,legacy_burden_exceeded=g['engineering_thresholds']['aggregate_exceeded'],
        excluded_dimensions=excluded,exclusion_reason='CONFIRMED_EMPTY_FUNCTIONAL_OBJECT_SET' if excluded else None)


def request(rt,jid,body,data,r,index,what):
    from .service import typed
    rows=rt.execution(jid)['nodes'];base=dict(protein_sequence=r['sequence'],user_sequence_id=body['user_sequence_id'],timeout_seconds=30)
    if what=='structure':
        if r.get('structure') is None:return None,'STRUCTURE_SUPPLIER_UNAVAILABLE'
        return dict(protein_sequence=r['sequence'],host_species=body['host_species'],structure_artifact=r['structure'],
            structure_name='v2-prediction.cif',declared_format='MMCIF',selection=dict(model_index=0,chain_selector='A'),
            context_chain_ids=['A'],source_declaration=dict(kind='predicted',note='v2 '+str(r.get('evidence_supplier'))),timeout_seconds=120),None
    if what=='foldx':
        from .revision_runtime import foldx_request
        return foldx_request(body,data,[r]),None
    if what in ('bepipred','netmhc','developability'):
        opt=body['analysis'][what]
        if opt is None:return None,what.upper()+'_INPUT_UNAVAILABLE'
        req=dict(base,**opt)
        if what=='netmhc':req['host_species']=body['host_species']
        if what=='developability':req['structure_input']=typed(rt,rows,key(index,r,'structure'))
        return req,None
    if what=='epitope_map':
        return dict(base,bepipred_input=typed(rt,rows,key(index,r,'bepipred')),netmhc_input=typed(rt,rows,key(index,r,'netmhc')),
            blast_input=dict(state='not_executed',artifact=None,reason_code='WT_EXPERIMENTAL_EVIDENCE_NOT_RELABELED_AS_VARIANT'),
            topology_input=dict(state='not_provided',artifact=None,reason_code=None),timeout_seconds=60),None
    raise RuntimeFault('INVALID_REQUEST','Unknown v2 stage')


def run_child(rt,jid,body,data,r,index,what):
    from .service import _record
    from .revision_controller import child
    from .revision_runtime import bind
    name=key(index,r,what);row=rt.execution(jid)['nodes'].get(name,{})
    if row.get('state')=='skipped':return True
    req,reason=request(rt,jid,body,data,r,index,what)
    if reason:
        _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code=reason));return True
    if not bind(rt,jid,body,name,req,[r]):return False
    try:return child(rt,jid,body,name,req)
    except RuntimeFault as e:
        if e.code!='ASSET_MISSING':raise
        _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='ENGINE_ASSET_UNAVAILABLE'));return True


def check_child(rt,jid,body,data,r,index,what):
    from .service import verified
    from .revision_runtime import assert_request
    ex=rt.execution(jid);name=key(index,r,what);row=ex['nodes'].get(name,{})
    if not row.get('job_id'):return row,None
    if stage(name) in ('l4','foldx'):
        chosen=ex.get('revision_v2_allocations',{}).get(stage(name)+str(index),{})
        ensure(r['candidate_id'] in chosen.get('selected_candidate_ids',[]),'OUTPUT_INVALID','v2 child outside frozen evaluation pool')
    b=ex['revision_bindings'][name]
    ensure(b['candidate_ids']==[r['candidate_id']] and b['content_hashes']==[r['content_hash']] and b['config_sha256']==sha(encode(body['revision_config'])),
           'OUTPUT_INVALID','v2 candidate identity mismatch')
    req,reason=request(rt,jid,body,data,r,index,what)
    ensure(req is not None,'OUTPUT_INVALID','v2 child prerequisite disappeared')
    assert_request(rt,row,req);job=verified(rt,body,name,row['job_id'],rt.get(jid)['run_id'],ex['nodes'])
    return row,job


def bp(rt,ref,sequence,run):
    if not ref or not ref.get('artifact') or rt.get(ref['job_id'])['state']!='succeeded':return None,None
    from ..bepipred.result import parse
    # N04 publishes raw scores without a scientific rule profile. Verify its
    # actual producer contract rather than importing the N12 scored contract.
    with rt._db() as db:
        job,_,value=rt._registered_result_artifact(db,ref['artifact'],'t01.real.bepipred')
        request_raw=rt._input(db,job['request_artifact'],job['run_id'])
    req=decode(request_raw);binding=value['binding']
    ensure(job['job_id']==ref['job_id'] and job['run_id']==run and req['protein_sequence']==sequence,
           'FORBIDDEN','L4 predictor reference differs')
    ensure(job['state']=='succeeded' and value['qualification']=='DEVELOPMENT_UNREVIEWED' and
           value['scientific_signoff'] is None and job['rule_profile'] is None and
           binding.get('rule_profile') is None and binding.get('input_sha256')==sha(request_raw) and
           binding.get('sequence_sha256')==sha(sequence.encode()) and
           all(binding.get(k)==job[k] for k in ('request_id','execution_identity','execution_profile')),
           'OUTPUT_INVALID','BepiPred source request/execution identity differs')
    files={}
    for item in value['raw_artifacts']:
        ensure(item['path'] not in files and item['artifact'] in job['artifacts'],
               'OUTPUT_INVALID','Foreign or duplicate BepiPred source artifact')
        files[item['path']]=rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id'])
    ensure(files.get('input.json')==request_raw,'OUTPUT_INVALID','BepiPred executed request differs')
    parsed=parse(files,sequence)
    ensure(all(value.get(k)==v for k,v in parsed.items()),'OUTPUT_INVALID','BepiPred published observations differ from native output')
    return [v['ensemble_probability'] for v in parsed['raw_scores']],dict(execution=job['execution_profile'],rule=job['rule_profile'],parameters={k:v for k,v in req.items() if k not in ('protein_sequence','user_sequence_id','timeout_seconds')})


def enrich(rt,jid,body,data,records):
    from .service import source
    from .candidate_developability import verified_value
    from .revision_runtime import foldx_observation
    frozen=verified_freeze(rt,jid,body)
    if frozen is None:return
    ex=rt.execution(jid);rows=ex['nodes'];run=rt.get(jid)['run_id'];cfg=body['revision_config']
    for r in records:
        if r['disposition']!='FORMAL_POOL':continue
        r['budget_B']=data['snapshot']['mutation_budget']['B'];geom(r,data)
        rules.s28(r,r.get('structure_observations',{}),cfg)
        index=next(i for i in range(3) if rows.get(f'formal{i}',{}).get('job_id') and source(rt,rows[f'formal{i}'])['artifact']==r['generation_source'])
        for what in ('structure','developability','bepipred','netmhc','epitope_map','foldx'):
            check_child(rt,jid,body,data,r,index,what)
        refs=dict(structure=source(rt,rows.get(key(index,r,'structure'))),epitope_map=None,domains=None)
        variant=side(rt,run,r['sequence'],refs)
        same_engine=cfg['policies']['model_roles']['model_role_policy']==rules.SINGLE_MODEL_POLICY
        if same_engine:variant['prediction_engine']=structure_engine(rt,refs['structure'])
        r['protection']=rules.protection(body['protein_sequence'],r,data['snapshot'],frozen['wt_side'],variant,
                                         same_engine_required=same_engine)
        row=rows.get(key(index,r,'developability'),{});value=None
        if row.get('state')=='succeeded':
            with rt._db() as db:value=verified_value(rt,db,source(rt,row),r['sequence'],run)
        r['developability_dimensions']=(value or {}).get('developability',{}).get('dimensions',{})
        r['description_weights']=(value or {}).get('developability',{}).get('dimension_weights')
        # Preserve the existing charge-only family classifier and disclose its
        # limits. No geometric family is inferred from missing annotations.
        from decimal import Decimal
        charge=data['scales']['charge'];signed=[Decimal(str(charge[m['mut']]))-Decimal(str(charge[m['wt']])) for m in r['mutations']]
        signed=[d for d in signed if d]
        r['family']='charge_tuning' if signed and abs(sum(signed))>=1 and (all(d>0 for d in signed) or all(d<0 for d in signed)) else 'mixed'
        r['family_warning']='FAMILY_PARTIAL_CHARGE_ONLY_OTHER_GEOMETRY_CLASSES_UNRESOLVED'
        permissions={p['position']:p for p in data['snapshot']['records']}
        r['permission_soft_reasons']=['SOFT_CONSTRAINT_MUTATION'] if any(permissions[m['position']].get('constraint_state')=='SOFT' for m in r['mutations']) else []
        wt_scores,wp=bp(rt,source(rt,rows.get('bepipred')),body['protein_sequence'],run)
        var_scores,vp=bp(rt,source(rt,rows.get(key(index,r,'bepipred'))),r['sequence'],run)
        from ...service_api.controller_maintenance import same_predictor
        r['l4']=rules.l4(wt_scores,var_scores,r['protection'],frozen['wt_side']['hotspots'],
                       same_predictor(rt.get(jid),ex,wp,vp))
        r['l4']['predictor_sources']=dict(wt=source(rt,rows.get('bepipred')),variant=source(rt,rows.get(key(index,r,'bepipred'))))
        maprow=rows.get(key(index,r,'epitope_map'),{})
        if maprow.get('state')=='succeeded':
            # Rebuild all maps and recursively verify predictor provenance. The
            # WT experimental annotations remain solely in frozen WT evidence.
            mapped=side(rt,run,r['sequence'],dict(refs,epitope_map=source(rt,maprow)))
            r['l4']['dynamic_map_source']=source(rt,maprow);r['l4']['dynamic_map']=mapped['hotspot_map_state']
        nrow=rows.get(key(index,r,'netmhc'),{})
        if nrow.get('state')=='succeeded':
            from ..netmhc.service import verify_sources
            nj=rt.get(nrow['job_id']);nv=rt.result(nj['job_id'])
            if nv.get('scope') in ('N05_NETMHC_PACKAGE_PAN','N05_NETMHC_HOST_PANEL'):verify_sources(rt,nj,nv)
            r['l4']['t_cell_source']=source(rt,nrow)
            r['l4']['t_cell_channels']={k:dict(status=ch.get('status'),reason_code=ch.get('reason_code')) if ch else None for k,ch in nv.get('channels',{}).items()}
            r['l4']['t_cell_preservation']='DESCRIPTIVE_ONLY_NO_HARD_THRESHOLD'
        r['l4']['execution_complete']=all(rows.get(key(index,r,k),{}).get('state')=='succeeded' for k in ('bepipred','netmhc','epitope_map'))
        if not r['l4']['execution_complete'] and not rules.l4_not_applicable(r['protection'],r['l4'],r):
            r['l4']['b_axis_observation']=dict(r['l4']);r['l4'].update(c.check('NOT_ASSESSED','L4_REQUIRED_EXECUTIONS_INCOMPLETE'),prediction_preservation=None)
        p=r['protection'];p['check_summaries']=[]
        for check_id,value,scope,required in [
            ('l1',p['l1'],p['target_scope_id'],'N13-L1-L3-v2'),
            ('l2',p['l2'],p['target_scope_id'],'N13-L1-L3-v2'),
            ('l3',p['l3'],p['target_scope_id'],'N13-L1-L3-v2'),
            ('l3_domains',p['auxiliary_geometry_status'],p['auxiliary_geometry_status']['auxiliary_scope_id'],'N13-domain-geometry-v2'),
            ('l4',r['l4'],p['target_scope_id'],'N13-L4-v2')]:
            evidence_refs=[ref['artifact'] for ref in [frozen['wt_refs'].get('structure'),frozen['wt_refs'].get('epitope_map'),frozen['wt_refs'].get('domains'),refs['structure'],r['l4']['predictor_sources']['wt'],r['l4']['predictor_sources']['variant']]
                  if ref and ref.get('artifact')]
            summary=dict(**{k:r[k] for k in c.IDENTITY},evaluation_profile_id='original',stage_id='N13',target_scope_id=scope,
                required_set_id=required,check_id=check_id,check_status=value['check_status'],
                role='soft' if check_id=='l4' else 'mandatory',
                selected_attempt_ids=sorted({ref['attempt_id'] for ref in evidence_refs if ref.get('attempt_id')}),
                selected_artifact_refs=[dict(artifact_id=ref['artifact_id'],content_hash=ref['sha256']) for ref in evidence_refs])
            summary['reason_codes']=value.get('reason_codes',[])
            if value['check_status']=='NOT_APPLICABLE' and check_id!='l3_domains':
                summary['applicability_evidence']=p.get('applicability_evidence')
            summary['summary_id']='summary-'+sha(encode(summary));p['check_summaries'].append(summary)
        fk=key(index,r,'foldx')
        if fk in ex.get('revision_bindings',{}):
            result=foldx_observation(rt,jid,body,data,fk,[r]);r['foldx']=result[r['candidate_id']]
        rules.score_record(r,frozen['frozen'],cfg)


def allocation(rt,jid,stage_name,index,records,limit):
    keyname=stage_name+str(index);ex=rt.execution(jid);old=ex.get('revision_v2_allocations',{}).get(keyname)
    # Recompute the same pool against earlier rounds only. Reservations made
    # by this allocation cannot erase its own selected candidates on resume.
    ledger=ex.get('revision_ledger',{});used={h for name,v in ledger.get('reservations',{}).items() if v['stage']==stage_name and not name.startswith(f'z{index}_') for h in v['objects']}
    current=[r for r in records if r['content_hash'] not in used]
    value=rules.select(current,max(0,limit-len(used)),foldx=stage_name=='foldx')
    if old is not None:
        ensure(old==value,'OUTPUT_INVALID','v2 frozen candidate allocation changed');return old
    with rt._tx() as db:
        job=rt._job(db,jid)
        if job['stop_reason'] or job['state'] in TERMINAL:return None
        ex=rt._execution(db,jid);ex.setdefault('revision_v2_allocations',{})[keyname]=value;rt._execution_store(db,jid,ex)
    return value


def verify_allocations(rt,jid,body,records):
    from .service import source
    ex=rt.execution(jid);cfg=body['revision_config']
    allowed={stage+str(i) for stage in ('l4','foldx') for i in range(3)}
    ensure(set(ex.get('revision_v2_allocations',{}))<=allowed,'OUTPUT_INVALID','Unknown v2 allocation identity')
    for name in ex.get('revision_v2_allocations',{}):
        stage_name,index=name[:-1],int(name[-1]);origin=source(rt,ex['nodes'].get(f'formal{index}'))
        ensure(origin is not None,'OUTPUT_INVALID','Allocation generation missing')
        rr=[r for r in records if r['generation_source']==origin['artifact'] and r['disposition']=='FORMAL_POOL']
        allocation(rt,jid,stage_name,index,rr,cfg['l4_eval_max'] if stage_name=='l4' else cfg['foldx_variant_max'])


def tick(rt,jid,body,data,records,index):
    from .service import source
    current=source(rt,rt.execution(jid)['nodes'][f'formal{index}'])['artifact']
    rr=[r for r in records if r['generation_source']==current and r['disposition']=='FORMAL_POOL'];cfg=body['revision_config']
    # Geometry is WT-derived and does not require any new model execution.
    for r in rr:geom(r,data);rules.s28(r,r.get('structure_observations',{}),cfg)
    from .revision_runtime import tick as structure_tick
    outcome=structure_tick(rt,jid,body,data,records,index,structure_only=True)
    if outcome is None:return None
    for r in rr:
        if r['validation']['check_status']!='PASS':continue
        for what in ('structure','developability'):
            if not run_child(rt,jid,body,data,r,index,what):return None
    enrich(rt,jid,body,data,records)
    chosen=allocation(rt,jid,'l4',index,rr,cfg['l4_eval_max'])
    if chosen is None:return None
    selected={r['candidate_id']:r for r in rr}
    for cid in chosen['selected_candidate_ids']:
        for what in ('bepipred','netmhc','epitope_map'):
            if not run_child(rt,jid,body,data,selected[cid],index,what):return None
    enrich(rt,jid,body,data,records)
    chosen=allocation(rt,jid,'foldx',index,rr,cfg['foldx_variant_max'])
    if chosen is None:return None
    for cid in chosen['selected_candidate_ids']:
        if not run_child(rt,jid,body,data,selected[cid],index,'foldx'):return None
    enrich(rt,jid,body,data,records)
    if any(r['validation']['check_status']=='PASS' for r in rr):return 'S28_ORIGINAL_PASS'
    if rr and all(r['validation']['check_status']=='FAIL' for r in rr):return 'all_rejected'
    return 'incomplete_only'
