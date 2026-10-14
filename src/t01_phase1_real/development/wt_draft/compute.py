"""Assemble traceable facts and the R-57 business decision; never release science."""
import copy
from .policy import PRODUCERS

OBSERVATIONS=dict(structure=('analysis',),topology=('topology',),blast=('database','search'),
    bepipred=('raw_scores','postprocessing','method_summary'),netmhc=('channels','panel_selection'),epitope_map=('epitopes','branch_status','blast_similarity'),
    glycosylation=('glycosylation','hotspot_assessment'),homology=('analysis','homolog_set'),
    domains=('analysis',),developability=('developability','steps'))


def _reason(code,source,affects,**details):
    return dict(code=code,source=source,affects=affects,**details)


def evaluate_design_applicability(body,values,receipts):
    """Apply R-57 as a business route without granting scientific release."""
    seq=body['protein_sequence'];context=body['design_context']
    topology=(values.get('topology') or {}).get('topology')
    topology_known=receipts['topology']['state']=='available' and isinstance(topology,dict)
    quality=((((values.get('structure') or {}).get('analysis') or {}).get('quality') or {}).get('quality') or {}).get('confidence')
    quality_known=receipts['structure']['state']=='available' and quality in ('high','medium','low')
    domain_analysis=(values.get('domains') or {}).get('analysis') or {}
    domains=domain_analysis.get('functional_domains')
    domains_known=receipts['domains']['state']=='available' and isinstance(domains,list)
    tm_domain_present=any(isinstance(row,dict) and row.get('type')=='TMhelix' for row in domains) if domains_known else None

    conditions={name:None for name in ('tm_count_at_least_3','tm_with_outside_under_100',
        'tm_with_outside_fraction_under_0_25','enveloped_tm_cross_confirmed')}
    tm_count=outside_length=outside_fraction=None
    if topology_known:
        tm_count=topology.get('tm_count');outside_length=topology.get('outside_length')
        if type(tm_count) is int and type(outside_length) is int and tm_count>=0 and outside_length>=0:
            outside_fraction=outside_length/len(seq)
            conditions['tm_count_at_least_3']=tm_count>=3
            conditions['tm_with_outside_under_100']=tm_count>0 and outside_length<100
            conditions['tm_with_outside_fraction_under_0_25']=tm_count>0 and outside_fraction<0.25
            if tm_count<1 or context['pathogen_type']!='virus_enveloped' or tm_domain_present is False:
                conditions['enveloped_tm_cross_confirmed']=False
            elif context['pathogen_type']=='virus_enveloped' and tm_domain_present is True:
                conditions['enveloped_tm_cross_confirmed']=True
    flags=list(conditions.values())
    membrane=True if True in flags else False if all(flag is False for flag in flags) else None
    missing=[]
    if not topology_known or conditions['tm_count_at_least_3'] is None:
        missing.append('TOPOLOGY')
    elif membrane is None and context['pathogen_type']=='virus_enveloped' and not domains_known:
        missing.append('FUNCTIONAL_DOMAINS')
    if not quality_known:missing.append('STRUCTURE_QUALITY')

    decision=[];constraints=[];skip=None;mode=None
    if membrane is True and not context['membrane_design_confirm']:
        status='NOT_SUITABLE_FOR_DESIGN';suitable=False;route='WT_PATH_REVIEW';skip='membrane_expected_poor'
        decision.append(_reason('R57_MEMBRANE_DESIGN_CONFIRMATION_REQUIRED','R-57',
            ['design_applicability','wt_route']))
        if quality=='low' and not context['low_conf_design_confirm']:
            decision.append(_reason('R57_LOW_CONFIDENCE_DESIGN_CONFIRMATION_REQUIRED','R-57',
                ['design_applicability','wt_route']))
    elif quality=='low' and not context['low_conf_design_confirm']:
        status='NOT_SUITABLE_FOR_DESIGN';suitable=False;route='WT_PATH_REVIEW';skip='skipped_low_confidence'
        decision.append(_reason('R57_LOW_CONFIDENCE_DESIGN_CONFIRMATION_REQUIRED','R-57',
            ['design_applicability','wt_route']))
    elif membrane is None or not quality_known:
        status='INPUT_INSUFFICIENT_OR_NOT_EVALUATED';suitable=None;route='HOLD_FOR_INPUTS'
        for fact in missing:
            decision.append(_reason('DESIGN_APPLICABILITY_'+fact+'_REQUIRED',fact.lower(),
                ['design_applicability']))
    else:
        status='SUITABLE_FOR_DESIGN';suitable=True;route='DESIGN_PATH_REVIEW'
        if membrane:constraints.extend(['EXTRACELLULAR_ONLY','TM_AND_INSIDE_FIXED'])
        if quality=='low':constraints.append('LOW_CONFIDENCE_RESULT_CAVEAT')
        if membrane and quality=='low':mode='EXTRACELLULAR_RESTRICTED_LOW_CONFIDENCE_REVIEW'
        elif membrane:mode='EXTRACELLULAR_RESTRICTED'
        elif quality=='low':mode='LOW_CONFIDENCE_CONFIRMED_REVIEW'
        else:mode='FULL_PROTEIN_REVIEW'

    n10=(values.get('developability') or {}).get('developability') or {}
    return dict(status=status,suitable_for_design=suitable,design_skip_reason=skip,route=route,
        business_gate_evaluated=status!='INPUT_INSUFFICIENT_OR_NOT_EVALUATED',wt_route=route=='WT_PATH_REVIEW',
        design_mode=mode,constraints=constraints,
        quality_flags=[flag for flag,active in (('membrane_expected_poor',membrane is True),
            ('skipped_low_confidence',quality=='low')) if active],
        decision_qualification='DEVELOPMENT_UNREVIEWED',
        scientific_release_status='CLOSED',n11_release=False,automatic_design_release=False,
        formal_wt_release=False,agent_c_handoff=False,decision_reasons=decision,
        basis=dict(authority=['AgentA_SKILL R-57','AgentA_SOP T-01 step 14'],
            source_states={name:receipts[name]['state'] for name in ('structure','topology','domains','developability')},
            pathogen_type=context['pathogen_type'],confirmations=dict(
                membrane_design_confirm=context['membrane_design_confirm'],
                low_conf_design_confirm=context['low_conf_design_confirm']),
            topology=dict(tm_count=tm_count,outside_length=outside_length,outside_fraction=outside_fraction),
            functional_tm_domain_present=tm_domain_present,structure_confidence=quality,
            r57_membrane_conditions=conditions,is_membrane=membrane,required_missing=missing,
            n10_complete=n10.get('n10_complete'),developability_classification=n10.get('classification')))


def assemble(body,values,receipts):
    reasons=[dict(code=code,source=None,affects=affects) for code,affects in (
        ('OI_021_FORMAL_GATE_AND_WT_STATE_UNSIGNED',['scientific_release','formal_wt_delivery']),
        ('OI_014_CANDIDATE_MAPPING_INCOMPLETE',['formal_wt_delivery']),
        ('OI_013_AGENT_C_PROTOCOL_UNRESOLVED',['agent_c_handoff']))]
    assessments={}
    for name in PRODUCERS:
        receipt=receipts[name];value=values.get(name);state=receipt['state']
        codes={'missing':'UPSTREAM_NOT_PROVIDED','pending':'UPSTREAM_NOT_TERMINAL',
            'failed':'UPSTREAM_FAILED','available':'UPSTREAM_SCIENTIFIC_SIGNOFF_MISSING'}
        reasons.append(dict(code=codes[state],source=name,affects=['scientific_release','formal_wt_delivery'],
            upstream_error=receipt.get('error_code')))
        assessments[name]=dict(state=state,execution_state=receipt.get('job_state'),
            executed=receipt.get('attempt_id') is not None,scientifically_accepted=False,
            source_artifact=receipt.get('artifact'),upstream_status=receipt.get('result_status'),
            observations=None if value is None else {k:copy.deepcopy(value.get(k)) for k in OBSERVATIONS[name]},
            upstream_warnings=None if value is None else copy.deepcopy(value.get('warnings')))
    n10=(values.get('developability') or {}).get('developability')
    if n10 is not None and n10.get('n10_complete') is not True:
        reasons.append(dict(code='N10_PARTIAL',source='developability',affects=['scientific_release','formal_wt_delivery'],
            missing_dimensions=copy.deepcopy(n10.get('missing_dimensions')),
            excluded_dimensions=copy.deepcopy(n10.get('excluded_dimensions'))))
    # Only direct, documented S-42 facts are projected. These are not a CandidateRecord.
    fields={}
    for name in ('protein_sequence','host_species','organism'):
        fields[name]=dict(value=body[name],producer='request',source_path=name,
            reason_code=None if body[name] is not None else 'INPUT_FACT_NOT_PROVIDED')
    for name,producer,reason in (
        ('candidate_id','S-42','OI_014_IDENTITY_MAPPING_PENDING'),
        ('protein_id','S-42','OI_014_IDENTITY_MAPPING_PENDING'),
        ('evidence_level','S-42','SCIENTIFIC_EVIDENCE_NOT_SIGNED'),
        ('dna_sequence','codon_optimization','NOT_EXECUTED'),
        ('design_permissions','S-27','DESIGN_NOT_EXECUTED'),
        ('validation','S-28','DESIGN_NOT_EXECUTED'),
        ('stability_validation','S-31/S-32','NOT_EXECUTED'),
        ('delta_table','S-42','NO_VARIANT_COMPARISON'),
        ('safety','S-23','NOT_EXECUTED')):
        fields[name]=dict(value=None,producer=producer,source_path=None,reason_code=reason)
    fields['optimization_status']=dict(value='not_optimized',producer='local WT path',
        source_path=None,reason_code='CODON_OPTIMIZATION_NOT_EXECUTED')
    for field,producer,path in (('epitopes','epitope_map','epitopes'),
        ('glycosylation','glycosylation','glycosylation'),('developability','developability','developability')):
        value=values.get(producer)
        fields[field]=dict(value=copy.deepcopy(value.get(path)) if value else None,
            producer=PRODUCERS[producer],source_path=path,source_artifact=receipts[producer].get('artifact'),
            reason_code='DEVELOPMENT_UNREVIEWED' if value else 'UPSTREAM_UNAVAILABLE')
    # Only an evaluated N07 shielding assessment may retain its derived risk.
    glyco=values.get('glycosylation') or {}
    shielding=(glyco.get('hotspot_assessment') or {}).get('status')
    if fields['glycosylation']['value'] is not None and shielding!='EVALUATED':
        fields['glycosylation']['value']['shielding_risk']=None
        fields['glycosylation']['reason_code']='HOTSPOT_SHIELDING_NOT_PERFORMED'
        reasons.append(dict(code='HOTSPOT_SHIELDING_NOT_PERFORMED',source='glycosylation',affects=['formal_wt_delivery']))
    gate=evaluate_design_applicability(body,values,receipts)
    gate['reasons']=gate.pop('decision_reasons')+reasons
    return dict(document_kind='LOCAL_WT_ASSESSMENT_DRAFT',schema_identity='t01/w4/local-wt-draft/0.2.0',
        candidate_record_complete=False,agent_c_payload=None,formal_wt_delivery=False,
        subject=dict(kind='WT',protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
            host_species=body['host_species'],organism=body['organism']),fields=fields,assessments=assessments,
        checks=dict(executed=[n for n,r in assessments.items() if r['executed']],
            not_executed=[n for n,r in assessments.items() if not r['executed']],
            missing=[n for n,r in assessments.items() if r['state']=='missing'],
            failed=[n for n,r in assessments.items() if r['state']=='failed'],
            pending=[n for n,r in assessments.items() if r['state']=='pending'],
            unsigned=[n for n,r in assessments.items() if r['state']=='available'],
            scientific_checks_passed=None,experimental_safety_status='NOT_ASSESSED'),gate=gate)
