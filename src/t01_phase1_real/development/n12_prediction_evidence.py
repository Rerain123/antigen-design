"""Read-only N12 sample/prediction linkage. No R-04 routing or candidate admission."""
from ..common import encode, ensure, sha
from .esm_if1 import policy
from .esm_if1.source import registered, sources
from .esm_if1.result import result as rebuild


def verified_prediction(rt,db,job_id,sequence,host,run_id,include_quality=False):
    producer=rt._job(db,job_id)['tool_id']
    ensure(producer in ('t01.real.esmfold2','t01.real.af3'),'FORBIDDEN','Unknown native structure predictor')
    from .workflow.service import prediction_source
    return prediction_source(producer.rsplit('.',1)[1]).verified(rt,db,job_id,sequence,host,run_id,include_quality=include_quality)


def inspect(rt, db, scoring_artifact, sample_number, prediction_job_id, host_species):
    policy.artifact(scoring_artifact)
    ensure(type(sample_number) is int and 1 <= sample_number <= 64,
           'INVALID_REQUEST', 'Original N11 sample number required')
    job, _, value, body, files = registered(rt, db, scoring_artifact, policy.TOOL)
    policy.request(encode(body))
    # Revalidate upstream generation and exact WT backbone; never relabel a
    # free-standing sequence or imported prediction as a scored candidate.
    prepared, _ = sources(rt, db, body, expected_run_id=job['run_id'])
    ensure(all(files.get(name) == raw for name, raw in prepared.items()),
           'OUTPUT_INVALID', 'Scoring inputs differ from verified upstream')
    fresh = rebuild(job, body, files, dict(value['execution']))
    ensure(fresh['scoring'] is not None and all(fresh[k] == value[k]
           for k in ('binding', 'scoring', 'baseline', 'engineering_rules')),
           'OUTPUT_INVALID', 'N12 result differs from independently rebuilt scoring')
    ensure(value['usable_for_pipeline'] is False and value['automatic_handoff'] is False,
           'OUTPUT_INVALID', 'Expected unqualified engineering source')
    rows = [r for r in fresh['scoring']['records'] if r['sample_number'] == sample_number]
    ensure(len(rows) == 1 and sample_number in body['sample_numbers'],
           'INVALID_REQUEST', 'Sample was not scored in this N12 task')
    row = rows[0]
    ensure(row['score'] is not None, 'OUTPUT_INVALID', 'Selected sample scoring failed')
    prediction = verified_prediction(rt, db, prediction_job_id, row['sequence'],
                                     host_species, job['run_id'], include_quality=True)
    rules = [r for r in fresh['engineering_rules']['records'] if r['sample_number'] == sample_number]
    ensure(len(rules) == 1, 'OUTPUT_INVALID', 'R-35 sample evidence missing')
    return dict(status='PREDICTION_LINKED_ENGINEERING_ONLY', sample_number=sample_number,
        scoring_artifact=scoring_artifact, n11_artifact=body['n11_artifact'],
        wt_structure_artifact=body['structure_artifact'],
        sequence_sha256=sha(row['sequence'].encode()), mutations=row['mutations'],
        r35_original=rules[0], r35_threshold=fresh['engineering_rules']['threshold'],
        prediction=prediction, engine_selection='EXPLICIT_ENGINEERING_ONLY_NOT_R04',
        validation=None, formal_candidates=None, scientific_gate='CLOSED',
        usable_for_pipeline=False, automatic_handoff=False,
        limitations=['No R-04 automatic routing or complete S-28 decision.',
                    'Original R-35 exclusions remain unchanged.',
                    'No WT low-confidence mutation downgrade or scientific signoff computed.'])
