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
        from ..proteinmpnn.policy import request as validate
        from ..proteinmpnn.mapping import project
        validate(encode(request))
        projected=project(request,values['structure'],files['input/structure-original.bin'],
            {n:decode(files['input/'+n+'.json']) for n in ('preflight','raw_metadata','raw_addresses')})
        converted={n:decode(data) for n,data in projected.items() if n.endswith(('.json','.jsonl'))}
    except (RuntimeFault,KeyError,ValueError) as exc:
        conversion_error=dict(code=getattr(exc,'code','OUTPUT_INVALID'),reason=str(exc));request=None
    domain_value=(values.get('domains') or {}).get('analysis');domains=None
    if domain_value is not None:
        # Inferred structural contact pairs are not contiguous functional-domain intervals.
        domains=[r for r in domain_value['functional_domains'] if r['source']!='structure' and r['type']!='disulfide_bond']
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
    reasons=perms['review_reasons']+[dict(source='burden',code='OI_008_FORMAL_BURDEN_CLOSED'),
        dict(source='design',code='SCIENTIFIC_GATE_AND_AGENT_C_CLOSED')]
    if records is None:reasons.append(dict(source='n11',code='VARIANTS_UNAVAILABLE_NO_BURDEN_COMPUTED'))
    if conversion_error:reasons.append(dict(source='mask_export',code='N11_MASK_EXPORT_BLOCKED',detail=conversion_error))
    return dict(kind='S27_S28_ENGINEERING_AUDIT',permissions=perms,geometry=geo,burden_records=records,
        mask_conversion=converted,mask_conversion_error=conversion_error,n11_request_draft=request,
        model_invoked=False,automatic_generation=False,n11_comparison=comparisons,
        n12_original_engineering_rules=scoring,n12_disposition_changed=False,
        domain_intervals=domains,epitope_hotspot_intervals=hotspots,scales_sha256=sha(files['input/scales.json']),
        review_reasons=reasons,formal_design_permissions=None,formal_mutation_burden=None,formal_validation=None)
