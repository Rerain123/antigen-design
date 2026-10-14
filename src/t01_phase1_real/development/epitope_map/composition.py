"""S-19 canonical weighted composition, keeping unknown operands explicit."""
import math

from ...common import ensure

WEIGHTS = {'E1-single': .2, 'E2-consensus': .5, 'E3-region': .8, 'E4-contact': 1.0}


def settings(value=None):
    if value is None:return dict(channel_weights=dict(bcell=.5,tcell=.5),hotspot_threshold=.5)
    ensure(isinstance(value,dict) and set(value)=={'channel_weights','hotspot_threshold'},
           'INVALID_REQUEST','S-19 composition settings require channel_weights and hotspot_threshold')
    weights=value['channel_weights'];threshold=value['hotspot_threshold']
    ensure(isinstance(weights,dict) and set(weights)=={'bcell','tcell'}
           and all(type(w) in (int,float) and math.isfinite(w) and 0<=w<=1 for w in weights.values())
           and math.isclose(sum(weights.values()),1,rel_tol=0,abs_tol=1e-12),
           'INVALID_REQUEST','S-19 channel weight proportions must be nonnegative and sum to one')
    ensure(type(threshold) in (int,float) and math.isfinite(threshold) and .3<=threshold<=.7,
           'INVALID_REQUEST','S-19 hotspot threshold must be within the expert range 0.3..0.7')
    return value


def channel_weights(present,parameters):
    total=sum(parameters['channel_weights'][k] for k in present)
    ensure(total>0,'INVALID_REQUEST','Available S-19 channels have no positive configured weight')
    return {k:parameters['channel_weights'][k]/total for k in present}


def synthesize(length, b_map, t_map, labels=None, parameters=None):
    maps = {k:v for k,v in [('bcell',b_map),('tcell',t_map)] if v is not None}
    ensure(maps, 'TOOL_FAILED', 'S-19 requires at least one predictor')
    parameters=settings(parameters);weights=channel_weights(maps,parameters)
    channels = {}; reasons = []
    for kind, value in maps.items():
        if weights[kind]==0:
            channels[kind]=[0.0]*length
            continue
        # Raw BepiPred columns are preserved, but OI-026 cannot be resolved here.
        if kind == 'bcell' and value.get('selected_project_score') is None:
            channels[kind] = None
            reasons.append('OI_026_BCELL_PROJECT_SCORE_UNRESOLVED')
            continue
        levels = [None]*length; scores = [0.0]*length; unknown = set()
        regions = value.get('regions') or [] if kind == 'bcell' else (
            (value.get('presentation_hotspots') or []) + (value.get('evidence_regions') or []))
        profile = value.get('residue_inverse_minmax_score') if kind == 'tcell' else None
        for region in regions:
            start,end,level = region['start'],region['end'],region['epitope_level']
            ensure(1 <= start <= end <= length and level in WEIGHTS, 'OUTPUT_INVALID', 'Invalid S-19 evidence interval')
            for offset in range(start-1,end):
                # MHC scores use the per-residue minimum covering peptide rank.
                norm = profile[offset] if kind == 'tcell' and profile is not None else region.get('norm_score')
                previous = levels[offset]
                if previous is not None and WEIGHTS[level] < WEIGHTS[previous]: continue
                if norm is None:
                    unknown.add(offset); levels[offset] = level
                    continue
                ensure(type(norm) in (int,float) and math.isfinite(norm) and 0 <= norm <= 1,
                       'OUTPUT_INVALID', 'S-19 normalized score is out of range')
                weighted = WEIGHTS[level]*norm
                if previous is None or WEIGHTS[level] > WEIGHTS[previous]:
                    scores[offset] = weighted; unknown.discard(offset)
                else:
                    scores[offset] = max(scores[offset],weighted)
                levels[offset] = level
        if unknown:
            channels[kind] = None
            reasons.append('EVIDENCE_NORMALIZATION_INPUT_UNAVAILABLE_'+kind.upper())
        else: channels[kind] = scores
    if any(v is None for v in channels.values()):
        return dict(status='review_required',density=None,hotspots=None,channel_density=channels,
                    channel_weights=weights,reason_codes=reasons)
    density = [math.fsum(weights[k]*channels[k][i] for k in maps) for i in range(length)]
    hotspots = []; start = None
    for index in range(length+1):
        active = index < length and density[index] > parameters['hotspot_threshold']
        if active and start is None: start=index
        if start is not None and not active:
            if index-start >= 8:
                row=dict(start=start+1,end=index,weighted_score=math.fsum(density[start:index])/(index-start))
                if labels is not None: row['in_outside_region']=any(v in ('outside','signal') for v in labels[start:index])
                hotspots.append(row)
            start=None
    return dict(status='computed_unreviewed',density=density,hotspots=hotspots,channel_density=channels,
                channel_weights=weights,reason_codes=[])
