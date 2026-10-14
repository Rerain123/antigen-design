"""C44 2026-10-09 shared Eq1/2/3 kernel for calibration and business sequences."""
import math
import numpy as np

from ...common import ensure

AA = 'ACDEFGHIKLMNPQRSTVWY'


def encode_sequence(sequence):
    ensure(isinstance(sequence, str) and sequence and set(sequence) <= set(AA),
           'INVALID_REQUEST', 'CamSol requires a nonempty AA20 sequence')
    return np.array([[AA.index(a) for a in sequence]], dtype=np.int64)


def pattern_counts(encoded, params):
    table = params['roseman_scale']['values']
    classes = np.array([-1 if table[a] <= -.5 else 1 if table[a] >= .5 else 0 for a in AA])
    signs = classes[encoded]; length = encoded.shape[1]
    counts = np.zeros(encoded.shape, dtype=np.int64)
    for start in range(5):
        if length < 5:
            break
        if start == 0:
            match = signs[:, :length-4] != 0
            for offset in range(1, 5):
                match &= signs[:, offset:length-4+offset] == signs[:, :length-4]*(-1)**offset
        counts[:, start:length-4+start] += match
    return counts


def hh_charges(encoded, params, target_ph, his_tag_positions=()):
    ensure(type(target_ph) in (int, float) and math.isfinite(target_ph),
           'INVALID_REQUEST', 'CamSol pH must be finite')
    pka = params['pka_table_median']; table = np.zeros(20)
    # Stable logistic evaluates the specified HH formulas even at extreme finite pH.
    def fraction(delta):
        if delta >= 0:
            small = 10.**(-min(delta, 400.))
            return small/(1+small)
        return 1/(1+10.**max(delta, -400.))
    for residue, name in [('D','ASP'),('E','GLU'),('Y','TYR')]:
        table[AA.index(residue)] = -fraction(pka[name]-target_ph)
    for residue, name in [('H','HIS'),('K','LYS'),('R','ARG')]:
        table[AA.index(residue)] = fraction(target_ph-pka[name])
    charge = table[encoded].copy()
    charge[:, 0] += fraction(target_ph-pka['N_terminus'])
    charge[:, -1] -= fraction(pka['C_terminus']-target_ph)
    ensure(isinstance(his_tag_positions, (list, tuple)) and len(set(his_tag_positions)) == len(his_tag_positions),
           'INVALID_REQUEST', 'Explicit unique His tag positions required')
    for position in his_tag_positions:
        ensure(type(position) is int and 1 <= position <= encoded.shape[1]
               and np.all(encoded[:, position-1] == AA.index('H')),
               'INVALID_REQUEST', 'His tag position must identify histidine')
        charge[:, position-1] += fraction(target_ph-pka['His_tag'])-table[AA.index('H')]
    return charge


def raw_profile(encoded, params, *, target_ph=None, his_tag_positions=(), details=False):
    encoded = np.asarray(encoded)
    ensure(encoded.ndim == 2 and encoded.shape[0] > 0 and encoded.shape[1] > 0
           and encoded.dtype.kind in 'iu' and np.all((encoded >= 0) & (encoded < 20)),
           'INVALID_REQUEST', 'CamSol kernel requires a nonempty AA20 index matrix')
    scales = params['amino_acid_scales']; coeff = params['linear_coefficients']
    fixed_charge = np.array([scales[a]['charge'] for a in AA])[encoded]
    charge = fixed_charge
    if target_ph is not None:
        charge = hh_charges(encoded, params, target_ph, his_tag_positions)
    else:
        ensure(not his_tag_positions, 'INVALID_REQUEST', 'His tag partial charges require pH mode')
    base = np.array([math.fsum(coeff[k]*scales[a][v] for k,v in (
        ('a_H','hydrophobicity'),('a_alpha','alpha'),('a_beta','beta'))) for a in AA])
    eq1 = base[encoded]+coeff['a_C']*charge
    length = encoded.shape[1]; smooth = np.zeros(eq1.shape); denominator = np.zeros(length)
    gatekeeper = np.zeros(eq1.shape)
    for shift in range(-5, 6):
        begin, end = max(0, -shift), min(length, length-shift)
        if begin >= end:
            continue
        # The shared Spec explicitly substitutes Eq1 p_C only in Layer2 MVP.
        gatekeeper[:, begin:end] += math.exp(-abs(shift)**4/200)*fixed_charge[:, begin+shift:end+shift]
        if abs(shift) <= 3:
            smooth[:, begin:end] += eq1[:, begin+shift:end+shift]
            denominator[begin:end] += 1
    smooth /= denominator
    counts = pattern_counts(encoded, params)
    corrections = params['correction_coefficients']
    profile = smooth+corrections['a_pat']*counts+corrections['a_gk']*gatekeeper
    ensure(np.isfinite(profile).all(), 'OUTPUT_INVALID', 'CamSol raw profile must be finite')
    if not details:
        return profile
    return dict(eq1_raw=eq1[0].tolist(), eq2_smoothing_term=smooth[0].tolist(),
                eq3_gatekeeper=gatekeeper[0].tolist(), pattern_counts=counts[0].tolist(),
                charges=charge[0].tolist(), eq2_complete=profile[0].tolist())
