"""Assemble traceable facts and missing checks; never evaluate a scientific gate."""
import copy
from .policy import PRODUCERS

OBSERVATIONS=dict(structure=('analysis',),topology=('topology',),blast=('database','search'),
    bepipred=('raw_scores',),netmhc=('channels',),epitope_map=('epitopes','branch_status','blast_similarity'),
    glycosylation=('glycosylation','hotspot_assessment'),homology=('analysis','homolog_set'),
    domains=('analysis',),developability=('developability','steps'))


def assemble(body,values,receipts):
    reasons=[dict(code=code,source=None,affects=affects) for code,affects in (
        ('OI_021_GATE_RULES_UNRESOLVED',['N11','formal_wt_delivery']),
        ('OI_014_CANDIDATE_MAPPING_INCOMPLETE',['formal_wt_delivery']),
        ('OI_013_AGENT_C_PROTOCOL_UNRESOLVED',['agent_c_handoff']))]
    assessments={}
    for name in PRODUCERS:
        receipt=receipts[name];value=values.get(name);state=receipt['state']
        codes={'missing':'UPSTREAM_NOT_PROVIDED','pending':'UPSTREAM_NOT_TERMINAL',
            'failed':'UPSTREAM_FAILED','available':'UPSTREAM_SCIENTIFIC_SIGNOFF_MISSING'}
        reasons.append(dict(code=codes[state],source=name,affects=['scientific_gate','formal_wt_delivery'],
            upstream_error=receipt.get('error_code')))
        assessments[name]=dict(state=state,execution_state=receipt.get('job_state'),
            executed=receipt.get('attempt_id') is not None,scientifically_accepted=False,
            source_artifact=receipt.get('artifact'),upstream_status=receipt.get('result_status'),
            observations=None if value is None else {k:copy.deepcopy(value.get(k)) for k in OBSERVATIONS[name]},
            upstream_warnings=None if value is None else copy.deepcopy(value.get('warnings')))
    n10=(values.get('developability') or {}).get('developability')
    if n10 is not None and n10.get('n10_complete') is not True:
        reasons.append(dict(code='N10_PARTIAL',source='developability',affects=['scientific_gate','formal_wt_delivery'],
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
    # N07's raw false is accompanied by NOT_PERFORMED; it cannot assert a completed check.
    glyco=values.get('glycosylation') or {}
    shielding=(glyco.get('hotspot_assessment') or {}).get('status')
    if fields['glycosylation']['value'] is not None and shielding!='EVALUATED':
        fields['glycosylation']['value']['shielding_risk']=None
        fields['glycosylation']['reason_code']='HOTSPOT_SHIELDING_NOT_PERFORMED'
        reasons.append(dict(code='HOTSPOT_SHIELDING_NOT_PERFORMED',source='glycosylation',affects=['formal_wt_delivery']))
    return dict(document_kind='LOCAL_WT_ASSESSMENT_DRAFT',schema_identity='t01/w4/local-wt-draft/0.1.0',
        candidate_record_complete=False,agent_c_payload=None,formal_wt_delivery=False,
        subject=dict(kind='WT',protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
            host_species=body['host_species'],organism=body['organism']),fields=fields,assessments=assessments,
        checks=dict(executed=[n for n,r in assessments.items() if r['executed']],
            not_executed=[n for n,r in assessments.items() if not r['executed']],
            missing=[n for n,r in assessments.items() if r['state']=='missing'],
            failed=[n for n,r in assessments.items() if r['state']=='failed'],
            pending=[n for n,r in assessments.items() if r['state']=='pending'],
            unsigned=[n for n,r in assessments.items() if r['state']=='available'],
            scientific_checks_passed=None,experimental_safety_status='NOT_ASSESSED'),
        gate=dict(status='NOT_EVALUATED',suitable_for_design=None,design_skip_reason=None,
            route='LOCAL_WT_DRAFT_REVIEW',n11_release=False,automatic_design_release=False,
            formal_wt_release=False,agent_c_handoff=False,reasons=reasons))
