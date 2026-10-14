"""Reproducible combined permissions and burden observations from verified snapshots."""
from ...common import RuntimeFault,decode,encode,ensure,sha
from . import policy,permissions,burden
from .geometry import geometry


def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json']);scales=decode(files['input/scales.json'])
    ensure(scales==decode((policy.HERE/'scales.json').read_bytes()),'OUTPUT_INVALID','Executed numeric scales changed')
    values={name:decode(files['input/'+name+'-result.json']) for name in policy.PRODUCERS if receipts[name]['state']=='available'}
    perms=permissions.assemble(body,values,receipts,scales)
    geo=geometry(body,files) if 'structure' in values else dict(status='unavailable',reason='STRUCTURE_UNAVAILABLE',residues=None)
    request=None;converted=None;conversion_error=None
    try:
        ensure(body['objective']=='general','INVALID_REQUEST','Only general ProteinMPNN mask export is implemented; burden objective remains supported')
        ensure('structure' in values,'OUTPUT_INVALID','Structure is unavailable for native mask conversion')
        ensure(not perms['user_conflict_positions'],'OUTPUT_INVALID','Conflicting user instructions cannot be exported')
        request=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
            structure_artifact=body['upstream']['structure']['artifact'],constraints=dict(purpose='ENGINEERING_EXPLICIT_MASKS',
                source_id='design-audit-request:'+sha(encode(body)),**{k:perms[k] for k in ('fixed_positions','restricted_positions','open_positions')}),
            n_designs=24,sampling_temperature=.1,seed=17,timeout_seconds=180)
        if body.get('t4_handshake'):
            request['t4_empty_fixed_confirmation']=True
        from ..proteinmpnn.policy import request as validate
        from ..proteinmpnn.mapping import project
        validate(encode(request))
        projected=project(request,values['structure'],files['input/structure-original.bin'],
            {n:decode(files['input/'+n+'.json']) for n in ('preflight','raw_metadata','raw_addresses')})
        converted={n:decode(data) for n,data in projected.items() if n.endswith(('.json','.jsonl'))}
    except (RuntimeFault,KeyError,ValueError) as exc:
        conversion_error=dict(code=getattr(exc,'code','OUTPUT_INVALID'),reason=str(exc));request=None
    domain_value=(values.get('domains') or {}).get('analysis');domains=None
    domain_unresolved=domain_value is not None and (domain_value.get('lookup',{}).get('status')!='hit'
        or any(code in domain_value.get('review_reasons',[]) for code in ('MULTIPLE_EXACT_ENTRIES_REQUIRE_SELECTION',
            'UNREVIEWED_CONFIDENCE_DOWNGRADE_UNRESOLVED','EXPLICIT_ENTRY_SEQUENCE_OR_ORGANISM_MISMATCH')))
    if domain_value is not None and not domain_unresolved:
        # Inferred structural contact pairs are not contiguous functional-domain intervals.
        from ..expert_feedback import functional_regions
        domains=[r for r in functional_regions(domain_value['functional_domains']) if r['source']!='structure' and r['type']!='disulfide_bond']
        for row in domains:permissions.interval(row,len(body['protein_sequence']))
    epitopes=(values.get('epitope_map') or {}).get('epitopes') or {}
    hotspots=(epitopes.get('b_cell_antigenic_hotspot_map') or {}).get('hotspots')
    if hotspots is not None:
        for row in hotspots:permissions.interval(row,len(body['protein_sequence']))
    records=None;comparisons=[];scoring=(values.get('esm_if1') or {}).get('engineering_rules')
    if 'n11' in values:
        selected={r['sample_number']:r for r in values['n11']['generation']['records']}
        records=[burden.compute(body['protein_sequence'],selected[n],geo,domains,hotspots,body['objective'],scales) for n in body['sample_numbers']]
        for n in body['sample_numbers']:
            r=selected[n];violations=[dict(position=p['position'],permission=p['design_permission'],residue=r['sequence'][p['position']-1])
                for p in perms['per_residue'] if r['sequence'][p['position']-1] not in p['allowed_residues']]
            comparisons.append(dict(sample_number=n,violations=violations,matches_current_engineering_masks=not violations,
                effect='AUDIT_ONLY_PRIOR_N11_RESULT_UNCHANGED'))
        scored={r['sample_number']:r for r in (scoring or {}).get('records',[])}
        for record in records:
            record['n12_scoring_record']=scored.get(record['sample_number'])
            record['n12_scoring_reason']=None if record['n12_scoring_record'] is not None else 'SAMPLE_NOT_SCORED_IN_AVAILABLE_N12'
    reasons=perms['review_reasons']+[dict(source='burden',code='OI_008_FORMAL_BURDEN_CLOSED'),
        dict(source='design',code='SCIENTIFIC_GATE_AND_AGENT_C_CLOSED')]
    if records is None:reasons.append(dict(source='n11',code='VARIANTS_UNAVAILABLE_NO_BURDEN_COMPUTED'))
    if domain_unresolved:reasons.append(dict(source='domains',code='DOMAIN_LOOKUP_UNRESOLVED_NOT_COMPUTED_EMPTY'))
    if conversion_error:reasons.append(dict(source='mask_export',code='N11_MASK_EXPORT_BLOCKED',detail=conversion_error))
    result=dict(kind='S27_S28_ENGINEERING_AUDIT',permissions=perms,geometry=geo,burden_records=records,
        mask_conversion=converted,mask_conversion_error=conversion_error,n11_request_draft=request,
        model_invoked=False,automatic_generation=False,n11_comparison=comparisons,
        n12_original_engineering_rules=scoring,n12_disposition_changed=False,
        domain_intervals=domains,epitope_hotspot_intervals=hotspots,scales_sha256=sha(files['input/scales.json']),
        functional_domain_assessment='NOT_ASSESSED' if domains is None else 'CONFIRMED_EMPTY' if not domains else 'OBJECTS_PRESENT',
        review_reasons=reasons,formal_design_permissions=None,formal_mutation_burden=None,formal_validation=None)

    if body.get('t4_handshake') and request is not None and not perms['fixed_positions']:
        request['t4_empty_fixed_confirmation']=False
        result.update(n11_request_draft=None, pending_n11_request_draft=request,
            confirmation_required=True, confirmation_code='T4_EMPTY_FIXED_CONFIRMATION_REQUIRED')
    return result
