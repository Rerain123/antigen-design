"""Executable derived contract for expert v2, §§6–13 (2026-09-29).

Source documents remain read-only. Values are pending calibration; this
version never confers scientific release or rewrites v1 observations.
"""
from decimal import Decimal
from ...common import encode,ensure,sha
from .revision_contract import check,finite,IDENTITY
from .revision_evaluation import axes,rank_groups,round_robin_groups,task_acceptance
from .revision_structure import LEGACY_MODEL_POLICY,SINGLE_MODEL_POLICY

RULE='expert-revision-20260929-v2'
REQUIRED=['chk_seq_valid','chk_permission','chk_budget','chk_chem','chk_esm_delta','chk_struct_quality']
DIMS=['solubility','aggregation','ph_stability','tag_exposure','expressibility']
WEIGHTS={'general':dict(dev=.50,stab=.10,epi=.30,burden=.10),
 'solubility':dict(dev=.60,stab=.10,epi=.20,burden=.10),
 'thermostability':dict(dev=.25,stab=.45,epi=.20,burden=.10)}
SELECTION='v2-stage-complete-dimension-group-dev-roundrobin-id-v2'
MIGRATION={'SOP:S28':'s28-orig-A','SKILL:R56/L1':'l1-perm-A-20260929',
 'SOP:T01/step19/L1':'l1-perm-A-20260929','phase1:N13':'l1-perm-A-20260929',
 'SOP:S28/geometry':'geom-audit-A-20260929','SOP:S08/R04':'primary_af3_secondary_c11',
 'Schema:S28/C18':'t01-core-20260929-v1','SOP:T01/step19b':'evaluation_pool',
 'SOP:S40/step20':'cmp-A-2026-09-29','SKILL:SC10':'acc-A-2026-09-29'}


def enabled(cfg):return cfg.get('rule_version')==RULE


def policies(objective='general',geometry='geometry_audit',model_policy=LEGACY_MODEL_POLICY):
    ensure(model_policy in (LEGACY_MODEL_POLICY,SINGLE_MODEL_POLICY),'INVALID_REQUEST','Unknown structure model policy')
    return dict(s28=dict(required_set_id='s28-orig-A',required_check_ids=REQUIRED,
                         supply_fallback=model_policy==LEGACY_MODEL_POLICY,threshold_status='pending_calibration'),
        model_roles=dict(model_role_policy=model_policy,min_plddt=.50,
            **(dict(comparison_policy='same_prediction_engine_required',wt_esmfold_reference='DEFERRED')
               if model_policy==SINGLE_MODEL_POLICY else {})),
        esm_near_zero=.01,geometry=dict(policy_version='geom-audit-A-20260929',mode=geometry),
        hotspot=dict(policy_version='l1-perm-A-20260929',migration=dict(MIGRATION,**{'SOP:S08/R04':model_policy})),
        l4=dict(policy_version='l4-wt-raw-A-20260929',delta_span_min=.05,delta_max=.2,
                threshold_status='pending_calibration',selection_rule_id=SELECTION),
        foldx_pool=dict(source_pool_id='evaluation_pool',selection_rule_id=SELECTION,reference_tasks=False),
        score=dict(score_policy_version='cmp-A-2026-09-29',objective=objective,weights=WEIGHTS[objective],
                   threshold_status='pending_calibration'),
        acceptance=dict(acceptance_config_id='acc-A-2026-09-29',threshold=.30,
                        threshold_status='pending_calibration',missing_policy='require_all'))


def config(config_id,objective='general',geometry='geometry_audit',*,model_policy=LEGACY_MODEL_POLICY):
    from .revision_contract import suggested_config
    cfg=suggested_config(config_id);cfg.update(rule_version=RULE,policies=policies(objective,geometry,model_policy));return cfg


def validate(p):
    ensure(isinstance(p,dict) and isinstance(p.get('score'),dict) and isinstance(p.get('geometry'),dict),
           'INVALID_REQUEST','v2 policy configuration incomplete')
    objective=p['score'].get('objective');geometry=p['geometry'].get('mode')
    model_policy=(p.get('model_roles') or {}).get('model_role_policy')
    ensure(objective in WEIGHTS and geometry in ('geometry_audit','legacy_hard')
           and model_policy in (LEGACY_MODEL_POLICY,SINGLE_MODEL_POLICY) and p==policies(objective,geometry,model_policy),
           'INVALID_REQUEST','v2 contract_incompatible: undeclared policy, threshold, migration or calibration claim')


def aggregate(values):
    states=[v['check_status'] for v in values]
    return check('FAIL' if 'FAIL' in states else 'NOT_ASSESSED' if not states or 'NOT_ASSESSED' in states
                 else 'PASS' if 'PASS' in states else 'NOT_APPLICABLE')


def esm(score,baseline):
    if not finite(score) or not finite(baseline) or abs(Decimal(str(baseline)))<Decimal('.01'):
        return check('NOT_ASSESSED','denominator_below_validity_bound',score=score,baseline=baseline,error_category=None)
    delta=(Decimal(str(score))-Decimal(str(baseline)))/abs(Decimal(str(baseline)))
    return check('PASS' if delta>=Decimal('-.10') else 'FAIL',score=score,baseline=baseline,
                 delta_pct=float(delta*100),threshold_status='pending_calibration')


def supplier(record,observations,cfg=None):
    from .revision_structure import route
    engines=route(len(record['sequence']),len(record['mutations']),cfg)
    valid=lambda v:v.get('execution_status')=='SUCCEEDED' and finite(v.get('plddt')) and 0<=v['plddt']<=1
    if cfg and cfg['policies']['model_roles']['model_role_policy']==SINGLE_MODEL_POLICY:
        engine=engines[0];v=observations.get(engine,{})
        available=valid(v)
        return check('NOT_ASSESSED' if not available else 'PASS' if v['plddt']>=.5 else 'FAIL',
            *([] if available else ['NO_VALID_STRUCTURE_SUPPLIER']),
            execution='SUCCEEDED' if available else v.get('execution_status','NOT_RUN'),
            evidence_supplier='primary' if available else None,selected=engine if available else None,
            degraded=False,model_disagreement=False)
    selected=None;label=None
    if engines==['esmfold2']:
        return check('NOT_ASSESSED','C11_ONLY_SUPPLY_UNDECLARED',execution='NOT_RUN',evidence_supplier=None,selected=None)
    a=observations.get('af3',{});b=observations.get('esmfold2',{})
    if valid(a):selected='af3';label='primary'
    elif len(engines)==2 and valid(b):selected='esmfold2';label='secondary'
    v=observations.get(selected,{})
    disagreement=valid(a) and valid(b) and (a['plddt']>=.5)!=(b['plddt']>=.5)
    return check('NOT_ASSESSED' if selected is None else 'PASS' if v['plddt']>=.5 else 'FAIL',
        *(['NO_VALID_STRUCTURE_SUPPLIER'] if selected is None else []),
        execution='SUCCEEDED' if selected else 'ERROR' if any(o.get('execution_status')=='ERROR' for o in observations.values()) else 'NOT_RUN',
        evidence_supplier=label,selected=selected,degraded=label=='secondary',model_disagreement=disagreement)


def s28(record,observations,cfg):
    verdict=record['constraint_check'];reasons=verdict['reason_codes'];valid='INVALID_SEQUENCE' not in reasons
    checks={'chk_seq_valid':check('PASS' if valid else 'FAIL')}
    for name,violations in [('chk_permission',{'PERMISSION_VIOLATION','SAMPLING_FIXED_CHANGED'}),
                            ('chk_budget',{'MUTATION_BUDGET_EXCEEDED'}),('chk_chem',{'CHEMICAL_HARD_FAIL'})]:
        checks[name]=check('NOT_ASSESSED' if not valid else 'FAIL' if set(reasons)&violations else 'PASS')
    checks['chk_esm_delta']=record['esm_if1'];checks['chk_struct_quality']=supplier(record,observations,cfg)
    checks['chk_geometry']=record.get('geometry_check',check('NOT_ASSESSED','GEOMETRY_UNAVAILABLE'))
    required=REQUIRED+(['chk_geometry'] if cfg['policies']['geometry']['mode']=='legacy_hard' else [])
    result=aggregate([checks[k] for k in required]);result.update(required_set_id='s28-orig-A',
        check_summaries=[dict(v,check_id=k,role='mandatory' if k in required else 'advisory',
            **{f:record[f] for f in ('candidate_id','content_hash','reference_id','calculation_config_id','rule_version')},
            evaluation_profile_id='original',stage_id='S28',target_scope_id=record['candidate_id'],required_set_id='s28-orig-A') for k,v in checks.items()],
        evaluation_profile_id='original',policy_status='pending_calibration')
    for summary in result['check_summaries']:
        k=summary['check_id']
        origins=([record.get('esm_source')] if k=='chk_esm_delta' else
                 [(o.get('source') or {}).get('artifact') for o in observations.values()] if k=='chk_struct_quality' else
                 [record.get('generation_source')])
        refs=[o for o in origins if o and o.get('artifact_id') and o.get('sha256')]
        summary['selected_attempt_ids']=sorted({o['attempt_id'] for o in refs if o.get('attempt_id')})
        summary['selected_artifact_refs']=[dict(artifact_id=o['artifact_id'],content_hash=o['sha256']) for o in refs]
        summary['summary_id']='summary-'+sha(encode(summary))
    record['validation']=result;record['checks']={k:v['check_status'] for k,v in checks.items()};record['checks']['s28']=result['check_status']
    sup=checks['chk_struct_quality'];selected=sup['selected'];record['structure_observations']=observations
    record['structure']=observations[selected]['structure'] if selected else None
    record['structure_reason']=None if selected else 'NO_VALID_STRUCTURE_SUPPLIER'
    record['evidence_supplier']=sup['evidence_supplier'];record['structure_degraded']=sup.get('degraded',False)
    record['hard_check_status']=result['check_status'];record['source_pool_id']='evaluation_pool'
    record['ranking_context']['model_disagreement']=sup.get('model_disagreement',False)


def protection(wt,record,snap,w,v,*,same_engine_required=False):
    from ..epitope_protection.compute import positions,rsa_delta,geometry
    hot=w['hotspots'];e4=w['e4_positions'];prior=w.get('iedb_prior')
    complete=hot is not None and prior is not None and prior.get('e4_status') in ('computed','not_applicable')
    ps=sorted(set(positions(hot or [],len(wt)))|set(e4));mut={m['position']:m for m in record['mutations']}
    permissions={r['position']:r for r in snap['records']}
    violations=[p for p in ps if p in mut and (permissions[p]['design_permission']=='FIXED' or
                 mut[p]['mut'] not in permissions[p]['allowed_residues'])]
    l1=check('FAIL' if violations else 'NOT_ASSESSED' if not complete else 'PASS' if ps else 'NOT_APPLICABLE',
        violations=violations,changed_positions=sorted(set(ps)&set(mut)))
    literal=all(wt[p-1]==record['sequence'][p-1] for p in ps) if complete and ps else None
    wt_engine=w.get('prediction_engine');variant_engine=v.get('prediction_engine')
    comparable=not same_engine_required or (wt_engine in ('af3','esmfold2') and wt_engine==variant_engine)
    unavailable='SAME_ENGINE_WT_REFERENCE_REQUIRED' if not comparable else 'QUALITY_UNAVAILABLE'
    quality=comparable and w['quality_condition'] is True and v['quality_condition'] is True
    r=rsa_delta(w['rsa'],v['rsa'],ps) if quality else {'value':None,'reason':unavailable}
    l2=check('NOT_APPLICABLE' if complete and not ps else 'NOT_ASSESSED' if not complete or r['value'] is None else 'PASS' if Decimal(str(r['value']))>Decimal('-.15') else 'FAIL',observation=r)
    targets=[('hotspot',positions([h],len(wt))) for h in hot or []]+([('e4',e4)] if e4 else [])
    domains=[('domain',positions([d],len(wt))) for d in w['domains'] or []]
    def objects(items,known):
        out=[];seen=set()
        for kind,pp in items:
            if tuple(pp) in seen:continue
            seen.add(tuple(pp));g=geometry(w['geometry'],v['geometry'],pp) if quality else {'value':None,'reason':unavailable}
            out.append(dict(kind=kind,positions=pp,observation=g,**check('NOT_ASSESSED' if g['value'] is None else 'PASS' if g['value']<2 else 'FAIL')))
        overall=aggregate(out if known else out+[check('NOT_ASSESSED','OBJECT_INVENTORY_INCOMPLETE')]) if out or not known else check('NOT_APPLICABLE','CONFIRMED_EMPTY')
        return dict(overall,objects=out,max_rmsd=max((o['observation']['value'] for o in out if o['observation']['value'] is not None),default=None))
    l3=objects(targets,complete);aux=objects(domains,w['domains'] is not None)
    structural=aggregate([l1,l2,l3]) if ps or not complete else check('NOT_APPLICABLE','no_verifiable_targets')
    result=dict(structural,structural_preservation=structural['passed'],l1=l1,l1_identity_pass=literal,l2=l2,l3=l3,
        auxiliary_geometry_status=dict(aux,auxiliary_scope_id='domains-'+sha(encode(w['domains']))),target_positions=ps,target_availability='COMPLETE' if complete else 'UNKNOWN',
        target_scope_id='V-'+sha(encode(dict(hotspots=hot,e4=e4))),
        l1_policy_version='l1-perm-A-20260929',new_l1_pass_legacy_identity_fail=l1['passed'] is True and literal is False)
    if same_engine_required:
        result['structure_comparison']=dict(wt_engine=wt_engine,variant_engine=variant_engine,allowed=comparable,
            reason_code=None if comparable else unavailable)
    if complete and not ps:
        # The inputs come from recursively verified and frozen WT sources.
        # Empty lists are evidence; absent/partial inventories are not.
        proof=dict(policy_version='empty-target-applicability-v1',reason_code='CONFIRMED_EMPTY_TARGETS',
            binding={k:record[k] for k in IDENTITY},target_scope_id=result['target_scope_id'],
            wt_sequence_sha256=sha(wt.encode()),hotspots=hot,e4_positions=e4,e4_status=prior['e4_status'],
            source_receipts_sha256=sha(encode(w.get('source_receipts',{}))))
        proof['evidence_id']='applicability-'+sha(encode(proof))
        result['applicability_evidence']=proof
    return result


def confirmed_empty(protection,record=None):
    """Consume only the scoped applicability statement rebuilt by protection()."""
    proof=protection.get('applicability_evidence')
    if not isinstance(proof,dict):return False
    if (protection.get('check_status')!='NOT_APPLICABLE' or protection.get('target_availability')!='COMPLETE'
        or protection.get('target_positions')!=[]
        or any(protection.get(k,{}).get('check_status')!='NOT_APPLICABLE' for k in ('l1','l2','l3'))):return False
    expected_scope='V-'+sha(encode(dict(hotspots=[],e4=[])))
    if (proof.get('policy_version')!='empty-target-applicability-v1'
        or proof.get('reason_code')!='CONFIRMED_EMPTY_TARGETS'
        or proof.get('hotspots')!=[] or proof.get('e4_positions')!=[]
        or proof.get('e4_status') not in ('computed','not_applicable')
        or proof.get('target_scope_id')!=expected_scope or protection.get('target_scope_id')!=expected_scope):return False
    if record is not None and proof.get('binding')!={k:record[k] for k in IDENTITY}:return False
    return proof.get('evidence_id')=='applicability-'+sha(encode({k:v for k,v in proof.items() if k!='evidence_id'}))


def l4_not_applicable(protection,l4,record=None):
    return (confirmed_empty(protection,record) and l4.get('check_status')=='NOT_APPLICABLE'
            and l4.get('prediction_preservation') is None
            and l4.get('applicability_evidence')==protection['applicability_evidence'])


def l4(wt_scores,variant_scores,protection,hotspots,profiles_match=True):
    ps=protection['target_positions'];extra=dict(prediction_preservation=None,delta_B=None,error_category=None)
    if confirmed_empty(protection):
        return check('NOT_APPLICABLE','CONFIRMED_EMPTY_TARGETS',
                     applicability_evidence=protection['applicability_evidence'],**extra)
    if not profiles_match:return check('NOT_ASSESSED','PREDICTOR_PROFILE_MISMATCH',**extra)
    if not ps or protection['target_availability']!='COMPLETE':return check('NOT_ASSESSED','NO_COMPLETE_TARGETS',**extra)
    if not wt_scores or not variant_scores or len(wt_scores)!=len(variant_scores) or any(not finite(x) for x in wt_scores):
        return check('NOT_ASSESSED','PREDICTION_UNAVAILABLE',**extra)
    lo=min(Decimal(str(x)) for x in wt_scores);hi=max(Decimal(str(x)) for x in wt_scores);span=hi-lo
    if span<Decimal('.05'):return check('NOT_ASSESSED','span_below_validity_bound',b_min=float(lo),b_max=float(hi),**extra)
    if any(p>len(variant_scores) or not finite(variant_scores[p-1]) for p in ps):return check('NOT_ASSESSED','TARGET_SCORE_MISSING',**extra)
    z=lambda x:max(Decimal(0),min(Decimal(1),(Decimal(str(x))-lo)/span))
    rows=[dict(position=p,wt=wt_scores[p-1],variant=variant_scores[p-1],raw_delta=float(Decimal(str(variant_scores[p-1]))-Decimal(str(wt_scores[p-1]))),
               normalized_delta=float(abs(z(variant_scores[p-1])-z(wt_scores[p-1])))) for p in ps]
    delta=sum(abs(z(variant_scores[p-1])-z(wt_scores[p-1])) for p in ps)/len(ps)
    return check('PASS' if delta<Decimal('.2') else 'FAIL',prediction_preservation=delta<Decimal('.2'),delta_B=float(delta),
        b_min=float(lo),b_max=float(hi),rows=rows,max_position_delta=max(r['normalized_delta'] for r in rows),
        clip_positions=sum(Decimal(str(variant_scores[p-1]))<lo or Decimal(str(variant_scores[p-1]))>hi for p in ps),
        hotspot_deltas=[dict(start=h['start'],end=h['end'],mean_delta=sum(r['normalized_delta'] for r in rows if h['start']<=r['position']<=h['end'])/(h['end']-h['start']+1)) for h in hotspots or []],
        threshold_status='pending_calibration',soft_penalty=.1 if delta>=Decimal('.2') else 0.)


def dimension_mode(d):
    value=d.get('value');value=value if isinstance(value,dict) else {}
    return dict(source=d.get('source'),**{k:value[k] for k in ('tool','method','mode','calculation_mode') if k in value})


def freeze(dimensions,source,weights=None):
    usable=[k for k in DIMS if dimensions.get(k,{}).get('reliable') is True and finite(dimensions[k].get('normalized_score'))]
    exclusions={k:dimensions.get(k,{}).get('exclusion_reason') or 'WT_DIMENSION_UNAVAILABLE' for k in DIMS if k not in usable}
    weights={k:(weights or {}).get(k,1.) for k in usable}
    ensure(all(finite(w) and w>=0 for w in weights.values()),'OUTPUT_INVALID','Invalid frozen WT dimension weight')
    base=dict(M0=usable,exclusions=exclusions,wt_source=source,normalization='S40-v9-v2',frozen_before_generation=True,weights=weights,
              calculation_modes={k:dimension_mode(dimensions[k]) for k in usable})
    return dict(base,dimension_set_id='cmp-'+sha(encode(base)),acceptance_dimensions=usable+['stability_ddg'],
                acceptance_dimension_set_id='acc-'+sha(encode(dict(base,required_stability=True))))


def score_record(record,frozen,cfg):
    dims=record.get('developability_dimensions',{});m=frozen['M0']
    observed={k:float(d['normalized_score']) for k,d in dims.items() if k in DIMS and d.get('reliable') is True and finite(d.get('normalized_score'))}
    usable={k:v for k,v in observed.items() if k in m and dimension_mode(dims[k])==frozen['calculation_modes'][k]}
    ensure(all(0<=v<=1 for v in usable.values()),'OUTPUT_INVALID','Unbounded normalized dimension')
    complete=bool(m) and all(k in usable for k in m)
    def mean(keys):
        total=sum(frozen['weights'][k] for k in keys)
        return sum(usable[k]*frozen['weights'][k] for k in keys)/total if total>0 else None
    dev=mean(m) if complete else None
    rdev=[k for k in m if k in usable];partial=mean(rdev)
    p=record.get('protection',{});l=record.get('l4',{});fx=record.get('foldx',{})
    ddg=fx.get('mean') if fx.get('execution_status')=='SUCCEEDED' and fx.get('valid_count')==5 else None
    aux=p.get('auxiliary_geometry_status',{}).get('check_status')
    protection_ready=p.get('check_status')=='PASS' or confirmed_empty(p,record)
    hard='FAIL' if record['validation']['check_status']=='FAIL' or p.get('check_status')=='FAIL' or aux=='FAIL' else 'PASS' if record['validation']['check_status']=='PASS' and protection_ready and aux in ('PASS','NOT_APPLICABLE') else 'NOT_ASSESSED'
    evidence=hard=='PASS' and p.get('check_status')=='PASS' and l.get('prediction_preservation') is not None and complete and finite(ddg)
    ax=axes(dev if complete else partial,ddg,p.get('structural_preservation'),l.get('prediction_preservation'),len(record['mutations']),record['budget_B'])
    accept_values=[usable[k] for k in m if k in usable]+([ax['stab']] if ax['stab'] is not None else [])
    acceptance=sum(accept_values)/len(accept_values) if evidence and len(accept_values)==len(frozen['acceptance_dimensions']) else None
    desc=dict(observed)
    if ax['stab'] is not None:desc['stability_ddg']=ax['stab']
    dw=record.get('description_weights') or {k:1. for k in desc};dt=sum(dw.get(k,0.) for k in desc)
    record.update(description_score=sum(val*dw.get(k,0.) for k,val in desc.items())/dt if dt>0 else None,
        acceptance_score=acceptance,acceptance_status='FAIL' if hard=='FAIL' else 'NOT_ASSESSED',
        provisional_acceptance_status='FAIL' if hard=='FAIL' else 'NOT_ASSESSED' if acceptance is None else 'PASS' if acceptance>=.30 else 'FAIL',
        comparison_score=None,axes=ax,evidence_group='E' if hard=='FAIL' else 'A' if evidence else 'C',
        evaluation_profile_id='original',score_context_id=sha(encode(dict(set=frozen['dimension_set_id'],available=rdev,policy=cfg['policies']['score'],
            protection_applicability='NOT_APPLICABLE' if confirmed_empty(p,record) else 'APPLICABLE' if p.get('check_status')=='PASS' else 'UNKNOWN'))),
        calculation_mode='v2-fixed-WT',soft_penalty_reasons=(['L4_PROFILE_CHANGED'] if l.get('prediction_preservation') is False else [])+record.get('permission_soft_reasons',[]),
        comparison_dimension_set_id=frozen['dimension_set_id'],acceptance_dimension_set_id=frozen['acceptance_dimension_set_id'],
        missing_frozen_dimensions=[k for k in m if k not in usable],threshold_status='pending_calibration',final_evidence_complete=evidence,
        nonstability_score=dev if complete else partial,nonstability_dimensions=rdev,
        stage_evidence_complete=hard=='PASS' and complete)
    record['ranking_context'].update(evidence_group=record['evidence_group'],rank=None,group_rank=None,group_id=None)
    record['score_contexts']=dict(description=dict(dimensions=list(desc),weights=dw,missing_policy='exclude_unavailable'),
        comparison=dict(dimension_set_id=frozen['dimension_set_id'],dimensions=m,available_dimensions=rdev,weights=frozen['weights'],
            calculation_modes=frozen['calculation_modes'],normalization=frozen['normalization'],policy=cfg['policies']['score'],missing_policy='separate_incomplete_groups'),
        acceptance=dict(dimension_set_id=frozen['acceptance_dimension_set_id'],dimensions=frozen['acceptance_dimensions'],
            weights={k:1. for k in frozen['acceptance_dimensions']},policy=cfg['policies']['acceptance']))


def select(records,limit,*,foldx=False):
    groups={};eligible=[]
    for r in records:
        p=r.get('protection',{});l=r.get('l4',{})
        if p.get('structure_comparison',{}).get('allowed') is False:continue
        if r['disposition']!='FORMAL_POOL' or r['validation']['check_status']!='PASS' or p.get('check_status')=='FAIL' or p.get('auxiliary_geometry_status',{}).get('check_status')=='FAIL':continue
        if foldx:
            protected=p.get('check_status')=='PASS' or confirmed_empty(p,r)
            evaluated=(l.get('check_status') in ('PASS','FAIL') and type(l.get('prediction_preservation')) is bool) or l4_not_applicable(p,l,r)
            if not protected or p.get('auxiliary_geometry_status',{}).get('check_status') not in ('PASS','NOT_APPLICABLE') or not evaluated:continue
        if not finite(r.get('nonstability_score')):continue
        gid=sha(encode(dict(complete=r['stage_evidence_complete'],dims=r['nonstability_dimensions'],protection=p.get('check_status'),mode=r['calculation_mode'])))
        groups.setdefault(gid,[]).append(r);eligible.append(r['candidate_id'])
    rows=[]
    for gid,rr in sorted(groups.items()):
        rr.sort(key=lambda r:(-r['nonstability_score'],r['candidate_id']))
        rows.append(dict(group_id=gid,stage_evidence_complete=rr[0]['stage_evidence_complete'],ordered_candidate_ids=[r['candidate_id'] for r in rr]))
    selected=round_robin_groups(rows,limit)
    return dict(selection_rule_id=SELECTION,groups=rows,selected_candidate_ids=selected,
                excluded_or_unavailable=sorted(r['candidate_id'] for r in records if r['candidate_id'] not in eligible),
                not_selected_for_budget=sorted(i for i in eligible if i not in selected),limit=limit)


def rank(records,cfg):
    ready=[r for r in records if r['disposition']=='FORMAL_POOL' and r.get('evidence_group')]
    result=rank_groups(ready,cfg['policies']['score'])
    for group in result['groups']:
        families={}
        for r in group['records']:families.setdefault(r.get('family','unclassified'),[]).append(r)
        chosen=[]
        for i in range(5):
            for rows in families.values():
                if i<len(rows) and len(chosen)<20:chosen.append(rows[i])
        chosen.extend(r for r in group['records'] if r not in chosen)
        group['selected']=chosen[:20];group['family_order']=list(families)
        group['family_quota_first_round']=5
        for ranked in group['records']:
            record=next(r for r in records if r['candidate_id']==ranked['candidate_id'] and r['disposition']=='FORMAL_POOL')
            record.update(comparison_score=ranked['comparison_score'],unpenalized_score=ranked['unpenalized_score'],penalty=ranked['penalty'])
            record['ranking_context'].update(group_id=group['group_id'],group_rank=ranked['group_rank'],evidence_group=record['evidence_group'],rank=None)
    return result
