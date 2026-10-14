"""C18/R-35 signed relative scores and bounded re-evaluation, without model calls."""
import math
from decimal import Decimal
from ...common import ensure


def evaluate(baseline,records):
    ensure(type(baseline) in (float,int) and math.isfinite(baseline) and baseline<0,
        'OUTPUT_INVALID','Finite negative WT log-likelihood required; zero denominator is invalid')
    rows=[]
    for record in records:
        score=record['score']
        if score is None:
            rows.append(dict(sample_number=record['sample_number'],esm_if1_score=None,delta_pct=None,passed=None,
                reason_code=record['error_code'] or 'SCORE_UNAVAILABLE'));continue
        ensure(type(score) in (float,int) and math.isfinite(score) and score<=0,'OUTPUT_INVALID','Invalid native log-likelihood')
        # Decimal preserves the declared > threshold boundary; do not round or negate native scores.
        delta=(Decimal(str(score))-Decimal(str(baseline)))/abs(Decimal(str(baseline)))
        rows.append(dict(sample_number=record['sample_number'],esm_if1_score=score,delta_pct=float(delta*100),
            passed=None,reason_code=None))
    history=[];rounds=[];threshold=.10;quality='standard'
    for threshold,quality in ((.10,'standard'),(.15,'relaxed'),(.20,'minimal')):
        for row in rows:
            if row['esm_if1_score'] is not None:
                delta=(Decimal(str(row['esm_if1_score']))-Decimal(str(baseline)))/abs(Decimal(str(baseline)))
                row['passed']=delta>=-Decimal(str(threshold));row['reason_code']=None if row['passed'] else 'R35_DETERIORATION_EXCEEDED'
        rounds.append(dict(threshold=threshold,passed=[r['sample_number'] for r in rows if r['passed'] is True],
            excluded=[r['sample_number'] for r in rows if r['passed'] is False],unavailable=[r['sample_number'] for r in rows if r['passed'] is None]))
        if threshold>.10:history.append(dict(step='validate_design',parameter='esm_if1恶化容忍',original_value=.10,
            relaxed_value=threshold,quality_flag=quality))
        if not rows or any(r['passed'] is not False for r in rows):break
    all_excluded=bool(rows) and all(r['passed'] is False for r in rows)
    return dict(rule='R-35',baseline_used=baseline,records=rows,threshold=threshold,quality_flag=quality,
        relaxation_history=history,rounds=rounds,all_excluded=all_excluded,
        failure_report='ALL_EXCLUDED_AFTER_20_PERCENT' if all_excluded else None,
        scope='ESM_IF1_ENGINEERING_RULE_ONLY',complete_validation_passed=None,structure_recheck='NOT_EXECUTED',mutation_burden=None)
