"""Step20 internal ranking of backend-verified sources, never caller scores.

Formal candidate fields remain closed. Partial inputs have individual reasons;
S-23 is outside phase-one scope and is never represented as a safety PASS.
"""
from collections import deque
from decimal import Decimal

from ...common import decode, ensure
from ..design_backend import policy as design
from ..developability.compute import summarize
from .ranking import COUNTS, WEIGHTS, finite, stability


def protection(row):
    warnings = []
    check = row.get('s28_validation') or {}
    if check.get('passed') is True and check.get('reason') == 'S28_PREDICTION_FAILED_RETAIN_R35':
        return dict(structural=None, prediction=None, norm=1., soft=False,
                    warnings=['NO_STRUCTURE_EPITOPE_NEUTRAL_NOT_VALIDATED'], missing=[])
    obs = (row.get('n13') or {}).get('observation')
    if not obs:
        return dict(structural=None, prediction=None, norm=None, soft=None,
                    warnings=[], missing=['N13_NOT_COMPUTED'])
    # Empty hotspots do not erase a real E4 validation region.
    if obs['hotspot_positions'] == [] and obs['validation_positions'] == []:
        return dict(structural=True, prediction=True, norm=1.3, soft=False,
                    warnings=['NO_HOTSPOTS_VALIDATION_SKIPPED'], missing=[])
    checks = [obs['l1']['value'], obs['l2'].get('engineering_threshold_pass'),
              obs['l3']['hotspot'].get('engineering_threshold_pass')]
    if checks[1] is None:
        checks[1] = True
        warnings.append('L2_UNAVAILABLE_OMITTED_FROM_AND_DEGRADED_VALIDATION')
    if obs['hotspot_positions'] == []:
        checks[0] = True
        warnings.append('NO_HOTSPOTS_L1_SKIPPED_E4_RETAINED')
    functional = obs['l3']['functional_rmsd']
    checks.append(functional < 2. if functional is not None else
                  True if obs['l3']['functional_reason'] == 'NO_DOMAINS_TO_VALIDATE' else None)
    if obs['l3']['functional_reason'] == 'NO_DOMAINS_TO_VALIDATE':
        warnings.append('NO_FUNCTIONAL_DOMAINS_TO_VALIDATE')
    structural = False if False in checks else None if None in checks else True
    pred = obs['l4'].get('engineering_threshold_pass')
    if pred is None:
        # SOP step19 explicitly permits missing L4, with a warning; no raw
        # prediction/scientific_pass field is changed by this ranking default.
        pred = True
        warnings.append('L4_UNAVAILABLE_TREATED_PASS_FOR_RANKING_ONLY')
    return dict(structural=structural, prediction=pred,
                norm=1. + .3 * pred if structural is True else None, soft=not pred,
                warnings=warnings, missing=['N13_STRUCTURAL_INCOMPLETE'] if structural is None else [])


def diversity(ranked, sequences):
    """Substitution-only shared-WT coordinates: BioPython aligned identities.

    Family traversal follows first occurrence in ranked_front. Equal scores use
    source inventory order, a disclosed first-version choice (not a signed rule).
    """
    from Bio.Align import Alignment
    import numpy as np
    queues = {}
    for row in ranked:
        queues.setdefault(row['family'], deque()).append(row)
    chosen = []; rejected = []; counts = dict.fromkeys(queues, 0)
    while any(queues.values()) and len(chosen) < 20:
        for family, queue in queues.items():
            if counts[family] >= 5:
                rejected.extend(dict(id=r['id'], reason='FAMILY_QUOTA') for r in queue)
                queue.clear()
            while queue and len(chosen) < 20:
                row = queue.popleft(); seq = sequences[row['id']]; duplicate = None
                for prior in chosen:
                    other = sequences[prior]
                    ensure(len(seq) == len(other) and len(seq) > 0, 'OUTPUT_INVALID',
                           'Diversity requires same-WT substitution coordinates')
                    aligned = Alignment([seq, other], np.array([[0, len(seq)], [0, len(seq)]]))
                    matches = int(aligned.counts().identities)
                    if matches * 100 > len(seq) * 95:
                        duplicate = dict(id=row['id'], reason='IDENTITY_ABOVE_0_95',
                                         retained_id=prior, identity=matches / len(seq))
                        break
                if duplicate:
                    rejected.append(duplicate)
                    continue
                chosen.append(row['id']); counts[family] += 1
                break
    rejected.extend(dict(id=r['id'], reason='TOP20_LIMIT') for q in queues.values() for r in q)
    return dict(ids=chosen, rejected=rejected, family_counts=counts, family_quota=5,
                identity_cutoff=.95, identity_method='BIOPYTHON_ALIGNED_IDENTITIES_SAME_WT_SUBSTITUTIONS',
                family_order=list(queues))


def evaluate(body, files, rows, audit):
    request = decode(files['input/design_audit-request.json']) if 'input/design_audit-request.json' in files else {}
    objective = request.get('objective')
    observations = decode(files['input/m1-observations.json']) if 'input/m1-observations.json' in files else {}
    representatives = {r['sample_number']: r for r in observations.get('representatives', [])}
    ensure(len(representatives) == len(observations.get('representatives', [])), 'OUTPUT_INVALID', 'Duplicate recomputation')
    if 'input/candidate-developability.json' in files:
        complete=decode(files['input/candidate-developability.json'])['records']
        ensure(len({r['sample_number'] for r in complete})==len(complete) and
               {r['sample_number'] for r in complete}=={r['sample_number'] for r in rows},'OUTPUT_INVALID','N10 inventory differs')
        for r in rows:
            item=next(c for c in complete if c['sample_number']==r['sample_number'])
            ensure(item['sequence_sha256']==r['sequence_sha256'],'OUTPUT_INVALID','N10 candidate sequence mismatch')
        representatives={r['sample_number']:r for r in complete}
    charge = decode((design.HERE / 'scales.json').read_bytes())['charge']
    permissions = {r['position']: r for r in (audit or {}).get('permissions', {}).get('per_residue', [])}
    inventory = []; computed = []
    for row in rows:
        reasons = [r['code'] for r in row['exclusion_reasons']]
        missing = []; warnings = []; flags = row['engineering_hard_filter']['flags']
        epi = protection(row); warnings.extend(epi['warnings']); missing.extend(epi['missing'])
        if epi['structural'] is False:
            reasons.append('N13_EPITOPE_VIOLATION')
        if row.get('non_standard'):
            reasons.append('NON_STANDARD_CONSTRAINT_OVERRIDE')
        if flags['constraint_override'] is None:
            missing.append('CONSTRAINT_AUDIT_UNAVAILABLE')
        if row['burden'] is not None and flags['burden_exceeded'] is None:
            missing.append('BURDEN_DIMENSIONS_INCOMPLETE')
        if row['burden'] is None:
            warnings.append('BURDEN_NULL_COUNT_ZERO_REFERENCE_DEFAULT')
        if (row.get('s28_validation') or {}).get('passed') is not True:
            missing.append('N12_S28_NOT_VERIFIED')
        if objective not in WEIGHTS:
            missing.append('OBJECTIVE_SOURCE_UNAVAILABLE')
        ddg = row['foldx']['ddg_foldx'] if row.get('foldx') else None
        if ddg is None:
            warnings.append('STABILITY_UNKNOWN_NEUTRAL_0_5_NOT_BENIGN')
        rep = representatives.get(row['sample_number'])
        results = (rep or {}).get('results', {}).get('developability') or {}
        dev = results.get('developability')
        if dev is not None:
            # Reuse the registered S-40 computation with exact variant component
            # facts and source weights. Never substitute WT or ESM-IF1 scores.
            fields = ('expressibility', 'tag_exposure', 'ph_stability', 'aggregation', 'solubility')
            components = results.get('steps') or results
            if all(k in components for k in fields):
                weights = None if dev.get('weight_policy')=='S40_EQUAL_INITIAL_PENDING_BACKTEST' else dev['dimension_weights']
                dev = summarize({'dimension_weights': weights},
                                *(components[k] for k in fields), stability_ddg=ddg)
            else:
                dev = None
                missing.append('S40_COMPONENTS_UNAVAILABLE')
        overall = None if dev is None else dev['overall_score']
        if overall is None:
            missing.append('DEVELOPABILITY_OVERALL_UNAVAILABLE')
        else:
            ensure(finite(overall) and 0 <= overall <= 1, 'OUTPUT_INVALID', 'Invalid S40 overall')
        mutated = [m['position'] for m in row['mutations']]
        if any(p not in permissions for p in mutated):
            missing.append('SOFT_CONSTRAINT_MAP_INCOMPLETE')
        soft = epi['soft'] is True or any(permissions.get(p, {}).get('constraint_state') == 'SOFT' for p in mutated)
        deltas = [Decimal(str(charge[m['mut']])) - Decimal(str(charge[m['wt']])) for m in row['mutations']]
        signed = [d for d in deltas if d]
        family = 'charge_tuning' if signed and abs(sum(signed)) >= 1 and (all(d > 0 for d in signed) or all(d < 0 for d in signed)) else 'mixed'
        warnings.append('FAMILY_PARTIAL_CHARGE_ONLY_OTHER_GEOMETRY_CLASSES_UNRESOLVED')
        item = dict(id=row['id'], state='EXCLUDED' if reasons else 'UNDETERMINED' if missing else 'RANKABLE',
                    exclusion_reasons=sorted(set(reasons)), missing=sorted(set(missing)), warnings=warnings,
                    developability=dev, protection=epi, family=family, soft_penalty=soft,
                    recomputation_sources=(rep or {}).get('sources'), scientific_eligible=False)
        inventory.append(item)
        if item['state'] != 'RANKABLE':
            continue
        count = row['burden']['values']['count'] if row['burden'] is not None else 0
        ensure(type(count) is int and count >= 0, 'OUTPUT_INVALID', 'Invalid mutation count')
        stab = stability(ddg)
        norms = [overall, stab, epi['norm'], max(0., 1 - count / COUNTS[objective])]
        score = sum(Decimal(str(w)) * Decimal(str(n)) for w, n in zip(WEIGHTS[objective], norms)) - Decimal('.10') * soft
        computed.append(dict(id=row['id'], family=family, overall=overall, ddg=ddg,
                             pareto=[overall, stab, epi['norm'], -count], norms=norms, score=float(score)))
    front = [r for r in computed if not any(all(a >= b for a, b in zip(u['pareto'], r['pareto']))
             and any(a > b for a, b in zip(u['pareto'], r['pareto'])) for u in computed)]
    ranked = sorted(front, key=lambda r: -r['score'])
    selection = diversity(ranked, {r['id']: r['sequence'] for r in rows})
    best = next((r for r in ranked if selection['ids'] and r['id'] == selection['ids'][0]), None)
    status = 'COMPUTED_PARTIAL_SCOPE' if best else 'ALL_EXCLUDED' if rows and all(r['state'] == 'EXCLUDED' for r in inventory) else 'INPUTS_INCOMPLETE'
    return dict(kind='BACKEND_EVIDENCE_INTERNAL_RANKING', status=status, objective=objective,
                weights=list(WEIGHTS[objective]) if objective in WEIGHTS else None, inventory=inventory, computed=computed,
                pareto_ids=[r['id'] for r in front], ranked_front=[r['id'] for r in ranked],
                diversity=selection, top20=selection['ids'], best_candidate=best['id'] if best else None,
                sc10=dict(overall_threshold=.30, overall_pass=best['overall'] >= .30 if best else None,
                          action='REVIEW_CANDIDATE' if best and best['overall'] >= .30 else
                          'WT_FALLBACK_BELOW_THRESHOLD' if best else 'NO_RANKABLE_CANDIDATE',
                          formal_pass=None, automatic_handoff=False),
                warnings=['S23_OUTSIDE_PHASE1_NOT_EXECUTED',
                          'N13_ALL_VALIDATED_L4_POOL_SELECTION_UNDEFINED' if
                          decode(files.get('input/n13-request.json',b'{}')).get('preselection',{}).get('selection_scope')=='ALL_VALIDATED' else
                          'N13_MAX_3_REPRESENTATIVES_NOT_FULL_POOL' if 'n14_source' in body else 'N13_N14_MAX_3_REPRESENTATIVES_NOT_FULL_POOL',
                          'FAMILY_CLASSIFICATION_PARTIAL', 'TIES_USE_SOURCE_INVENTORY_ORDER_FIRST_VERSION'] +
                         (['ALL_STABILITY_UNKNOWN_CONSTANT_DIMENSION'] if computed and all(r['ddg'] is None for r in computed) else []),
                usable_for_pipeline=False, scientific_release_gate='CLOSED', formal_ranking_changed=False)
