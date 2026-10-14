"""S-28 per-candidate engineering validation, persisted same-run native jobs.

SOP v10.5 S-28/T-01 step17; structure ToolSpec 2b/2c. Unresolved R-04
domains and asset support limits stay unknown; they are never failed predictions.
"""
import math
import re
from ...common import TERMINAL, RuntimeFault, decode, ensure, sha

NAMES=('validation','retry1_validation','retry2_validation')
CHILD=re.compile(r'v([012])_s([1-9][0-9]?)_(af3|esmfold2)$')
ROUNDS=(24,48,64)
CHILDREN={f'v{r}_s{s}_{engine}':engine for r,n in enumerate(ROUNDS)
          for s in range(1,n+1) for engine in ('af3','esmfold2')}


def prefix(name):return '' if name=='validation' else name[:7]
def round_index(name):return 0 if name=='validation' else int(name[5])


def route(length,count,partial=False):
    ensure(type(length) is int and length>0 and type(count) is int and 0<=count<=length,
           'OUTPUT_INVALID','Invalid mutation fraction')
    if partial:return dict(engines=['esmfold2'],reason='STRUCTURE_SPEC_PARTIAL_C11')
    # Only the intersection of SOP / SKILL / ToolSpec domains is automatic.
    if count<=5 and count*100<=2*length:return dict(engines=['af3'],reason='R04_SMALL_HIGH_IDENTITY')
    if count>5 and count*100>10*length:return dict(engines=['esmfold2'],reason='R04_LARGE_REDESIGN')
    if count>5 and 5*length<=count*100<=10*length:return dict(engines=['af3','esmfold2'],reason='R04_DUAL_5_TO_10_PERCENT')
    return dict(engines=[],reason='R04_ROUTE_UNRESOLVED')


def decision(score,observations,routing):
    """Tri-state validation: failed prediction differs from low successful pLDDT."""
    ensure(score.get('passed') is None or type(score['passed']) is bool,'OUTPUT_INVALID','Invalid R35 decision')
    if score['passed'] is False:return dict(passed=False,reason='R35_DETERIORATION_EXCEEDED',selected=None,degraded=False)
    if score['passed'] is None:return dict(passed=None,reason='R35_UNAVAILABLE',selected=None,degraded=True)
    if not routing['engines']:return dict(passed=None,reason=routing['reason'],selected=None,degraded=True)
    ensure(set(observations)==set(routing['engines']),'OUTPUT_INVALID','Incomplete engine observations')
    valid=[]
    for engine,value in observations.items():
        if value['state']=='succeeded':
            q=value['plddt']
            ensure(type(q) in (int,float) and math.isfinite(q) and 0<=q<=1,'OUTPUT_INVALID','Invalid normalized pLDDT')
            valid.append((q,engine))
    if valid:
        q,engine=max(valid,key=lambda pair:(pair[0],-routing['engines'].index(pair[1])))
        incomplete=any(v['state']!='succeeded' for v in observations.values())
        if q>=.5:return dict(passed=True,reason='S28_PASSED',selected=engine,degraded=incomplete)
        if incomplete:return dict(passed=None,reason='DUAL_ENGINE_INCOMPLETE_LOW_AVAILABLE_PLDDT',selected=engine,degraded=True)
        return dict(passed=False,reason='PLDDT_BELOW_0_50',selected=engine,degraded=False)
    if all(v['state']=='prediction_failed' for v in observations.values()):
        return dict(passed=True,reason='S28_PREDICTION_FAILED_RETAIN_R35',selected=None,degraded=True)
    return dict(passed=None,reason='STRUCTURE_VALIDATION_NOT_EXECUTED',selected=None,degraded=True)


def inputs(rt,body,rows,name,run_id):
    from .service import verified,source
    p=prefix(name);values={};refs={}
    for kind in ('design','rescore','design_audit'):
        row=rows.get(p+kind,{})
        if row.get('state')!='succeeded':return None
        verified(rt,body,p+kind,row['job_id'],run_id,rows)
        values[kind]=rt.result(row['job_id']);refs[kind]=source(rt,row)
    # Rebuild the audit from registered native generation/scoring/backbone bytes.
    # A self-consistent cached decision is insufficient to authorize regeneration.
    from ..variant_report.source import sources as audit_sources
    with rt._db() as db:
        _,checked,_=audit_sources(rt,db,dict(protein_sequence=body['protein_sequence'],
            user_sequence_id=body['user_sequence_id'],upstream=dict(design_audit=refs['design_audit'],foldx=None),
            variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=60))
    ensure(checked['design_audit']==values['design_audit'],'OUTPUT_INVALID','Validation audit replay differs')
    audit_request=decode(rt._request_bytes(rt.get(rows[p+'design_audit']['job_id'])))
    ensure(audit_request['upstream']['n11']==refs['design'] and audit_request['upstream']['esm_if1']==refs['rescore'],
           'OUTPUT_INVALID','Validation audit sources differ from this round')
    generated=values['design']['generation']['records']
    scores=values['rescore']['engineering_rules']['records'];audit=values['design_audit']['audit']
    numbers=[g['sample_number'] for g in generated]
    ensure(numbers==list(range(1,len(numbers)+1)) and len(numbers)<=ROUNDS[round_index(name)],'OUTPUT_INVALID','N11 sample inventory differs')
    ensure([s['sample_number'] for s in scores]==numbers,'OUTPUT_INVALID','N12 must score every generated sample')
    ensure([s['sample_number'] for s in audit['burden_records']]==numbers,'OUTPUT_INVALID','Burden must cover every sample')
    requested=decode(rt._request_bytes(rt.get(rows[p+'design']['job_id'])))['n_designs']
    ensure(not numbers or len(numbers)==requested,'OUTPUT_INVALID','Incomplete generated round')
    verified(rt,body,'structure',rows['structure']['job_id'],run_id,rows)
    structure=rt.result(rows['structure']['job_id'])['analysis'];refs['structure']=source(rt,rows['structure'])
    partial=any(e['reason']!='mapped' for e in structure['mapping']['entries'])
    low=structure.get('low_confidence_regions')
    if low is None:low=(structure.get('quality',{}).get('quality') or {}).get('low_confidence_regions')
    for g in generated:
        ensure(len(g['sequence'])==len(body['protein_sequence']),'OUTPUT_INVALID','Variant length differs')
        actual=[dict(position=i,wt_residue=a,mut_residue=b,source='ProteinMPNN')
                for i,(a,b) in enumerate(zip(body['protein_sequence'],g['sequence']),1) if a!=b]
        ensure(actual==g['mutations'],'OUTPUT_INVALID','N11 mutation identity differs')
    return dict(generation=generated,scores=scores,audit=audit,refs=refs,partial=partial,low=low,
                baseline=values['rescore']['engineering_rules']['baseline_used'],
                r35_rules=values['rescore']['engineering_rules'])


def child_sequence(rt,rows,name):
    m=CHILD.fullmatch(name);ensure(m is not None and name in CHILDREN,'INVALID_REQUEST','Unknown validation child')
    p='' if m[1]=='0' else f'retry{m[1]}_'
    records=rt.result(rows[p+'design']['job_id'])['generation']['records']
    found=[g for g in records if g['sample_number']==int(m[2])]
    ensure(len(found)==1,'OUTPUT_INVALID','Validation child sample absent')
    return found[0]['sequence']


def observation(rt,body,rows,key,run_id):
    from .service import verified,source,prediction_source
    row=rows.get(key)
    if not row:return None
    if not row.get('job_id'):return dict(state='not_executed',reason=row['reason_code'],source=None,plddt=None,structure=None)
    job=verified(rt,body,key,row['job_id'],run_id,rows)
    if job['state'] not in TERMINAL:return None
    if job['state']!='succeeded':
        ensure(job['state'] in ('failed','timed_out') and job['error_code'] in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'),
               job['error_code'] or 'OUTPUT_INVALID','Invalid validation prediction failure')
        return dict(state='prediction_failed',reason=job['error_code'],source=source(rt,row),plddt=None,structure=None)
    engine=CHILDREN[key];seq=child_sequence(rt,rows,key)
    with rt._db() as db:
        result=prediction_source(engine).verified(rt,db,job['job_id'],seq,body['host_species'],run_id,include_quality=True)
    observed=dict(state='succeeded',reason=None,source=source(rt,row),plddt=result['quality']['structure']['mean_plddt'],
                  structure=result['structure_artifact'],quality_artifact=result['quality_artifact'])
    if engine=='af3':
        request=decode(rt._request_bytes(job))
        if 'msa_source' in request:observed['msa_source']=request['msa_source']
    return observed


def assemble(rt,body,rows,name,run_id):
    data=inputs(rt,body,rows,name,run_id)
    ensure(data is not None,'OUTPUT_INVALID','Validation prerequisites incomplete')
    results=[];r=round_index(name)
    for g,s,b in zip(data['generation'],data['scores'],data['audit']['burden_records']):
        routing=route(len(g['sequence']),len(g['mutations']),data['partial']);obs={}
        if s['passed'] is True:
            for engine in routing['engines']:
                value=observation(rt,body,rows,f'v{r}_s{g["sample_number"]}_{engine}',run_id)
                ensure(value is not None,'OUTPUT_INVALID','Prediction still incomplete');obs[engine]=value
        verdict=decision(s,obs,routing)
        positions=[m['position'] for m in g['mutations']]
        low_positions=None if data['low'] is None else [p for p in positions if any(x['start']<=p<=x['end'] for x in data['low'])]
        warnings=[]
        if low_positions:warnings.append('MUTATION_IN_WT_LOW_CONFIDENCE_REGION')
        if low_positions is None:warnings.append('WT_LOW_CONFIDENCE_REGIONS_UNAVAILABLE')
        if verdict['degraded']:warnings.append(verdict['reason'])
        if obs.get('af3',{}).get('state')=='succeeded' and not obs['af3'].get('msa_source'):
            warnings.append('AF3_LOCAL_MSA_NOT_WT_REUSE')
        results.append(dict(sample_number=g['sample_number'],sequence_sha256=sha(g['sequence'].encode()),
            **verdict,route=routing,engines=obs,esm_if1=s,baseline_used=data['baseline'],mutation_burden=b,
            burden_exceeded=bool(b and b['engineering_thresholds']['any_known_exceeded']),
            low_confidence_mutations=low_positions,validation_confidence='degraded' if warnings else 'computed_unreviewed',
            warnings=warnings,plddt=None if verdict['selected'] is None else obs[verdict['selected']]['plddt'],
            structure=None if verdict['selected'] is None else obs[verdict['selected']]['structure']))
    pool=[r['sample_number'] for r in results if r['passed'] is True]
    rejected=[r['sample_number'] for r in results if r['passed'] is False]
    unknown=[r['sample_number'] for r in results if r['passed'] is None]
    reused=any(r['engines'].get('af3',{}).get('msa_source') for r in results)
    return dict(kind='S28_ALL_CANDIDATE_VALIDATION',scope='ENGINEERING_UNREVIEWED',run_id=run_id,
        source_jobs=data['refs'],records=results,review_pool=pool,rejected=rejected,unavailable=unknown,
        status='NO_CANDIDATES' if not results else 'VALIDATION_UNAVAILABLE' if unknown else 'REVIEW_POOL' if pool else 'ALL_REJECTED',
        scientific_release=False,usable_for_pipeline=False,
        r35_rules=data.get('r35_rules'),
        method_summary=dict(authority_version='v10.5_20260902',sections=['SOP S-28','T-01 step17','Structure ToolSpec 2b/2c'],
            decisions='Backend replay of registered native sources',plddt_scale='0..1',
            af3_msa='Same-run WT MSA; query substituted, homolog rows preserved' if reused else
                    'Current local AF3 pipeline; WT MSA reuse is not implemented'),
        limitations=['R04 ambiguous domains remain unverified','Burden is attached for later step20 filtering; it is not an S28 rejection',
                     'AF3 accepts 9..999 aa; native capacity beyond recorded runs remains unverified',
                     'WT MSA reuse is engineering validated; native capacity remains unverified' if reused else
                     'AF3 prepares local MSA per variant; ToolSpec WT MSA reuse remains an engineering gap'])


def verified_fact(rt,jid,name):
    from . import policy
    ensure(name in NAMES,'INVALID_REQUEST','Unknown validation round')
    job=rt.get(jid);ensure(job['tool_id']==policy.TOOL,'FORBIDDEN','Validation workflow producer differs')
    body=policy.request(rt._request_bytes(job));rows=rt.execution(jid)['nodes'];row=rows[name]
    ensure(row['state']=='succeeded' and row.get('origin')=='INTERNAL_FACT','OUTPUT_INVALID','Validation fact incomplete')
    fresh=assemble(rt,body,rows,name,job['run_id'])
    ensure(row['fact']==fresh,'OUTPUT_INVALID','Validation fact differs from verified native sources')
    return fresh


def tick(rt,jid,body,name,verified_facts=None):
    from .service import _record,_create_child,worker
    job=rt.get(jid);rows=rt.execution(jid)['nodes'];prior=rows.get(name,{})
    if prior.get('state')=='succeeded':
        fact=verified_fact(rt,jid,name)
        if verified_facts is not None:verified_facts[(jid,name)]=fact
        return True
    if prior.get('state')=='skipped':return True
    data=inputs(rt,body,rows,name,job['run_id'])
    if data is None:
        _record(rt,jid,name,dict(job_id=None,state='skipped',origin=None,reason_code='VALIDATION_PREREQUISITES_UNAVAILABLE'));return True
    r=round_index(name)
    _record(rt,jid,name,dict(job_id=None,state='running',origin='INTERNAL_CONTROLLER',reason_code=None))
    for g,s in zip(data['generation'],data['scores']):
        if s['passed'] is not True:continue
        routing=route(len(g['sequence']),len(g['mutations']),data['partial'])
        for engine in routing['engines']:
            if rt.get(jid)['stop_reason']:return False
            key=f'v{r}_s{g["sample_number"]}_{engine}';rows=rt.execution(jid)['nodes']
            if observation(rt,body,rows,key,job['run_id']) is not None:continue
            row=rows.get(key,{})
            if not row.get('job_id'):
                req=dict(protein_sequence=g['sequence'],user_sequence_id=body['user_sequence_id'],host_species=body['host_species'],
                         seed=1,timeout_seconds=7200 if engine=='af3' else 900)
                if len(g['sequence'])>worker(key).MAX_AA:
                    _record(rt,jid,key,dict(job_id=None,state='skipped',origin=None,reason_code='ENGINE_VERIFIED_LENGTH_LIMIT'));continue
                if engine=='af3':
                    from .msa_reuse import ready
                    msa,reason=ready(rt,jid,body)
                    if reason=='WAITING':return False
                    if reason:
                        _record(rt,jid,key,dict(job_id=None,state='skipped',origin=None,reason_code=reason));continue
                    req['msa_source']=msa
                try:child=_create_child(rt,jid,key,req)
                except RuntimeFault as exc:
                    if exc.code!='ASSET_MISSING':raise
                    _record(rt,jid,key,dict(job_id=None,state='skipped',origin=None,
                                           reason_code='ENGINE_ASSET_UNAVAILABLE',detail=str(exc)))
                    continue
                if child is None:return False
            else:child=row['job_id']
            if rt.get(child)['state']=='queued':rt.dispatch(child)
            else:rt.recover(child)
            state=rt.get(child)
            _record(rt,jid,key,dict(rt.execution(jid)['nodes'][key],state=state['state'],reason_code=state['error_code']))
            if state['state'] not in TERMINAL:return False
            observation(rt,body,rt.execution(jid)['nodes'],key,job['run_id'])
    fact=assemble(rt,body,rt.execution(jid)['nodes'],name,job['run_id'])
    _record(rt,jid,name,dict(job_id=None,state='succeeded',origin='INTERNAL_FACT',reason_code=None,fact=fact,
                            validation_source=dict(workflow_job_id=jid,node=name)))
    if verified_facts is not None:verified_facts[(jid,name)]=fact
    return True
