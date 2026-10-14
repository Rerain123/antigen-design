"""Compute the expert's full reference pool and two independent validation pools.

No biological task is submitted. Original expert assets are read-only; actual
statistics are written to a separately versioned derived parameter asset.
"""
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from t01_phase1_real.common import decode, encode, ensure, sha
from t01_phase1_real.development.expert_feedback import authority, ROOT as EXPERT
from t01_phase1_real.development.developability.calibration import assets, batches, moments
from t01_phase1_real.development.developability.camsol_kernel import raw_profile, AA

OUTPUT = ROOT/'src/t01_phase1_real/development/developability/assets/camsol-20261009-v1'
REPORT = ROOT/'reports/expert-feedback-20261009'


def calculate(params, frequencies, seed):
    counts = 0; summary = None; checkpoints = []
    for encoded in batches(frequencies, seed=seed, length=200, count=100000, batch_size=250):
        profile = raw_profile(encoded, params)
        ensure(profile.shape == encoded.shape, 'OUTPUT_INVALID', 'Calibration profile shape differs')
        part = moments([profile]); counts += encoded.shape[0]
        if summary is None:
            summary = part
        else:
            n, m = summary['count'], part['count']; total = n+m
            delta = part['mean']-summary['mean']
            variance = (summary['population_std']**2*n+part['population_std']**2*m+delta**2*n*m/total)/total
            summary = dict(count=total, mean=summary['mean']+delta*m/total, population_std=math.sqrt(variance))
        if counts in (10000, 50000, 100000):
            checkpoints.append(dict(sequence_count=counts, **summary))
    ensure(counts == 100000 and summary['count'] == 20000000, 'OUTPUT_INVALID', 'Incomplete calibration pool')
    return dict(seed=seed, sequence_count=counts, **summary, checkpoints=checkpoints)


def main():
    receipt = authority(); original = (EXPERT/'camsol_params.json').read_bytes(); params = decode(original)
    ensure(sha(original) == (EXPERT/'camsol_params.json.sha256').read_text().strip(),
           'HASH_MISMATCH', 'Expert parameter sidecar differs')
    prepared = assets(); frequencies = prepared['frequencies']
    ensure(prepared['release'] == 'Swiss-Prot 2026_03' and prepared['amino_acid_order'] == AA,
           'OUTPUT_INVALID', 'CamSol reference frequency identity differs')
    main_pool = calculate(params, frequencies, 4401)
    checks = [calculate(params, frequencies, seed) for seed in (4402, 4403)]
    mean, std = main_pool['mean'], main_pool['population_std']
    ensure(math.isfinite(mean) and math.isfinite(std) and std > 0, 'OUTPUT_INVALID', 'Invalid actual moments')
    for check in checks:
        check.update(mean_shift_over_main_sigma=abs(check['mean']-mean)/std,
            relative_sigma_difference=abs(check['population_std']/std-1),
            normalized_with_main=dict(mean=(check['mean']-mean)/std, std=check['population_std']/std))
    code = ROOT/'src/t01_phase1_real/development/developability'
    implementation = {n: sha((code/n).read_bytes()) for n in ('camsol_kernel.py', 'calibration.py')}
    report = dict(kind='C44_EQ2_ACTUAL_REFERENCE_STATISTICS', protocol=receipt,
        parameter_original_sha256=sha(original), implementation=implementation,
        frequencies=frequencies, published_percent=prepared['published_percent'], release=prepared['release'],
        original_percent_sum=math.fsum(prepared['published_percent'].values()),
        rng='numpy.PCG64', numpy_version=np.__version__, aa_order=AA, batch_size=250, length=200,
        ddof=0, all_positions_included=True, calibration_mode='intrinsic', main=main_pool, checks=checks,
        statistics_status='CANDIDATE_STATISTICS_NO_PREDECLARED_ACCEPTANCE_TOLERANCE',
        validation_status='NOT_ASSESSED', scientific_consumption=False, new_scientific_jobs=0)
    OUTPUT.mkdir(parents=True, exist_ok=True); REPORT.mkdir(parents=True, exist_ok=True)
    report_raw = encode(report); digest = sha(report_raw)
    derived = copy.deepcopy(params)
    derived['random_normalization'].update(mu_random=mean, sigma_random=std,
        statistics_status=report['statistics_status'], receipt_sha256=digest,
        sequence_length=200, sequence_count=100000, position_count=20000000, ddof=0)
    derived['derived_asset'] = dict(version='camsol-20261009-v1', source_sha256=sha(original),
        authority=receipt, scientific_validation='NOT_ASSESSED', original_modified=False)
    raw = encode(derived)
    for name, data in {'calibration.json':report_raw, 'camsol_params.json':raw,
                       'camsol_params.json.sha256':(sha(raw)+'\n').encode()}.items():
        path = OUTPUT/name
        if path.exists():
            ensure(path.read_bytes() == data, 'HASH_MISMATCH', 'Versioned calibration must not be overwritten')
        else:
            path.write_bytes(data)
    (REPORT/'calibration.json').write_bytes(report_raw)
    print(json.dumps(dict(parameter_sha256=sha(raw), calibration_sha256=digest,
        mu=mean, sigma=std, positions=main_pool['count'], checks=[dict(seed=c['seed'],
        mean_delta=c['mean_shift_over_main_sigma'], sigma_delta=c['relative_sigma_difference']) for c in checks],
        status=report['statistics_status']), indent=2))


if __name__ == '__main__':
    main()
