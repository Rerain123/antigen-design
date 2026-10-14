"""Resolve predicted structures without relabelling outputs as user uploads."""
from ...common import decode, encode, ensure, sha
from ...files import read_verified
from . import policy
from .result import result as rebuild


def verified(rt, db, job_id, sequence, host, run_id, include_quality=False):
    job = rt._job(db, job_id)
    ensure(job['run_id'] == run_id and job['tool_id'] == policy.TOOL and job['state'] == 'succeeded',
           'FORBIDDEN', 'Prediction must be a successful task in the current run')
    ref = next((r for r in job['artifacts'] if r['role'] == 'result'), None)
    ensure(ref is not None, 'OUTPUT_INVALID', 'Prediction result missing')
    _, _, value = rt._registered_result_artifact(db, ref, policy.TOOL)
    body = policy.request(rt._input(db, job['request_artifact'], run_id))
    ensure(body['protein_sequence'] == sequence and body['host_species'] == host,
           'OUTPUT_INVALID', 'Prediction sequence or host differs')
    files = {}; refs = {}
    for item in value['raw_artifacts']:
        name, ref = item['path'], item['artifact']
        row = db.execute('SELECT relative_path,data FROM artifacts WHERE id=?', (ref['artifact_id'],)).fetchone()
        ensure(name not in files and ref in job['artifacts'] and row and decode(row['data']) == ref,
               'FORBIDDEN', 'Prediction output registration differs')
        files[name] = read_verified(rt.root, row['relative_path'], ref['sha256'], ref['size_bytes'], 32*1024**2)
        refs[name] = ref
    fresh = rebuild(job, body, files, dict(value['execution']))
    ensure(fresh['prediction'] is not None and fresh['prediction'] == value['prediction']
           and fresh['binding'] == value['binding'] and value['qualification'] == 'DEVELOPMENT_UNREVIEWED'
           and value['scientific_signoff'] is None, 'OUTPUT_INVALID', 'Prediction source validation failed')
    if include_quality:
        return dict(prediction_job_id=job_id, prediction_attempt_id=job['attempt_id'],
            structure_artifact=refs['output/tool-structure.cif'],
            native_structure_artifact=refs['output/raw/structure.cif'],
            quality_artifact=refs['output/prediction-quality.json'],
            quality=decode(files['output/prediction-quality.json']),
            conversion=decode(files['output/structure-conversion.json']))
    return refs['output/tool-structure.cif'], files['output/tool-structure.cif']


def structure_bytes(rt, db, body, run_id):
    ref = body['structure_artifact']
    expected, raw = verified(rt, db, ref['job_id'], body['protein_sequence'], body['host_species'], run_id)
    ensure(ref == expected and body['source_declaration']['kind'] == 'predicted'
           and body['declared_format'] == 'MMCIF' and body['selection'] == {'model_index':0,'chain_selector':'A'}
           and body['context_chain_ids'] == ['A'], 'FORBIDDEN', 'Predicted structure identity/selection differs')
    return raw
