"""Bounded M1 continuation scheduled as ordinary transactional workflow children.

Legacy M1 retains three representatives. BACKEND_EVIDENCE_V1 uses full S28
validation, full validated N13 reassessment and the independent step19b N14 pool.
Five-run BuildModel and explicitly permitted WT scan do not grant scientific release.
"""
from ...common import ensure

KINDS = {'rescore': ('esm_if1','N12'), 'design_audit': ('design_audit','N12'),
    'stability': ('foldx','N14'), 'protection': ('epitope_protection','N13'),
    'wt_foldx': ('foldx','N17'), 'wt_thermompnn': ('thermompnn','N17')}
REASSESS = ('bepipred','netmhc','epitope_map','glycosylation','developability')

def reassessment(label):
    return REASSESS if label=='wt' else ('bepipred','netmhc','blast','epitope_map','glycosylation','developability')

LABELS = ('wt',) + tuple('rep'+str(i) for i in range(1,65))
for label in LABELS:
    for kind in (('prediction','structure') if label != 'wt' else ()) + reassessment(label):
        KINDS[label+'_'+kind] = ({'prediction':'esmfold2','structure':'ingest_structure'}.get(kind,kind),
                                'N12' if kind in ('prediction','structure') else 'N13')
TAIL = ('rescore','design_audit','preselection') + tuple(
    label+'_'+kind for label in ('wt','rep1','rep2','rep3')
    for kind in (('prediction','structure') if label!='wt' else ()) + reassessment(label)) + (
    'protection','stability','variant_report','codon','wt_foldx','wt_thermompnn','wt_reference','local_delivery')
FULL_TAIL = TAIL[:3] + tuple(label+'_'+kind for label in LABELS
    for kind in (('prediction','structure') if label!='wt' else ()) + reassessment(label)) + TAIL[-8:]


def selected(rt, rows):
    row=rows.get('preselection') or {}
    if row.get('state')!='succeeded':return []
    fact=row['fact']
    ensure(fact['kind']=='N12_REPRESENTATIVE_PRESELECTION' and
        [r['sample_number'] for r in fact['selected']]==fact['sample_numbers'],
        'OUTPUT_INVALID','Internal preselection identity differs')
    return fact['selected']


def preselection(rt,b,rows):
    from .engineering import enabled
    if enabled(b):
        from .design_rounds import active
        rows=active(rows)
    from .service import source
    from ..variant_report.m1 import verified_preselection
    audit=source(rt,rows.get('design_audit'))
    ensure(audit is not None and rows['design_audit']['state']=='succeeded',
        'OUTPUT_INVALID','N12 design audit required before representative preselection')
    with rt._db() as db:
        context=rows.get('validation',{}).get('validation_source')
        if enabled(b) and 'validation' in rows:
            ensure(context is not None,'OUTPUT_INVALID','Complete N12 validation required before selection')
        return verified_preselection(rt,db,b['protein_sequence'],b['user_sequence_id'],audit,context,
            'ALL_VALIDATED' if enabled(b) and context is not None else None)


def sequence(rt, body, rows, name):
    if name.startswith('rep') and name in KINDS:
        index=int(name.split('_',1)[0][3:])-1;records=selected(rt,rows)
        ensure(index<len(records),'OUTPUT_INVALID','Representative slot has no selected candidate')
        return records[index]['sequence']
    return body['protein_sequence']


def prediction_validation(rows,name):
    if not name.startswith('rep') or name not in KINDS:return None
    records=(rows.get('preselection',{}).get('fact') or {}).get('selected',[])
    index=int(name.split('_',1)[0][3:])-1
    return records[index].get('validation') if index<len(records) else None


def prediction_engine(rows,name):
    validation=prediction_validation(rows,name)
    return (validation or {}).get('selected') or 'esmfold2'


def scan_scope(rt, body, rows):
    from .stability_scope import scope
    return scope(rt,body,rows)


def request_for(rt,b,rows,name):
    from .service import source,typed
    def src(n):return source(rt,rows.get(n))
    base=dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],timeout_seconds=60)
    designed=rows.get('design',{}).get('state')=='succeeded'
    if designed and rows['design'].get('generation_status')=='not_generated_no_designable_positions':
        if name in ('rescore','design_audit','variant_report'):
            return None,'NO_DESIGNABLE_POSITIONS'
        designed=False
    records=selected(rt,rows)
    if name=='preselection':return None,'INTERNAL_N12_FACT'
    if name in KINDS and name not in ('wt_foldx','wt_thermompnn') and not designed:
        return None,'DESIGN_NOT_EXECUTED'
    if name=='rescore':
        return dict(base,structure_artifact=src('structure')['artifact'],n11_artifact=src('design')['artifact'],
            sample_numbers=list(range(1,b['m1_test']['n_designs']+1)),baseline_artifact=None,timeout_seconds=900),None
    if name=='design_audit':
        from ..design_backend.policy import PRODUCERS
        constraints=b['m1_test']['constraints'];regions=[]
        for permission,positions in (('FIXED',constraints['fixed_positions']),('OPEN',constraints['open_positions'])):
            regions += [dict(start=p,end=p,permission=permission,allowed_residues=None,source_id=constraints['source_id']) for p in positions]
        regions += [dict(start=r['position'],end=r['position'],permission='RESTRICTED',allowed_residues=r['allowed_residues'],
                         source_id=constraints['source_id']) for r in constraints['restricted_positions']]
        from .engineering import enabled
        if enabled(b):regions=[]  # Derived facts are not user overrides.
        return dict(base,upstream={n:src({'n11':'design','esm_if1':'rescore'}.get(n,n)) for n in PRODUCERS},
            user_regions=regions,objective='general',epitope_policy='PRESERVE',epitope_mode='both',
            membrane_design_confirm=b.get('design_context',{}).get('membrane_design_confirm',False),
            sample_numbers=list(range(1,b['m1_test']['n_designs']+1))),None
    if name=='variant_report':
        if not designed:return None,'DESIGN_NOT_EXECUTED'
        from .engineering import enabled
        partial=enabled(b)
        if not partial and (rows.get('protection',{}).get('state')!='succeeded' or rows.get('stability',{}).get('state')!='succeeded'):
            return None,'N13_OR_N14_NOT_COMPLETE'
        if rows.get('design_audit',{}).get('state')!='succeeded':return None,'N12_AUDIT_NOT_COMPLETE'
        request=dict(base,upstream=dict(design_audit=src('design_audit'),foldx=src('stability')),
            variant_source='N11_DESIGN_AUDIT',foldx_bindings=[])
        if rows.get('validation',{}).get('validation_source'):
            request['validation_source']=rows['validation']['validation_source']
        if records and rows.get('stability',{}).get('state')=='succeeded':
            request['foldx_bindings']=[dict(sample_number=r['sample_number'],variant_id=r['id']) for r in records]
        if partial and rows.get('stability',{}).get('state')=='succeeded':
            from .stability_pool import pool
            fact,reason=pool(rt,b,rows)
            ensure(reason is None,'OUTPUT_INVALID','Completed N14 lacks a valid candidate pool')
            request['foldx_bindings']=[dict(sample_number=r['sample_number'],variant_id=r['id']) for r in fact['selected']]
        if records and rows.get('protection',{}).get('state')=='succeeded':
            request['n13_source']=src('protection')
        # The legacy enriched report requires complete paired calculations. If
        # unavailable, still publish verified N11/N12/N13/FoldX facts via the
        # base report, preserving failed sources and unknown dimensions.
        required=['wt_'+k for k in REASSESS]
        required += ['rep'+str(i)+'_'+k for i in range(1,len(records)+1)
                     for k in ('prediction','structure',*REASSESS)]
        complete=all(rows.get(n,{}).get('state')=='succeeded' for n in required)
        full=(rows.get('preselection',{}).get('fact') or {}).get('selection_scope')=='ALL_VALIDATED'
        if records and (not partial or complete) and 'n13_source' in request and not full:
            request['m1_test']=dict(wt={k:src('wt_'+k) for k in ('epitope_map','glycosylation','developability')},
                representatives=[dict(sample_number=r['sample_number'],**{k:src('rep'+str(i)+'_'+k)
                    for k in ('prediction','structure','epitope_map','glycosylation','developability')}) for i,r in enumerate(records,1)])
        return request,None
    if name in KINDS and name.startswith(('wt_','rep')) and name not in ('wt_foldx','wt_thermompnn'):
        label,kind=name.split('_',1)
        if label!='wt' and int(label[3:])>len(records):return None,'NO_REPRESENTATIVE_IN_SLOT'
        if not records:return None,'NO_SCORED_NON_WT_REPRESENTATIVE'
        seq=sequence(rt,b,rows,name);base.update(protein_sequence=seq)
        structure=src('structure' if label=='wt' else label+'_structure')
        if kind=='prediction':
            validation=prediction_validation(rows,name)
            if validation is not None and validation['selected'] is None:
                return None,'VARIANT_PREDICTION_UNAVAILABLE_S28_WARNING'
            return dict(base,host_species=b['host_species'],seed=1,
                        timeout_seconds=7200 if prediction_engine(rows,name)=='af3' else 900),None
        if kind=='blast':
            # Requery the configured local snapshot for this exact variant; the
            # WT's HSP coordinates must never masquerade as variant evidence.
            if b['analysis']['blast'] is None:return None,'DATABASE_NOT_PROVIDED'
            return dict(base,**b['analysis']['blast']),None
        if kind=='structure':
            if rows.get(label+'_prediction',{}).get('state')!='succeeded':
                return None,'VARIANT_PREDICTION_UNAVAILABLE_S28_WARNING'
            from .service import prediction_source
            engine=prediction_engine(rows,name)
            verified=prediction_source(engine).verified
            prediction=rt.get(rows[label+'_prediction']['job_id'])
            with rt._db() as db:ref,_=verified(rt,db,prediction['job_id'],seq,b['host_species'],prediction['run_id'])
            return dict(protein_sequence=seq,host_species=b['host_species'],structure_artifact=ref,structure_name=engine+'.cif',
                declared_format='MMCIF',selection=dict(model_index=0,chain_selector='A'),context_chain_ids=['A'],
                source_declaration=dict(kind='predicted',note=engine+' job '+prediction['job_id']),timeout_seconds=120),None
        if kind in ('bepipred','netmhc','developability'):
            if kind=='netmhc' and b['analysis'][kind] is None:
                return None,'ALLELE_PANEL_NOT_PROVIDED'
            ensure(b['analysis'][kind] is not None,'INVALID_REQUEST','M1 representative analysis requires '+kind)
            req=dict(base,**b['analysis'][kind])
            if kind=='netmhc':req['host_species']=b['host_species']
            if kind=='developability':req['structure_input']=typed(rt,rows,'structure' if label=='wt' else label+'_structure')
            return req,None
        if kind=='epitope_map':
            blast=typed(rt,rows,'blast' if label=='wt' else label+'_blast')
            if blast['state']=='not_provided':
                blast=dict(state='not_executed',artifact=None,reason_code='PAIRED_LOCAL_BLAST_NOT_EXECUTED')
            return dict(base,bepipred_input=typed(rt,rows,label+'_bepipred'),
                netmhc_input=typed(rt,rows,label+'_netmhc'),blast_input=blast,
                topology_input=typed(rt,rows,'topology') if label=='wt' else
                    dict(state='not_provided',artifact=None,reason_code=None)),None
        if kind=='glycosylation':return dict(base,hotspot_input=rt.n06_hotspot_input(rows[label+'_epitope_map']['job_id'],seq)),None
    if name=='stability':
        from .engineering import enabled
        if enabled(b):
            from .stability_pool import pool
            fact,reason=pool(rt,b,rows)
            if reason:return None,reason
            if rows.get('protection',{}).get('state') not in ('succeeded','skipped'):
                return None,'N13_NOT_COMPLETE'
            return dict(base,structure_artifact=src('structure')['artifact'],mode='buildmodel',scan_positions=[],
                fixed_positions=b['m1_test']['constraints']['fixed_positions'],
                variants=[dict(variant_id=r['id'],mutations=r['mutations']) for r in fact['selected']],timeout_seconds=14400,
                scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE',source_id='N14 complete pool sha256='+fact['pool_sha256'])),None
        if rows.get('protection',{}).get('state')!='succeeded':return None,'N13_NOT_COMPLETE'
        if not records:return None,'NO_SCORED_NON_WT_REPRESENTATIVE'
        return dict(base,structure_artifact=src('structure')['artifact'],mode='buildmodel',scan_positions=[],
            fixed_positions=b['m1_test']['constraints']['fixed_positions'],
            variants=[dict(variant_id=r['id'],mutations=r['mutations']) for r in records],timeout_seconds=14400,
            scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE',source_id='M1 current workflow selected exact N11 diffs')),None
    if name=='protection':
        if not records:return None,'NO_SCORED_NON_WT_REPRESENTATIVE'
        return dict(base,upstream=dict(design_audit=src('design_audit')),
            preselection=rows['preselection']['fact'],pairs=[dict(variant_id=r['id'],
            wt=dict(structure=src('structure'),epitope_map=src('wt_epitope_map'),domains=src('domains')),
            variant=dict(structure=src('rep'+str(i)+'_structure'),epitope_map=src('rep'+str(i)+'_epitope_map'),domains=None))
            for i,r in enumerate(records,1)]),None
    if name=='codon':
        if not designed:return None,'NO_QUALIFIED_CANDIDATE'
        if rows.get('variant_report',{}).get('state')!='succeeded':return None,'N15_NOT_COMPLETE'
        report=rt.result(rows['variant_report']['job_id'])['report']
        if not report.get('ranked_candidates'):return None,'NO_QUALIFIED_CANDIDATE'
        return None,'EXPRESSION_HOST_NOT_PROVIDED' if b['expression_host'] is None else 'N16_BUSINESS_LINEAGE_UNAPPROVED'
    if name in ('wt_foldx','wt_thermompnn'):
        if designed and rows.get('variant_report',{}).get('state')!='succeeded':return None,'N15_NOT_COMPLETE'
        scope,reason=scan_scope(rt,b,rows)
        if reason:return None,reason
        if name=='wt_thermompnn' and not scope['monomer']:return None,'R39_MULTICHAIN_THERMOMPNN_SKIPPED'
        req=dict(base,structure_artifact=src('structure')['artifact'],scan_positions=scope['positions'],timeout_seconds=900)
        source_id='N17 '+scope['selection_rule']+'; complete mapped OPEN positions; FIXED+RESTRICTED excluded; scope_sha256='+scope['scope_sha256']
        if name=='wt_foldx':
            from .stability_scope import timeout
            req.update(mode='positionscan',fixed_positions=scope['excluded'],variants=[],timeout_seconds=timeout(scope['positions']),
                scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE',source_id=source_id))
        else:req.update(excluded_positions=scope['excluded'],scope_source=dict(purpose='ENGINEERING_EXPLICIT_SCAN_SCOPE',source_id=source_id))
        return req,None
    if name=='wt_reference':
        if rows.get('variant_report',{}).get('state')!='succeeded' and designed:return None,'N15_NOT_COMPLETE'
        return dict(base,upstream={k:src(v) for k,v in dict(structure='structure',topology='topology',
            design_audit='design_audit',foldx='wt_foldx',thermompnn='wt_thermompnn').items()}),None
    if name=='local_delivery':
        from .engineering import enabled
        from .candidate_dna import ORDER as DNA_ORDER
        from .service import recoverable_child_failure
        ensure(all(rows.get(n,{}).get('state') in ('succeeded','skipped') or
            (rows.get(n,{}).get('job_id') and recoverable_child_failure(b,n,rt.get(rows[n]['job_id'])))
            for n in (DNA_ORDER if enabled(b) and any(n in rows for n in DNA_ORDER[1:]) else ('codon',))) and
            rows.get('wt_reference',{}).get('state') in ('succeeded','skipped'),
            'OUTPUT_INVALID','N18 must wait for independent N16 and N17 branch terminals')
    return None
