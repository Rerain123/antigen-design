from ...common import RuntimeFault, decode, encode, ensure, sha
from ...resident_result import image_matches, isolation_matches
from . import policy
from .standard import normalize, NAMES


def result(job, body, files, execution, fault=None):
    binding = {k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'], sequence_sha256=sha(body['protein_sequence'].encode()))
    value = dict(contract_version='0.1.0', tool_id=policy.TOOL, binding=binding, execution=execution,
        qualification='DEVELOPMENT_UNREVIEWED', evidence_kind='G0_REAL_OUTPUT', scientific_signoff=None,
        production_status='NOT_DEPLOYED', usable_for_pipeline=False, automatic_handoff=False, requires_review=True,
        scientific_gate='CLOSED', status='unreliable', null_reason=execution.get('error_code'), warnings=[], prediction=None)
    try:
        if execution.get('error_code'): raise RuntimeFault(execution['error_code'], 'Prediction execution did not finish')
        ensure(execution.get('backend') == 'resident-process' and image_matches(execution, policy.IMAGE),
               'OUTPUT_INVALID', 'Clean registered resident prediction required')
        runtime = decode(files['output/runtime.json'])
        ensure(runtime['binding'] == binding and runtime['input_sha256'] == sha(files['input.json'])
               and runtime['python_exit_code'] == 0 and runtime['socket_probe'] == 'INET_INET6_DENIED'
               and isolation_matches(runtime, files, policy.IMAGE), 'OUTPUT_INVALID', 'Prediction execution binding/isolation differs')
        ensure(runtime['source_sha256'] == {p.name:sha(p.read_bytes()) for p in sorted(policy.HERE.iterdir())
               if p.suffix in ('.py','.json')}, 'OUTPUT_INVALID', 'Prediction worker source changed')
        native = {n:files['output/raw/'+n] for n in NAMES | {'manifest.json'}}
        standard = normalize(native, body, binding)
        ensure(all(files['output/'+n] == raw for n,raw in standard.items()), 'OUTPUT_INVALID', 'Standard result differs from native output')
        value.update(status='predicted_engineering_unreviewed', null_reason=None, prediction=decode(standard['result.json']))
    except (RuntimeFault, KeyError, ValueError, TypeError, OSError) as exc:
        value['null_reason'] = getattr(exc,'code','OUTPUT_INVALID')
        execution.update(error_code=value['null_reason'], diagnostic=str(exc))
        value['warnings'] = [str(exc)]
    return value
