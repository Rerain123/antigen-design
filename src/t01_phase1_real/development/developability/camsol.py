"""C44 versioned numerical assessment; scientific validation remains separate."""
import math
from pathlib import Path

from ...common import REPO, decode, ensure, sha

ASSET = REPO / '工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/camsol_params.json'
ASSET_SHA256 = 'fb135655bf2bf326db5c94a3c914a6a85eb2dd0de1bf6aa909ca2f8f27f629f4'


def parameters():
    raw = ASSET.read_bytes()
    ensure(sha(raw) == ASSET_SHA256 and
           ASSET.with_suffix('.json.sha256').read_text(encoding='utf8').strip() == ASSET_SHA256,
           'HASH_MISMATCH', 'C44 expert parameter asset hash mismatch')
    return decode(raw)


def intrinsic_terms(sequence, params):
    """Eq.1, boundary-truncated smooth term and Eq.3, before pattern correction."""
    scales = params['amino_acid_scales']; a = params['linear_coefficients']
    ensure(isinstance(sequence, str) and sequence and all(aa in scales for aa in sequence),
           'INVALID_REQUEST', 'C44 requires a nonempty AA20 sequence')
    raw = [math.fsum((a['a_H'] * scales[aa]['hydrophobicity'],
                     a['a_C'] * scales[aa]['charge'],
                     a['a_alpha'] * scales[aa]['alpha'],
                     a['a_beta'] * scales[aa]['beta'])) for aa in sequence]
    smooth = [math.fsum(raw[max(0, i-3):i+4]) / len(raw[max(0, i-3):i+4])
              for i in range(len(sequence))]
    gatekeeper = [math.fsum(math.exp(-abs(j-i)**4/200) * scales[sequence[j]]['charge']
                           for j in range(max(0, i-5), min(len(sequence), i+6)))
                  for i in range(len(sequence))]
    return dict(eq1_raw=raw,eq2_smoothing_term=smooth,eq3_gatekeeper=gatekeeper,
                eq2_complete=None,normalized_profile=None,
                qualification='INTERMEDIATE_ONLY_NOT_SOLUBILITY')


def assess(sequence, target_ph=None):
    from .camsol_kernel import encode_sequence, raw_profile
    from .camsol_numerics import normalize, summarize
    params, identity = registered_parameters()
    terms = raw_profile(encode_sequence(sequence), params, target_ph=target_ph, details=True)
    norm = params['random_normalization']
    profile = normalize(terms['eq2_complete'], mu=norm['mu_random'], sigma=norm['sigma_random'])
    summary = summarize(profile)
    return dict(status='computed_unreviewed',reliable=False,
                reason_code='CAMSOL_SCIENTIFIC_VALIDATION_NOT_COMPLETED',
                global_score=summary['eq9_value'],per_residue=profile,
                classification=summary['classification'],insoluble_regions=summary['insoluble_regions'],
                mode='intrinsic' if target_ph is None else 'ph_mvp',
                ph_used='neutral' if target_ph is None else target_ph,
                tool='CamSol-reimpl(C44)',blocked_dependencies=['CAMSOL_REFERENCE_VALIDATION_NOT_COMPLETED'],
                intermediate_terms=terms,parameter_sha256=identity['parameter_sha256'],
                parameter_completeness='COMPLETE',consistency_status='NOT_ASSESSED',
                normalization_status=norm['statistics_status'],backend_identity=identity,
                method_summary=dict(source='C_SPEC_CamSol_reimpl 20261009 / normalization protocol',network=False,
                    random_sequence_length=200,random_sequence_count=100000,
                    all_reference_positions=20000000,normalization_mode='FIXED_LAYER1_REFERENCE_FOR_BOTH_MODES',
                    hh_substitution='EQ1_P_C_ONLY;EQ3_NEUTRAL_CHARGE_UNCHANGED',
                    his_tag_assignment='NO_EXPLICIT_TAG_DECLARATION;NO_INFERRED_TAG',
                    classification_source='A_SOP_R51_PROJECT_RULE_NOT_OFFICIAL_ENUM',
                    official_numeric_comparison='NOT_PERFORMED',
                    validation_groups={name:'NOT_PERFORMED' for name in ('gammabody_seven_variants','bsa_five_ph','five_protein_profile_correlation')}),
                scientific_consumption=False)


CURRENT_ASSETS = Path(__file__).parent/'assets/camsol-20261009-v1'
CURRENT_PARAMETER_SHA256 = '299b121a33ac066cc7dfe9a4eb916f848740cbb612faa6f6de6914cea379cc4e'
CURRENT_CALIBRATION_SHA256 = '34751600237f6398c5c326087e2c470d4c27ac8d4d0a937b69d080ee184de4aa'


def registered_parameters():
    from ..expert_feedback import authority, ROOT as EXPERT
    receipt = authority()
    ensure(all((CURRENT_ASSETS/n).is_file() for n in ('camsol_params.json','camsol_params.json.sha256','calibration.json')),
           'DEPENDENCY_MISSING', 'CamSol versioned parameters/calibration are unavailable')
    raw = (CURRENT_ASSETS/'camsol_params.json').read_bytes()
    ensure(sha(raw) == CURRENT_PARAMETER_SHA256 and
           (CURRENT_ASSETS/'camsol_params.json.sha256').read_text().strip() == CURRENT_PARAMETER_SHA256,
           'HASH_MISMATCH', 'Current CamSol parameter asset/sidecar changed')
    calibration = (CURRENT_ASSETS/'calibration.json').read_bytes()
    ensure(sha(calibration) == CURRENT_CALIBRATION_SHA256,
           'HASH_MISMATCH', 'CamSol calibration receipt changed')
    result = decode(raw); record = decode(calibration); norm = result['random_normalization']
    ensure(norm.get('mu_random') is not None and norm.get('sigma_random') is not None,
           'DEPENDENCY_MISSING', 'CamSol normalization statistics are missing')
    for name, digest in record['implementation'].items():
        ensure(sha((CURRENT_ASSETS.parent.parent/name).read_bytes()) == digest,
               'HASH_MISMATCH', 'CamSol profile kernel changed; calibration must be versioned again')
    ensure(record['protocol'] == receipt and record['parameter_original_sha256'] == sha((EXPERT/'camsol_params.json').read_bytes())
           and norm['receipt_sha256'] == CURRENT_CALIBRATION_SHA256 and record['main']['count'] == 20000000
           and norm['mu_random'] == record['main']['mean'] and norm['sigma_random'] == record['main']['population_std']
           and type(norm['mu_random']) in (int,float) and math.isfinite(norm['mu_random'])
           and type(norm['sigma_random']) in (int,float) and math.isfinite(norm['sigma_random']) and norm['sigma_random'] > 0,
           'OUTPUT_INVALID', 'Incomplete or unbound CamSol normalization statistics')
    return result, dict(version='camsol-20261009-v1', authority=receipt,
        parameter_sha256=CURRENT_PARAMETER_SHA256, calibration_sha256=CURRENT_CALIBRATION_SHA256,
        validation_status='NOT_ASSESSED')
