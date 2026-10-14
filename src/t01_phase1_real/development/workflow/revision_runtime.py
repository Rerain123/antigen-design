"""Explicit, unreviewed policy inputs and persisted structure/FoldX consumers.

No defaults confer scientific approval. Native jobs retain their registered
worker contracts; the controller verifies their exact requests and raw results.
"""
from ...common import TERMINAL, RuntimeFault, decode, encode, ensure, sha
from . import revision_contract as c, revision_budget as budget
from .revision_structure import route
from .revision_sampling import select_structure
from .revision_evaluation import foldx_pool, repeats

PREDICTIONS={f'rx{r}_s{s}_{e}':e for r,n in enumerate((24,48,64))
             for s in range(1,n+1) for e in ('af3','esmfold2')}
FOLDX={f'rf{r}':'foldx' for r in range(3)}
from .revision_v2_runtime import CHILDREN as V2_CHILDREN
CHILDREN={**PREDICTIONS,**FOLDX,**V2_CHILDREN}


def validate_policies(p):
    keys={'s28','model_roles','foldx_pool','score','acceptance','hotspot','geometry','l4','esm_near_zero'}
    ensure(isinstance(p,dict) and set(p)==keys,'INVALID_REQUEST','Exact revision policy fields required')
    for key in ('score','acceptance','hotspot','geometry','l4'):
        ensure(p[key] is None,'INVALID_REQUEST','Unsupported runtime policy: '+key)
    ensure(p['esm_near_zero'] is None or c.finite(p['esm_near_zero']) and p['esm_near_zero']>=0,
           'INVALID_REQUEST','Invalid ESM near-zero configuration')
    for key in ('s28','model_roles','foldx_pool'):
        q=p[key]
        if q is None:continue
        ensure(isinstance(q,dict) and q.get('policy_status')=='ENGINEERING_UNREVIEWED'
               and isinstance(q.get('policy_id'),str) and 0<len(q['policy_id'])<=128,
               'INVALID_REQUEST','Explicit unreviewed policy identity required: '+key)
    s=p['s28']
    if s is not None:
        ensure(set(s)=={'policy_id','policy_status','required_set_id','required_check_ids'}
               and isinstance(s['required_set_id'],str) and bool(s['required_set_id'])
               and isinstance(s['required_check_ids'],list) and bool(s['required_check_ids'])
               and all(isinstance(k,str) and k for k in s['required_check_ids'])
               and len(set(s['required_check_ids']))==len(s['required_check_ids'])
               and {'constraints','esm_if1','structure'}<=set(s['required_check_ids']),
               'INVALID_REQUEST','S28 must declare constraints, ESM and structure; unavailable extra checks remain unknown')
    m=p['model_roles']
    if m is not None:
        ensure(set(m)=={'policy_id','policy_status','model_roles','min_plddt','selection_order'}
               and isinstance(m['model_roles'],dict) and set(m['model_roles'])=={'af3','esmfold2'}
               and all(v in ('mandatory','advisory') for v in m['model_roles'].values())
               and isinstance(m['min_plddt'],dict) and set(m['min_plddt'])=={'af3','esmfold2'}
               and all(c.finite(v) and 0<=v<=1 for v in m['min_plddt'].values())
               and m['selection_order'] in (['af3','esmfold2'],['esmfold2','af3']),
               'INVALID_REQUEST','Explicit model roles, normalized quality thresholds and selection order required')
    f=p['foldx_pool']
    if f is not None:
        ensure(set(f)=={'policy_id','policy_status','source_pool_id','required_check_ids','selection_rule_version','applicability'}
               and f['source_pool_id']=='revision_formal_pool'
               and isinstance(f['required_check_ids'],list) and bool(f['required_check_ids'])
               and all(isinstance(k,str) and k for k in f['required_check_ids'])
               and len(set(f['required_check_ids']))==len(f['required_check_ids'])
               and 's28' in f['required_check_ids'] and f['selection_rule_version']=='esm-desc-mutation-count-id-v1'
               and type(f['applicability']) is bool,
               'INVALID_REQUEST','Explicit FoldX source, S28 prerequisite, selection and applicability required')


def sequence(rt,rows,name):
    # Resolve by generating round and native sample identity, never list order.
    r,s,_=name.split('_',2);number=int(s[1:]);formal='formal'+r[2:]
    found=[v for v in rt.result(rows[formal]['job_id'])['generation']['records'] if v['sample_number']==number]
    ensure(len(found)==1,'OUTPUT_INVALID','Revision prediction candidate missing')
    return found[0]['sequence']


def assert_request(rt,row,expected):
    actual=decode(rt._request_bytes(rt.get(row['job_id'])))
    adjusted=dict(expected,timeout_seconds=actual['timeout_seconds'])
    ensure(0<actual['timeout_seconds']<=expected['timeout_seconds'] and actual==adjusted,
           'OUTPUT_INVALID','Revision child request or candidate association differs')


def reservation(ex,body,name,req):
    cfg=body['revision_config'];ledger=ex.setdefault('revision_ledger',budget.new(cfg))
    binding=ex.get('revision_bindings',{}).get(name)
    ensure(binding and binding['config_sha256']==sha(encode(cfg)), 'OUTPUT_INVALID','Missing revision child binding')
    expected=binding['request']
    ensure(dict(req,timeout_seconds=expected['timeout_seconds'])==expected and 0<req['timeout_seconds']<=expected['timeout_seconds'],
           'OUTPUT_INVALID','Revision admission differs from frozen request')
    stage=child_stage(name)
    return budget.reserve(ledger,cfg,name,stage,
                          binding['content_hashes'],internal_runs=5*len(binding['content_hashes']) if stage=='foldx' else 1)


def child_stage(name):
    from .revision_v2_runtime import stage
    return stage(name) if name in V2_CHILDREN else 'structure' if name in PREDICTIONS else 'foldx'


def stage_remaining(ex,body,name):
    """Reservations survive resume, but do not bypass elapsed stage limits."""
    stage=child_stage(name)
    limit=body['revision_config']['time_limits'].get(stage)
    if limit is None:return None
    attempts=[v for v in ex.get('revision_ledger',{}).get('attempts',{}).values() if v['stage']==stage]
    if any(v.get('execution_seconds') is None for v in attempts):return 0
    return max(0,int(limit-sum(v['execution_seconds'] for v in attempts)))


def bind(rt,jid,body,name,req,records):
    value=dict(config_sha256=sha(encode(body['revision_config'])),request=req,
               candidate_ids=[r['candidate_id'] for r in records],content_hashes=[r['content_hash'] for r in records])
    with rt._tx() as db:
        job=rt._job(db,jid)
        if job['stop_reason'] or job['state'] in TERMINAL:return False
        ex=rt._execution(db,jid);bindings=ex.setdefault('revision_bindings',{})
        ensure(name not in bindings or bindings[name]==value,'OUTPUT_INVALID','Revision child binding changed')
        bindings[name]=value;rt._execution_store(db,jid,ex)
    return True


def prediction_request(body,record,engine,msa=None):
    req=dict(protein_sequence=record['sequence'],user_sequence_id=body['user_sequence_id'],
             host_species=body['host_species'],seed=1,timeout_seconds=7200 if engine=='af3' else 900)
    if engine=='af3':req['msa_source']=msa
    return req


def prediction_observation(rt,jid,body,record,key):
    from .service import verified,source,prediction_source
    rows=rt.execution(jid)['nodes'];row=rows.get(key,{})
    empty=lambda reason,execution='NOT_RUN':dict(c.check('NOT_ASSESSED',reason,execution=execution),
                                               plddt=None,structure=None,source=None)
    if not row.get('job_id'):return empty(row.get('reason_code') or 'NOT_RUN')
    expected=rt.execution(jid)['revision_bindings'][key]
    ensure(expected['config_sha256']==sha(encode(body['revision_config']))
           and expected['candidate_ids']==[record['candidate_id']] and expected['content_hashes']==[record['content_hash']],
           'OUTPUT_INVALID','Revision prediction binding mismatch')
    engine=PREDICTIONS[key];req=prediction_request(body,record,engine,expected['request'].get('msa_source'))
    assert_request(rt,row,req)
    job=verified(rt,body,key,row['job_id'],rt.get(jid)['run_id'],rows)
    if job['state']!='succeeded':
        ensure(job['state'] not in TERMINAL or job['error_code'] in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'),
               job['error_code'] or 'OUTPUT_INVALID','Invalid prediction failure')
        return empty(job.get('error_code') or 'PENDING','ERROR' if job['state'] in TERMINAL else 'RUNNING')
    with rt._db() as db:
        value=prediction_source(engine).verified(rt,db,job['job_id'],record['sequence'],body['host_species'],job['run_id'],include_quality=True)
    q=value['quality']['structure']['mean_plddt']
    ensure(c.finite(q) and 0<=q<=1,'OUTPUT_INVALID','Invalid normalized model quality')
    from .revision_v2 import enabled
    threshold=body['revision_config']['policies']['model_roles']['min_plddt']
    threshold=threshold if enabled(body['revision_config']) else threshold[engine]
    return dict(c.check('PASS' if q>=threshold else 'FAIL'),
                plddt=q,structure=value['structure_artifact'],quality_artifact=value['quality_artifact'],
                source=source(rt,row),attempt_id=job['attempt_id'],
                shared_contract_version=c.VERSION,**{k:record[k] for k in c.IDENTITY})


def summarize(record,observations,policies):
    checks={'constraints':record['constraint_check'],'esm_if1':record['esm_if1']}
    roles=policies['model_roles'];s28=policies['s28']
    expected=route(len(record['sequence']),len(record['mutations']))
    required=[e for e in expected if roles and roles['model_roles'][e]=='mandatory']
    states=[observations.get(e,{}).get('check_status','NOT_ASSESSED') for e in required]
    status='FAIL' if 'FAIL' in states else 'PASS' if states and all(s=='PASS' for s in states) else 'NOT_ASSESSED'
    checks['structure']=c.check(status,*(['configuration_incomplete'] if not roles else []))
    ids=s28['required_check_ids'] if s28 else ['constraints','esm_if1','structure']
    states=[checks.get(k,{}).get('check_status','NOT_ASSESSED') for k in ids]
    status='FAIL' if 'FAIL' in states else 'PASS' if s28 and all(s=='PASS' for s in states) else 'NOT_ASSESSED'
    record['validation']=c.check(status,*(['configuration_incomplete'] if not s28 or not roles else []),
        evaluation_profile_id='original',required_set_id=s28['required_set_id'] if s28 else None,
        missing_check_ids=[k for k in ids if checks.get(k,{}).get('check_status','NOT_ASSESSED')=='NOT_ASSESSED'],
        policy_status='ENGINEERING_UNREVIEWED')
    record['checks']={k:v['check_status'] for k,v in checks.items()};record['checks']['s28']=status
    record['hard_check_status']=status;record['source_pool_id']='revision_formal_pool'
    record['structure_observations']=observations
    valid=[v['check_status'] for v in observations.values() if v['execution_status']=='SUCCEEDED']
    disagreement=len(set(valid))>1
    selected=next((e for e in (roles or {}).get('selection_order',[]) if e in observations and observations[e]['check_status']=='PASS'),None)
    record['structure']=observations[selected]['structure'] if selected else None
    record['structure_reason']=None if selected else 'NO_VERIFIED_PASSING_STRUCTURE'
    record['ranking_context']['model_disagreement']=disagreement
    record['ranking_context']['evidence_group']='E' if status=='FAIL' else 'C'
    if status=='FAIL':record['acceptance_status']=record['provisional_acceptance_status']='FAIL'


def selected_foldx(records,cfg,ledger,jid):
    from . import revision_v2
    if revision_v2.enabled(cfg):
        used={h for v in ledger['reservations'].values() if v['stage']=='foldx' for h in v['objects']}
        return revision_v2.select([r for r in records if r['content_hash'] not in used],max(0,cfg['foldx_variant_max']-len(used)),foldx=True)
    p=cfg['policies']['foldx_pool']
    used={h for v in ledger['reservations'].values() if v['stage']=='foldx' for h in v['objects']}
    available=[r for r in records if r['disposition']=='FORMAL_POOL' and r['content_hash'] not in used]
    if p is None:return foldx_pool(available,None,cfg['foldx_variant_max'],mode='variant_score',task_id=jid)
    if not p['applicability']:
        return dict(mode='variant_score',task_id=jid,results=[],**c.check('NOT_APPLICABLE','FOLDX_INAPPLICABLE',execution='NOT_RUN'))
    eligible=[r for r in available if all(r.get('checks',{}).get(k)=='PASS' for k in p['required_check_ids'])]
    eligible.sort(key=lambda r:(-r['esm_if1']['score'],len(r['mutations']),r['candidate_id']))
    selected=eligible[:max(0,cfg['foldx_variant_max']-len(used))]
    if eligible and not selected:
        return dict(mode='variant_score',task_id=jid,results=[],**c.check('NOT_ASSESSED','SKIPPED_BUDGET',execution='NOT_RUN'))
    return foldx_pool(available,dict(p,selected_candidate_ids=[r['candidate_id'] for r in selected]),
                      cfg['foldx_variant_max'],mode='variant_score',task_id=jid)


def foldx_request(body,data,records):
    return dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
        structure_artifact=data['snapshot']['wt_structure_id'],mode='buildmodel',
        fixed_positions=[p for p in range(1,len(body['protein_sequence'])+1) if p not in data['snapshot']['eligible_positions']],
        scan_positions=[],variants=[dict(variant_id=r['candidate_id'],mutations=r['mutations']) for r in records],
        scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE',source_id='revision:'+sha(encode(body['revision_config']))),timeout_seconds=14400)


def foldx_observation(rt,jid,body,data,key,records):
    from .service import verified,source
    from ..esm_if1.source import registered
    from ..foldx.source import sources
    from ..foldx.result import parse
    rows=rt.execution(jid)['nodes'];row=rows.get(key,{})
    if not row.get('job_id'):
        return {r['candidate_id']:dict(c.check('NOT_ASSESSED',row.get('reason_code') or 'NOT_RUN',execution='NOT_RUN'),
            mean=None,std=None,valid_count=0) for r in records}
    req=foldx_request(body,data,records);assert_request(rt,row,req)
    job=verified(rt,body,key,row['job_id'],rt.get(jid)['run_id'],rows)
    if job['state']!='succeeded':
        ensure(job['state'] not in TERMINAL or job['error_code'] in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'),
               job['error_code'] or 'OUTPUT_INVALID','Invalid FoldX failure')
        return {r['candidate_id']:dict(c.check('NOT_ASSESSED',job.get('error_code') or 'PENDING',
            execution='ERROR' if job['state'] in TERMINAL else 'RUNNING'),mean=None,std=None,source=source(rt,row)) for r in records}
    with rt._db() as db:
        _,_,value,request,files=registered(rt,db,source(rt,row)['artifact'],'t01.real.foldx')
        prepared,_=sources(rt,db,request,expected_run_id=job['run_id'])
    ensure(all(files.get(k)==v for k,v in prepared.items()),'HASH_MISMATCH','FoldX executed WT inputs differ')
    # Projection must be byte-identical to the WT actually used for generation.
    for record in records:
        with rt._db() as db:
            _,_,_,_,native=registered(rt,db,record['generation_source'],'t01.real.proteinmpnn')
        ensure(files['native/target.pdb']==native['native/target.pdb'],'HASH_MISMATCH','FoldX WT differs from generating WT')
    parsed=parse(request,files)
    repair=None
    if 'output/runtime.json' in files:
        native_runtime=decode(files['output/runtime.json'])
        repair=dict(external_calls=1,repair_pdb_calls=1,repaired_pdb=parsed['repaired_pdb'],
                    command=native_runtime['commands']['repair'],cache_hit=False)
    ensure(value['variant_ddg']==parsed['rows'],'OUTPUT_INVALID','FoldX published scores differ from native repeats')
    by_id={r['variant_id']:r for r in parsed['rows']}
    ensure(len(by_id)==len(parsed['rows']) and set(by_id)<={r['candidate_id'] for r in records},
           'OUTPUT_INVALID','FoldX result candidate identities differ')
    out={}
    for record in records:
        cid=record['candidate_id'];native=by_id.get(cid)
        if native is None:
            ensure(any(v['variant_id']==cid and v['mapping_failed'] for v in decode(files['native/payload.json'])['variants']),
                   'OUTPUT_INVALID','FoldX candidate result missing without mapping failure')
        attempts=[] if native is None else [dict(repeat_id=f'{job["attempt_id"]}:{cid}:{i}',value=v,verified=True,
            execution_status='SUCCEEDED') for i,v in enumerate(native['native_ddg_runs'])]
        out[cid]=dict(repeats(5,attempts),source=source(rt,row),attempt_id=job['attempt_id'],
            native_result=native,reason_codes=['MAPPING_FAILED'] if native is None else [],
            policy_status='ENGINEERING_UNREVIEWED',shared_contract_version=c.VERSION,**{k:record[k] for k in c.IDENTITY})
        from .revision_v2 import enabled
        if enabled(body['revision_config']):out[cid].update(repair_observation=repair,policy_status='pending_calibration')
    return out


def enrich(rt,jid,body,data,records):
    from . import revision_v2
    cfg=body['revision_config'];ex=rt.execution(jid)
    for record in records:
        if record['disposition']!='FORMAL_POOL':
            if revision_v2.enabled(cfg):revision_v2.s28(record,{},cfg)
            continue
        observations={}
        for key,binding in ex.get('revision_bindings',{}).items():
            if key in PREDICTIONS and binding['candidate_ids']==[record['candidate_id']]:
                observations[PREDICTIONS[key]]=prediction_observation(rt,jid,body,record,key)
        # Missing scheduled engines remain visible (asset/length/budget skips).
        for allocation in ex.get('revision_allocations',{}).values():
            for item in allocation:
                if item['candidate_id']==record['candidate_id']:
                    for key in item['keys']:
                        if PREDICTIONS[key] not in observations:
                            observations[PREDICTIONS[key]]=prediction_observation(rt,jid,body,record,key)
        from . import revision_v2
        if revision_v2.enabled(cfg):revision_v2.s28(record,observations,cfg)
        else:summarize(record,observations,cfg['policies'])
        record['foldx']=dict(c.check('NOT_ASSESSED','NOT_SELECTED_OR_POLICY_MISSING',execution='NOT_RUN'),mean=None,std=None)
    for key,binding in ex.get('revision_bindings',{}).items():
        if key not in FOLDX:continue
        selected=[next(r for r in records if r['candidate_id']==cid and r['disposition']=='FORMAL_POOL') for cid in binding['candidate_ids']]
        observations=foldx_observation(rt,jid,body,data,key,selected)
        for r in selected:
            if r['candidate_id'] in observations:r['foldx']=observations[r['candidate_id']]
    if revision_v2.enabled(cfg):
        from .revision_v2_runtime import enrich as enrich_v2
        enrich_v2(rt,jid,body,data,records)


def tick(rt,jid,body,data,records,index,structure_only=False):
    from .service import _record,worker,source
    from .revision_controller import child
    cfg=body['revision_config'];pol=cfg['policies'];ex=rt.execution(jid)
    if pol['model_roles'] is None or pol['s28'] is None or pol['esm_near_zero'] is None:return 'configuration_incomplete'
    current=source(rt,ex['nodes'][f'formal{index}'])['artifact']
    round_records=[r for r in records if r['generation_source']==current]
    from .revision_v2 import enabled
    if enabled(cfg):
        from .revision_sequence import attach
        attach(round_records)
    key=str(index);allocation=ex.get('revision_allocations',{}).get(key)
    if allocation is None:
        ledger=ex.get('revision_ledger',budget.new(cfg));used={h for v in ledger['reservations'].values() if v['stage']=='structure' for h in v['objects']}
        ids=select_structure([r for r in records if r['content_hash'] not in used and r['generation_source']==current],
                             {r['candidate_id']:r['esm_if1'] for r in records if r['disposition']=='FORMAL_POOL'},max(0,cfg['structure_eval_max']-len(used)),
                             require_sequence_metrics=enabled(cfg))
        from .revision_structure import scheduled_engines
        allocation=[dict(candidate_id=r['candidate_id'],keys=[f'rx{index}_s{r["sample_number"]}_{e}' for e in scheduled_engines(len(r['sequence']),len(r['mutations']),cfg)])
                    for r in records if r['disposition']=='FORMAL_POOL' and r['candidate_id'] in ids
                    and scheduled_engines(len(r['sequence']),len(r['mutations']),cfg)]
        with rt._tx() as db:
            job=rt._job(db,jid)
            if job['stop_reason'] or job['state'] in TERMINAL:return None
            ex=rt._execution(db,jid)
            # Reserve all required engines for a candidate atomically. Failed
            # second-engine reservation must not spend its first-engine budget.
            import copy
            ledger=ex.setdefault('revision_ledger',budget.new(cfg))
            for item in allocation:
                record=next(r for r in records if r['candidate_id']==item['candidate_id'])
                tentative=copy.deepcopy(ledger)
                if all(budget.reserve(tentative,cfg,n,'structure',[record['content_hash']]) for n in item['keys']):
                    ledger.clear();ledger.update(tentative)
                else:
                    for n in item['keys']:
                        ex['nodes'][n]=dict(node_id='N12',job_id=None,state='skipped',origin=None,reason_code='SKIPPED_BUDGET')
            ex.setdefault('revision_allocations',{})[key]=allocation;rt._execution_store(db,jid,ex)
    by_id={r['candidate_id']:r for r in records if r['disposition']=='FORMAL_POOL'}
    for item in allocation:
        record=by_id[item['candidate_id']]
        for name in item['keys']:
            if rt.get(jid)['stop_reason']:return None
            row=rt.execution(jid)['nodes'].get(name,{})
            if row.get('state')=='skipped':continue
            engine=PREDICTIONS[name];msa=None
            if not 9<=len(record['sequence'])<=worker(name).MAX_AA:
                _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='ENGINE_VERIFIED_LENGTH_LIMIT'));continue
            if engine=='af3':
                from .msa_reuse import ready
                msa,reason=ready(rt,jid,body)
                if reason=='WAITING':return None
                if reason:
                    _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code=reason));continue
            req=prediction_request(body,record,engine,msa)
            if not bind(rt,jid,body,name,req,[record]):return None
            try:
                if not child(rt,jid,body,name,req):return None
            except RuntimeFault as exc:
                if exc.code!='ASSET_MISSING':raise
                _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='ENGINE_ASSET_UNAVAILABLE'))
    enrich(rt,jid,body,data,records)
    if structure_only:return 'STRUCTURE_STAGE_COMPLETE'
    ledger=rt.execution(jid).get('revision_ledger',budget.new(cfg));name=f'rf{index}'
    binding=rt.execution(jid).get('revision_bindings',{}).get(name)
    pool=selected_foldx(round_records,cfg,ledger,jid)
    selected=[by_id[cid] for cid in binding['candidate_ids']] if binding else pool['results']
    if selected:
        req=foldx_request(body,data,selected)
        if not bind(rt,jid,body,name,req,selected):return None
        try:
            if not child(rt,jid,body,name,req):return None
        except RuntimeFault as exc:
            if exc.code!='ASSET_MISSING':raise
            _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='ENGINE_ASSET_UNAVAILABLE'))
    enrich(rt,jid,body,data,records)
    if pol['foldx_pool'] is None:return 'configuration_incomplete'
    if 'SKIPPED_BUDGET' in pool.get('reason_codes',[]):return 'budget_exhausted'
    if any(r.get('foldx',{}).get('execution_status')!='SUCCEEDED' for r in selected):return 'incomplete_only'
    if any(r['validation']['check_status']=='PASS' for r in round_records):return 'S28_ORIGINAL_PASS'
    formal=[r for r in round_records if r['disposition']=='FORMAL_POOL']
    if formal and all(r['validation']['check_status']=='FAIL' for r in formal):
        return 'all_rejected'
    return 'incomplete_only'
