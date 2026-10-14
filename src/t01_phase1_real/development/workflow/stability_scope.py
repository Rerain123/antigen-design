"""SOP v10.5 S-31/R-37/R-41: complete allowed WT scan, never one-site sampling."""
import math
from ...common import ensure, encode, sha


def intervals(positions):
    out=[]
    for p in sorted(set(positions)):
        if out and p==out[-1]['end']+1:out[-1]['end']=p
        else:out.append(dict(start=p,end=p))
    return out


def region(value,length):
    ensure(isinstance(value,list) and len(value)==2 and all(type(p) is int for p in value)
           and 1<=value[0]<=value[1]<=length,'INVALID_REQUEST','Scan region must be [start,end], 1-based inclusive')
    return set(range(value[0],value[1]+1))


def scope(rt,body,rows):
    if rows.get('structure',{}).get('state')!='succeeded':return None,'STRUCTURE_UNAVAILABLE'
    if rows.get('topology',{}).get('state')!='succeeded':return None,'TOPOLOGY_UNAVAILABLE'
    analysis=rt.result(rows['structure']['job_id'])['analysis']
    if analysis['quality']['quality']['confidence']=='low':return None,'LOW_CONFIDENCE_SCAN_SKIPPED'
    topology=rt.result(rows['topology']['job_id'])['topology']
    if topology['tm_count']:return None,'MEMBRANE_SCAN_DOMAIN_NOT_SUPPORTED'
    length=len(body['protein_sequence']);constraints=body['m1_test']['constraints'];mapping=analysis['mapping']
    covered={e['sequence_position'] for e in mapping['entries'] if e['reason']=='mapped'
             and not e['structure_residue']['insertion_code']}
    ensure(all(type(p) is int and 1<=p<=length for p in covered),'OUTPUT_INVALID','Mapped scan positions outside WT')
    excluded=set(constraints['fixed_positions'])|{r['position'] for r in constraints['restricted_positions']}
    opened=set(constraints['open_positions']);warnings=[]
    explicit=body.get('stability_scan',{}).get('scan_region')
    chosen=set(range(1,length+1));rule='WHOLE_SEQUENCE_LE_500'
    if explicit is not None:
        chosen=region(explicit,length);rule='R41_EXPLICIT_REGION'
    elif length>500:
        from ..structure.normalization import consumable_positions
        rsa_fact=analysis.get('rsa') or {}
        rsa=(consumable_positions(rsa_fact) if 'position_result' in rsa_fact
             else rsa_fact.get('raw_normalized_ratios'))
        exposed=set()
        if rsa is not None:
            ensure(isinstance(rsa,list) and len(rsa)==length,'OUTPUT_INVALID','RSA must align to complete WT sequence')
            exposed={p for p,x in enumerate(rsa,1) if type(x) in (int,float) and math.isfinite(x) and .20<=x<=1.}
            if any(x is None or type(x) not in (int,float) or not math.isfinite(x) or not 0<=x<=1 for x in rsa):
                warnings.append('RSA_PARTIAL_OR_OUT_OF_RANGE_VALUES_NOT_USED')
        if exposed:
            chosen=exposed;rule='R41_RSA_GE_0_20_CONTIGUOUS_SEGMENTS'
        else:
            hotspots=None;domains=None
            if rows.get('epitope_map',{}).get('state')=='succeeded':
                hotspots=(rt.result(rows['epitope_map']['job_id']).get('epitopes',{}).get('b_cell_antigenic_hotspot_map') or {}).get('hotspots')
            audit_name='design_audit' if rows.get('design_audit',{}).get('state')=='succeeded' else 'design_inputs'
            if rows.get(audit_name,{}).get('state')=='succeeded':
                domains=rt.result(rows[audit_name]['job_id'])['audit'].get('domain_intervals')
            if hotspots:
                chosen=set();rule='R41_HOTSPOT_PLUS_MINUS_20'
                for r in hotspots:
                    region([r['start'],r['end']],length)
                    chosen.update(range(max(1,r['start']-20),min(length,r['end']+20)+1))
            elif domains:
                chosen=set();rule='R41_DOMAIN_BOUNDARY_PLUS_MINUS_10'
                for r in domains:
                    region([r['start'],r['end']],length)
                    for p in (r['start'],r['end']):chosen.update(range(max(1,p-10),min(length,p+10)+1))
            else:
                chosen=set(range(1,501));rule='R41_FALLBACK_FIRST_500'
                warnings.append('DEFAULT_FIRST_500_PROVIDE_SCAN_REGION')
    positions=sorted(chosen & covered & opened - excluded)
    uncovered=sorted(chosen-covered)
    if uncovered:warnings.append('PARTIAL_STRUCTURE_SCAN_LIMITED_TO_MAPPED_COVERAGE')
    if any(e['reason']=='mapped' and e['structure_residue']['insertion_code'] for e in mapping['entries']):
        warnings.append('INSERTION_CODES_UNSUPPORTED_NOT_SCANNED')
    fact=dict(positions=positions,excluded=sorted(excluded),monomer=len(mapping['chain_candidates'])==1
              and not mapping['fixed_chain_ids'],selection_rule=rule,selection_regions=intervals(chosen),
              covered_positions=sorted(covered),uncovered_selected_positions=uncovered,
              not_open_selected_positions=sorted(chosen-opened),warnings=warnings,
              scope_complete_for_available_permissions=True,scientific_pass=None,
              permission_source=constraints['source_id'],sequence_sha256=sha(body['protein_sequence'].encode()),
              authority='SOP v10.5 S-31/R-37/R-41; T-01 step22',
              temporary_interpretation='All qualifying RSA runs; all hotspot expanded intervals or domain boundary windows; no extra top-N truncation')
    fact['scope_sha256']=sha(encode(fact))
    return fact,None if positions else 'NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION'


def timeout(positions):
    # Engineering budget, not a scientific threshold or promised wall time.
    # SOP estimates ~1 minute/site; allow repair/overhead within the parent's
    # existing 8h ceiling. Parent cancellation still wins over this deadline.
    return min(28800,max(900,180+90*len(positions)))
