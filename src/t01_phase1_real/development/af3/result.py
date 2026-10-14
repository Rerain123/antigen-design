from ...common import RuntimeFault, decode, encode, ensure, sha
from ...resident_result import image_matches, isolation_matches
from . import policy
from .standard import normalize


LEGACY_SOURCE_SHA256='f0eab0ed566f1c2fa9435166d9bf7c86c345f8a81e2606a12b1d79be8c9e4439'
PRE_MSA_SOURCE_SHA256='51945e4890998bbdd9e07408ab0ec3c478dada30587b478ff9505471ea8a8ab2'
PRE_ADDRESS_SOURCE_SHA256='8953e089ea9b33f005375a10b45875b9b3f89fd02caa5f5913f0862c57c9b764'
PRE_ADDRESS_PROFILE_SHA256='504519017252584af7d8764ae55f27c35e70ba65bfd90ef4433a2194d26f836a'


def verify_source_identity(job,body,runtime,*,historical_source=False):
    current={p.name:sha(p.read_bytes()) for p in sorted(policy.HERE.iterdir()) if p.suffix in ('.py','.json')}
    recorded=runtime['source_sha256']
    if recorded==current:return True
    # Replay only the exact archived 76-aa profile, never admit new work with it.
    digest=sha(encode(recorded))
    if (historical_source and digest==PRE_ADDRESS_SOURCE_SHA256
        and job['execution_profile']==dict(id='af3-v3.0.2-resident-r01',version='0.1.0',sha256=PRE_ADDRESS_PROFILE_SHA256)):
        return False
    ensure(historical_source and 'mode' not in body and 'msa_source' not in body
        and ((len(body['protein_sequence'])<=76 and digest==LEGACY_SOURCE_SHA256)
             or (len(body['protein_sequence'])<=999 and digest==PRE_MSA_SOURCE_SHA256))
        and job['execution_profile']==dict(id='af3-v3.0.2-resident-r01',version='0.1.0',sha256=digest),
        'OUTPUT_INVALID','AF3 worker source changed')
    return False


def result(job,body,files,execution,fault=None,*,historical_source=False):
    binding={key:job[key] for key in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,execution=execution,
        qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',scientific_signoff=None,
        production_status='NOT_DEPLOYED',usable_for_pipeline=False,automatic_handoff=False,requires_review=True,
        scientific_gate='CLOSED',status='unreliable',null_reason=execution.get('error_code'),warnings=[],prediction=None)
    try:
        if execution.get('error_code'):raise RuntimeFault(execution['error_code'],'AF3 execution did not finish')
        ensure(execution.get('backend')=='resident-process' and image_matches(execution,policy.IMAGE),
               'OUTPUT_INVALID','Clean registered resident AF3 execution required')
        runtime=decode(files['output/runtime.json'])
        ensure(runtime['binding']==binding and runtime['input_sha256']==sha(files['input.json'])
               and runtime['python_exit_code']==0 and runtime['socket_probe']=='INET_INET6_DENIED'
               and isolation_matches(runtime,files,policy.IMAGE),'OUTPUT_INVALID','AF3 execution isolation differs')
        current_source=verify_source_identity(job,body,runtime,historical_source=historical_source)
        native={name[len('output/raw/'):]:raw for name,raw in files.items() if name.startswith('output/raw/')}
        prepared=decode(files['msa-source.json']) if 'msa_source' in body else None
        standard=normalize(native,body,binding,prepared,canonical_addresses=current_source)
        ensure(all(files['output/'+name]==raw for name,raw in standard.items()),
               'OUTPUT_INVALID','AF3 standard result differs from native output')
        if body.get('mode')=='msa_only':
            value.update(status='msa_prepared_engineering_unreviewed',null_reason=None,msa=decode(standard['msa.json']))
        else:
            value.update(status='predicted_engineering_unreviewed',null_reason=None,prediction=decode(standard['result.json']))
    except (RuntimeFault,KeyError,ValueError,TypeError,OSError) as exc:
        value['null_reason']=getattr(exc,'code','OUTPUT_INVALID')
        execution.update(error_code=value['null_reason'],diagnostic=str(exc));value['warnings']=[str(exc)]
    return value
