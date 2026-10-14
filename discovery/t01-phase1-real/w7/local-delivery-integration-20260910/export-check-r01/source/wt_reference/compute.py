from ...common import decode,sha,encode
from . import policy

def evaluate(body,files):
    receipts=decode(files['input/source-receipts.json'])
    values={n:decode(files['input/'+n+'-result.json']) for n in policy.PRODUCERS if receipts[n]['state']=='available'}
    engines={};reasons=[]
    permissions=(values.get('design_audit') or {}).get('audit',{}).get('permissions')
    protected=sorted(r['position'] for r in (permissions or {}).get('per_residue',[]) if r['design_permission'] in ('FIXED','RESTRICTED'))
    for name in ('foldx','thermompnn'):
        req=decode(files['input/'+name+'-request.json']) if 'input/'+name+'-request.json' in files else None
        value=values.get(name);parsed=decode(files['input/'+name+'-verified-scan.json']) if value else None
        rows=(parsed['rows'] if name=='foldx' else parsed['predictions']) if parsed else []
        excluded=(req['fixed_positions'] if name=='foldx' else req['excluded_positions']) if req else []
        effective=sorted({r['position'] for r in rows})
        engines[name]=dict(state=receipts[name]['state'],status=value['status'] if value else None,
            requested_positions=req['scan_positions'] if req else None,excluded_positions=excluded,
            scope_source=req['scope_source'] if req else None,effective_positions=effective,records=rows,
            comparison_set_sha256=sha(encode([(r['position'],r['wt'],r['mut']) for r in rows])),
            source=receipts[name],protected_positions_in_observed_scope=sorted(set(effective)&set(protected)),
            ranking_scope='PRESERVED_ORIGINAL_ENGINE_COMPARISON_SET',scientific_pass=None)
        if not value:reasons.append(dict(code='SCAN_'+receipts[name]['state'].upper(),source=name))
        if value and not rows:reasons.append(dict(code=value['status'].upper(),source=name))
    sets=[{(r['position'],r['wt'],r['mut']) for r in engines[n]['records']} for n in ('foldx','thermompnn')]
    intersection=sorted(sets[0]&sets[1])
    reasons.extend([dict(code='OI_011_SCIENTIFIC_SCAN_SCOPE_AND_CONSENSUS_UNSIGNED',source='N17'),
        dict(code='HISTORICAL_REFERENCE_DOES_NOT_TRIGGER_SCAN_OR_GRANT_GATE',source='N17')])
    if permissions is None:reasons.append(dict(code='SCIENTIFIC_PERMISSIONS_MISSING',source='design_audit'))
    if 'structure' not in values:reasons.append(dict(code='STRUCTURE_'+receipts['structure']['state'].upper(),source='structure'))
    if 'topology' not in values:reasons.append(dict(code='TOPOLOGY_'+receipts['topology']['state'].upper(),source='topology'))
    return dict(kind='LOCAL_WT_STABILITY_REFERENCE',wt_sequence_sha256=sha(body['protein_sequence'].encode()),
        structure_source=body['upstream']['structure'],engines=engines,
        common_observed_mutations=[dict(position=p,wt=w,mut=m) for p,w,m in intersection],
        same_comparison_set=bool(sets[0]) and sets[0]==sets[1],combined_ddg=None,consensus_ranking=None,
        scientific_scan_trigger='NOT_EVALUATED',scientific_pass=None,scan_invocations=0,
        protected_positions=protected if permissions else None,topology=values.get('topology'),
        structure_quality=(values.get('structure') or {}).get('analysis',{}).get('quality'),
        review_reasons=reasons,source_receipts=receipts)
