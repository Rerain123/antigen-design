"""S-27 automatic evidence states and explicit user overrides, engineering only."""
from ...common import ensure
from .policy import AA


def interval(row,length):
    ensure(type(row['start']) is int and type(row['end']) is int and 1<=row['start']<=row['end']<=length,
        'OUTPUT_INVALID','Source interval outside WT coordinates')
    return range(row['start'],row['end']+1)


def assemble(body,values,receipts,scales):
    seq=body['protein_sequence'];evidence={p:[] for p in range(1,len(seq)+1)};review=[]
    for name,r in receipts.items():
        review.append(dict(source=name,code={'missing':'UPSTREAM_MISSING','pending':'UPSTREAM_PENDING','failed':'UPSTREAM_FAILED',
            'available':'UPSTREAM_SCIENTIFIC_SIGNOFF_MISSING'}[r['state']]))
    def add(positions,state,source,rule,path,confidence=None):
        for p in positions:
            ensure(p in evidence,'OUTPUT_INVALID','Evidence position outside WT')
            evidence[p].append(dict(constraint_state=state,source=source,rule=rule,source_path=path,
                artifact=receipts[source]['artifact'],confidence=confidence,qualification='DEVELOPMENT_UNREVIEWED'))
    domains=(values.get('domains') or {}).get('analysis') or {}
    for i,row in enumerate(domains.get('functional_domains') or []):
        pos=interval(row,len(seq));kind=row['type'];confidence=row['confidence']
        if row['source']=='structure':
            review.append(dict(source='domains',code='STRUCTURAL_DOMAIN_GEOMETRY_NOT_VALIDATED',index=i));continue
        if kind=='disulfide_bond':pos=sorted({row['start'],row['end']})
        state='HARD' if confidence in ('high','user_high') else 'RESTRICTED'
        if kind=='PTM_site':
            state='RESTRICTED';review.append(dict(source='domains',code='PTM_E2_BOUNDARY_EVIDENCE_UNAVAILABLE',index=i))
        add(pos,state,'domains','S27_VALIDATED_FUNCTIONAL' if state=='HARD' else 'S27_FUNCTIONAL_RESTRICTED',
            'analysis.functional_domains['+str(i)+']',confidence)
    # Never synthesize scientific core_map from N09 engineering components.
    review.append(dict(source='domains',code='OI_006_CORE_MAP_NULL_NOT_RECONSTRUCTED'))
    hom=(values.get('homology') or {}).get('analysis') or {};con=hom.get('conservation') or {}
    degraded=set(con.get('unreliable_query_positions') or [])
    if hom.get('global_conservation_role')=='single_subtype' and str(con.get('conservation_confidence')).upper() in ('MEDIUM','HIGH'):
        scores=con.get('score_per_residue')
        if scores is not None:
            ensure(len(scores)==len(seq),'OUTPUT_INVALID','Conservation length differs')
            for p,score in enumerate(scores,1):
                if p in degraded or score is None:continue
                ensure(type(score) in (int,float) and 0<=score<=1,'OUTPUT_INVALID','Conservation outside domain')
                if score>=.8:add([p],'RESTRICTED','homology','S27_HIGH_CONSERVATION' if score>=.93 else 'S27_MID_CONSERVATION',
                    'analysis.conservation.score_per_residue['+str(p-1)+']',con.get('conservation_confidence'))
                # VARIABLE alone cannot prove absence of other unresolved evidence.
    elif hom:review.append(dict(source='homology',code='CONSERVATION_LOW_OR_POOLED_DIAGNOSTIC_NOT_USED'))
    epitopes=(values.get('epitope_map') or {}).get('epitopes') or {}
    presentation=epitopes.get('t_cell_presentation_map') or {}
    for i,row in enumerate(presentation.get('evidence_regions') or []):
        if row.get('epitope_level')=='E1-single':
            add(interval(row,len(seq)),'SOFT','epitope_map','S27_E1_SOFT','epitopes.t_cell_presentation_map.evidence_regions['+str(i)+']')
    if body['epitope_mode']=='tcell_only':
        presentation=epitopes.get('t_cell_presentation_map') or {}
        for i,row in enumerate(presentation.get('presentation_hotspots') or []):
            add(interval(row,len(seq)),'RESTRICTED','epitope_map','S27_EXPLICIT_TCELL_PRESENTATION',
                'epitopes.t_cell_presentation_map.presentation_hotspots['+str(i)+']')
    review.append(dict(source='epitope_map',code='OI_007_E2_E3_E4_COMPOSITE_EVIDENCE_UNAVAILABLE'))
    glyco=values.get('glycosylation') or {};assessment=glyco.get('hotspot_assessment') or {}
    if assessment.get('status')=='EVALUATED' and assessment.get('source_verification')=='VERIFIED_N06_ARTIFACT_REF':
        for i,row in enumerate(assessment['windows']):
            interval(row,len(seq))
            if row['shielding_risk'] and row['end']-row['start']+1==20:
                add(row['site_positions'],'RESTRICTED','glycosylation','S27_KEY_GLYCO','hotspot_assessment.windows['+str(i)+']')
    elif glyco:review.append(dict(source='glycosylation',code='GLYCO_SHIELDING_NOT_VERIFIED'))
    topology=(values.get('topology') or {}).get('topology')
    if topology and body['membrane_design_confirm']:
        ensure(len(topology['labels'])==len(seq),'OUTPUT_INVALID','Topology length differs')
        add([p for p,label in enumerate(topology['labels'],1) if label in ('TMhelix','inside')],
            'HARD','topology','S27_CONFIRMED_MEMBRANE_FIXED','topology.labels')
    low=(((values.get('structure') or {}).get('analysis') or {}).get('low_confidence_regions'))
    if low is not None:
        for row in low:add(interval(row,len(seq)),'RESTRICTED','structure','S27_LOW_CONFIDENCE_REGION','analysis.low_confidence_regions','low')
    # No producer currently exports signed low_confidence_regions or mechanistic evidence.
    review.extend([dict(source='structure',code='LOW_CONFIDENCE_REGIONS_CONSUMER_CONTRACT_UNRESOLVED'),
        dict(source='homology',code='MECHANISTIC_EVIDENCE_EXPLICITLY_EMPTY')])
    rows=[];conflicts=[];override=False
    for p,wt in enumerate(seq,1):
        ev=evidence[p];auto='HARD' if any(e['constraint_state']=='HARD' for e in ev) else 'RESTRICTED' if any(e['constraint_state']=='RESTRICTED' for e in ev) else 'SOFT' if ev else 'RESTRICTED'
        permission='FIXED' if auto=='HARD' else 'RESTRICTED';state=auto
        allowed=''.join(a for a in AA if a==wt or scales['blosum62'][wt][a]>0)
        users=[r for r in body['user_regions'] if r['start']<=p<=r['end']]
        choices={(r['permission'],r['allowed_residues']) for r in users}
        reasons=[e['rule'] for e in ev] or ['S27_FINAL_ELSE_RESTRICTED']
        if auto=='SOFT':reasons.append('OPEN_EXPRESSION_OPERANDS_UNRESOLVED_ENGINEERING_RESTRICTED')
        if p in degraded:reasons.append('conservation_degraded')
        changed=False
        if len(choices)>1:
            conflicts.append(p);reasons.append('OI_002_CONFLICTING_USER_REGIONS_NO_PRECEDENCE')
        elif users:
            user=users[0];permission=user['permission'];state={'FIXED':'HARD','RESTRICTED':'RESTRICTED','OPEN':'SOFT'}[permission]
            if user['allowed_residues'] is not None:allowed=''.join(a for a in AA if a in user['allowed_residues'])
            changed=auto=='HARD' and permission!='FIXED';override|=changed
            reasons.append('S27_EXPLICIT_USER_OVERRIDE')
        if permission=='FIXED':allowed=wt
        if permission=='OPEN':allowed=AA
        rows.append(dict(position=p,wt_residue=wt,constraint_state=state,design_permission=permission,
            automatic_constraint_state=auto,allowed_residues=allowed,reasons=reasons,evidence_source=ev,
            user_sources=users,confidence=None,core_state=None,epitope_level=None,constraint_override=changed))
    return dict(per_residue=rows,constraint_override=override,non_standard=override,user_conflict_positions=conflicts,
        review_reasons=review,formal_design_permissions=None,scientific_release=False,
        open_basis='Explicit nonconflicting user instructions only; VARIABLE cannot resolve missing scientific operands',
        fixed_positions=[r['position'] for r in rows if r['design_permission']=='FIXED'],
        restricted_positions=[dict(position=r['position'],allowed_residues=r['allowed_residues']) for r in rows if r['design_permission']=='RESTRICTED'],
        open_positions=[r['position'] for r in rows if r['design_permission']=='OPEN'])
