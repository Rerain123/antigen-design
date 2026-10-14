"""Defined C44 arithmetic; no default pattern count or calibration is chosen.

The registered assessment shares normalization and aggregation below. Numerical
tests cannot confer scientific approval; explicit calibration is always required.
"""
import math

from ...common import ensure
from .camsol import intrinsic_terms


def corrected_profile(sequence, params, *, pattern_counts):
    terms = intrinsic_terms(sequence, params)
    ensure(isinstance(pattern_counts, (list, tuple)) and len(pattern_counts) == len(sequence)
           and all(type(n) is int and n >= 0 for n in pattern_counts),
           'INVALID_REQUEST', 'C44 requires explicit nonnegative per-residue pattern counts')
    coeff = params['correction_coefficients']
    return [math.fsum((smooth, coeff['a_pat']*pat, coeff['a_gk']*gk))
            for smooth, pat, gk in zip(terms['eq2_smoothing_term'], pattern_counts, terms['eq3_gatekeeper'])]


def normalize(profile, *, mu, sigma):
    ensure(type(mu) in (int, float) and math.isfinite(mu) and
           type(sigma) in (int, float) and math.isfinite(sigma) and sigma > 0,
           'INVALID_REQUEST', 'Explicit finite C44 mu and positive sigma required')
    _profile(profile)
    result = [(value-mu)/sigma for value in profile]
    _profile(result)
    return result


def _profile(profile):
    ensure(isinstance(profile, (list, tuple)) and profile and all(
        type(v) in (int, float) and math.isfinite(v) for v in profile),
        'OUTPUT_INVALID', 'C44 profile must be nonempty and finite')


def summarize(normalized_profile):
    _profile(normalized_profile)
    total = math.fsum(v for v in normalized_profile if abs(v) > .7)/len(normalized_profile)
    regions = []; start = None
    for i, value in enumerate([*normalized_profile, 0.], 1):
        if value < -1 and start is None:
            start = i
        if value >= -1 and start is not None:
            if i-start >= 5:
                regions.append(dict(start=start, end=i-1))
            start = None
    return dict(eq9_value=total, classification='high' if total > 1 else 'low' if total < -1 else 'medium',
                insoluble_regions=regions, qualification='NUMERICAL_KERNEL_ONLY', scientific_consumption=False)
