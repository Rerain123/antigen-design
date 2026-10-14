"""Identity-based development joins and C34 normalization; no mapping approval."""
import math


POSITION_POLICY='RSA_REQUIRED_POSITIONS_V1_20261010'


def position_result(ratios):
    """Keep the full coordinate axis; invalid observations are never imputed."""
    values=[];states=[]
    for value in ratios:
        valid=type(value) in (int,float) and math.isfinite(value) and 0<=value<=1
        values.append(value if valid else None)
        states.append('valid' if valid else 'missing' if value is None else 'out_of_domain')
    complete=all(s=='valid' for s in states)
    return dict(policy=POSITION_POLICY,per_residue=values,position_status=states,
        valid_positions=[i for i,s in enumerate(states,1) if s=='valid'],
        unavailable_positions=[i for i,s in enumerate(states,1) if s!='valid'],
        complete=complete,buried_fraction=(sum(r<.20 for r in values)/len(values)) if complete and values else None,
        scientific_signoff=None,usable_for_pipeline=False)


def consumable_positions(rsa):
    """Versioned development observations, after the structure result's source checks."""
    if not rsa:return None
    if 'position_result' not in rsa:
        return (rsa.get('development_result') or {}).get('per_residue')
    raw=rsa.get('raw_normalized_ratios')
    if not isinstance(raw,list) or not raw or rsa['position_result']!=position_result(raw):
        raise ValueError('RSA position policy or validity differs from raw observations')
    return list(rsa['position_result']['per_residue'])


def normalize(mapping,raw_residues,raw_areas,table,*,per_position=False):
    by_raw={r['raw_residue_id']:r for r in raw_areas}
    if len(by_raw)!=len(raw_areas):raise ValueError('Duplicate raw SASA residue')
    projections={}
    for residue in raw_residues:
        if residue['model_index']!=mapping['model_index']:continue
        projection=residue['consumers']['integer_mapping_v0_1']
        if not projection['representable']:continue
        address=projection['address']
        key=(address['chain_id'],address['res_seq'],address['insertion_code'],residue['residue_name'])
        if key in projections:raise ValueError('Raw address projection is not unique')
        projections[key]=residue['residue_id']
    areas=[];ratios=[];joined=[];outliers=[];missing=[]
    if mapping['target_chain_id'] is None:raise ValueError('No unique mapping for normalization')
    for entry in mapping['entries']:
        pos=entry['sequence_position'];mapped=entry['structure_residue']
        if mapped is None:
            if entry['reason']!='missing_structure_residue':raise ValueError('Unresolved mapping cannot become a missing position')
            areas.append(None);ratios.append(None);missing.append(pos);joined.append(None);continue
        key=tuple(mapped[k] for k in ['chain_id','res_seq','insertion_code','residue_name'])
        raw_id=projections[key];row=by_raw[raw_id]
        area=row['absolute_sasa_a2']
        if isinstance(area,bool) or not isinstance(area,(int,float)) or not math.isfinite(area) or area<0:raise ValueError('Invalid absolute SASA')
        ratio=area/table[entry['sequence_residue']]
        areas.append(area);ratios.append(ratio);joined.append(dict(sequence_position=pos,raw_residue_id=raw_id,raw_address=row['raw_address']))
        if ratio<0 or ratio>1:outliers.append(dict(sequence_position=pos,residue=entry['sequence_residue'],raw_residue_id=raw_id,absolute_sasa_a2=area,raw_ratio=ratio))
    target_ids={r['residue_id'] for r in raw_residues if r['model_index']==mapping['model_index']
        and r['address']['auth_asym_id'][0]==mapping['target_chain_id'] and r['residue_class']!='nonprotein'}
    joined_ids=[r['raw_residue_id'] for r in joined if r is not None]
    if len(joined_ids)!=len(set(joined_ids)) or set(joined_ids)!=target_ids:raise ValueError('Incomplete/duplicate target residue join')
    value=dict(status='output_invalid' if outliers else 'computed_unverified',error_code='OUTPUT_INVALID' if outliers else None,
        aligned_absolute_sasa_a2=areas,raw_normalized_ratios=ratios,identity_join=joined,missing_positions=missing,out_of_domain=outliers,
        development_result=None if outliers else dict(per_residue=ratios,buried_fraction=sum(r is not None and r<.20 for r in ratios)/len(mapping['sequence'])),
        normal_rsa_result=None,scientific_signoff=None,usable_for_pipeline=False)
    if per_position:
        value['position_result']=position_result(ratios)
        if value['development_result'] is not None:
            value['development_result']['buried_fraction']=value['position_result']['buried_fraction']
    return value
