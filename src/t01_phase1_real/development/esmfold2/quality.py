"""SOP v10.5 S-09 for already verified normalized ESMFold2 confidence."""
import math

DEFAULTS = dict(high_plddt=0.70, medium_plddt=0.50, topology_ptm=0.50,
                low_plddt=0.50, min_region_length=5, merge_gap=3)


def assess(scores, ptm, parameters=None, source='esmfold2_predicted'):
    p = dict(DEFAULTS if parameters is None else parameters)
    if (set(p) != set(DEFAULTS) or source not in ('esmfold2_predicted','af3_predicted')
            or not scores or any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores)):
        raise ValueError('Invalid verified confidence or S09 parameters')
    mean = math.fsum(scores)/len(scores)
    regions = []; start = None
    for pos, score in enumerate([*scores, 1.0], 1):
        if score < p['low_plddt'] and start is None: start = pos
        if score >= p['low_plddt'] and start is not None:
            if pos-start >= p['min_region_length']: regions.append(dict(start=start, end=pos-1))
            start = None
    merged = []
    for r in regions:
        if merged and r['start']-merged[-1]['end']-1 <= p['merge_gap']: merged[-1]['end'] = r['end']
        else: merged.append(dict(r))
    quality = dict(confidence='high' if mean >= p['high_plddt'] else 'medium' if mean >= p['medium_plddt'] else 'low',
                   topology_reliable=ptm is not None and ptm >= p['topology_ptm'], low_confidence_regions=merged)
    return dict(structure=dict(source=source, mean_plddt=mean, plddt_per_residue=scores,
                               ptm=ptm, **quality), quality=quality, parameters=p,
                rule_basis='AgentA_SOP_v10.5_20260902 S-09; ToolSpec_结构预测获取链_v10.5 §2c/3',
                calibration='E-06 defaults; not scientifically signed off',
                scientific_gate='CLOSED', usable_for_pipeline=False, automatic_handoff=False)
