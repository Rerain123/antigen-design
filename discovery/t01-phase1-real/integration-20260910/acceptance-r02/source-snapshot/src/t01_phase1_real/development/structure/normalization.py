"""Identity-based development joins and C34 normalization; no mapping approval."""
import math


def normalize(mapping,raw_residues,raw_areas,table):
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
    return dict(status='output_invalid' if outliers else 'computed_unverified',error_code='OUTPUT_INVALID' if outliers else None,
        aligned_absolute_sasa_a2=areas,raw_normalized_ratios=ratios,identity_join=joined,missing_positions=missing,out_of_domain=outliers,
        development_result=None if outliers else dict(per_residue=ratios,buried_fraction=sum(r is not None and r<.20 for r in ratios)/len(mapping['sequence'])),
        normal_rsa_result=None,scientific_signoff=None,usable_for_pipeline=False)
