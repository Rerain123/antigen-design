"""S17 operators and the expert's separately versioned 2026-10-09 peak policy."""
import math

from ...common import ensure


def scores(values):
    ensure(isinstance(values, (list, tuple)) and values and all(
        type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values),
        'OUTPUT_INVALID', 'S17 requires finite probabilities in sequence order')
    return values


def threshold_mask(values, threshold=.1512):
    ensure(type(threshold) in (int, float) and math.isfinite(threshold) and .10 <= threshold <= .20,
           'INVALID_REQUEST', 'S17 threshold outside the expert range')
    return [v > threshold for v in scores(values)]


def native_top20_mask(values):
    """Pinned CLI behavior only: round(n*.2), ties in original sequence order."""
    values = scores(values)
    selected = set(sorted(range(len(values)), key=lambda i: values[i], reverse=True)[:round(len(values)*.2)])
    return [i in selected for i in range(len(values))]


def segments(mask):
    ensure(isinstance(mask, (list, tuple)) and all(type(v) is bool for v in mask),
           'OUTPUT_INVALID', 'S17 mask must contain booleans')
    result = []; start = None
    for i, active in enumerate([*mask, False], 1):
        if active and start is None:
            start = i
        if not active and start is not None:
            result.append(dict(start=start, end=i-1)); start = None
    return result


def checked_intervals(rows):
    previous = 0
    for row in rows:
        start, end = row['start'], row['end']
        ensure(type(start) is int and type(end) is int and previous < start <= end,
               'OUTPUT_INVALID', 'S17 intervals must be ordered, positive and disjoint')
        previous = end
    return rows


def minimum_length(rows, length=6):
    ensure(type(length) is int and length >= 1, 'INVALID_REQUEST', 'Invalid minimum peak length')
    return [dict(r) for r in checked_intervals(rows) if r['end']-r['start']+1 >= length]


def bridge(rows, gap=2):
    ensure(type(gap) is int and gap >= 0, 'INVALID_REQUEST', 'Invalid bridge gap')
    merged = []
    for row in checked_intervals(rows):
        if merged and row['start']-merged[-1]['end']-1 <= gap:
            merged[-1]['end'] = row['end']
        else:
            merged.append(dict(row))
    return merged


def inspect(raw_scores):
    """Column-wise diagnostic evidence; never S19 input or a project peak set."""
    ensure(isinstance(raw_scores, list) and raw_scores and
           [r['sequence_position'] for r in raw_scores] == list(range(1, len(raw_scores)+1)),
           'OUTPUT_INVALID', 'BepiPred diagnostic positions differ')
    columns = {}
    for column in ('ensemble_probability', 'linear_epitope_score'):
        values = [r[column] for r in raw_scores]
        mask = threshold_mask(values)
        columns[column] = dict(above_project_threshold_positions=[i for i,v in enumerate(mask, 1) if v],
                               native_top20_positions=[i for i,v in enumerate(native_top20_mask(values), 1) if v],
                               strict_threshold_segments=segments(mask))
    return dict(status='DIAGNOSTIC_ONLY', columns=columns, selected_project_score=None,
                linear_scores=None, linear_peaks=None, scientific_consumption=False,
                unresolved=['project_score_column', 'top20_combination', 'filter_bridge_order',
                            'mean_score_residue_set', 'length_feature_variant'])


def project(raw_scores):
    """2026-10-09 proposed policy: raw ensemble, bridge then length filter."""
    from ..expert_feedback import authority
    inspect(raw_scores)  # Validate both native columns and their positions.
    values = [r['ensemble_probability'] for r in raw_scores]
    ordered = sorted(range(len(values)), key=lambda i: (-values[i], i))
    count = math.floor(.2*len(values)); chosen = set(ordered[:count])
    top = [i in chosen for i in range(len(values))]
    cutoff = values[ordered[count-1]] if count else None
    tied = [i+1 for i,v in enumerate(values) if v == cutoff] if cutoff is not None else []
    split_tie = bool(count and count < len(values) and values[ordered[count]] == cutoff)

    def extract(mask):
        output = []
        for row in minimum_length(bridge(segments(mask))):
            start, end = row['start'], row['end']; subset = values[start-1:end]; selected = mask[start-1:end]
            positives = [v for v, active in zip(subset, selected) if active]
            positive_count = len(positives)
            longest = max((r['end']-r['start']+1 for r in segments(selected)), default=0)
            output.append(dict(row, mean_score=math.fsum(subset)/len(subset),
                mean_score_all=math.fsum(subset)/len(subset), mean_score_positive=math.fsum(positives)/positive_count,
                positive_count=positive_count, positive_fraction=positive_count/len(subset),
                longest_positive_run=longest, bridge_count=len(subset)-positive_count))
        return output

    threshold = extract(threshold_mask(values)); top20 = extract(top)
    return dict(status='computed_pending_calibration', policy_version='s17-20261009-v1', authority=authority(),
        linear_scores=values, linear_peaks=threshold, linear_peaks_threshold=threshold,
        linear_peaks_top20=top20, conf_scores=None, conf_peaks=None, epitope_map=None,
        selected_project_score='ensemble_probability', csv_score_column='BepiPred-3.0 score',
        canonical_parameters=dict(threshold=.1512, comparison='strictly_greater', top_fraction=.2,
            top_count_method='floor', min_peak_length=6, gap_tolerance=2, add_seq_len=False,
            processing_order=['continuous_segments','bridge','minimum_length'],
            mean_score_scope='ALL_RESIDUES_INCLUDING_BRIDGES', positive_count_hard_filter=False),
        top20_audit=dict(count=count, cutoff_score=cutoff, tied_positions=tied, tie_split=split_tie,
            selected_positions=[i+1 for i in sorted(chosen)], tie_rule='sequence_position_ascending',
            usage='REPORT_COMPARISON_ONLY_NOT_S19'),
        interpretation='连续预测候选区段；不是实验验证的线性表位', scientific_consumption=False)
