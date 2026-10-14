"""Same-scope registered local structure facts; no inferred scientific qualification."""
from ...common import decode, ensure, sha
from .mapping import project


def sources(rt,db,body,expected_run_id=None,*,pdb_format_projection=False):
    ref=body['structure_artifact'];job,raw,source=rt._registered_result_artifact(db,ref,'t01.real.ingest_structure')
    if expected_run_id is not None:
        ensure(ref['run_id']==expected_run_id and job['run_id']==expected_run_id,
            'FORBIDDEN','N11 structure source belongs to another run')
    ensure(job['state']=='succeeded' and ref['role']=='result','OUTPUT_INVALID','N11 requires a successful structure task')
    request_raw=rt._input(db,job['request_artifact'],job['run_id']);request=decode(request_raw)
    ensure(request['protein_sequence']==body['protein_sequence'] and source['binding']['sequence_sha256']==sha(body['protein_sequence'].encode())
        and source['binding']['input_sha256']==sha(request_raw) and source['binding']['execution_profile']==job['execution_profile'],
        'OUTPUT_INVALID','N11 upstream sequence/request/profile binding differs')
    ensure(source['qualification']=='DEVELOPMENT_UNREVIEWED' and source['scientific_signoff'] is None,
        'OUTPUT_INVALID','N11 source qualification is not registered')
    indexed={}
    for item in source['raw_artifacts']:
        ensure(item['path'] not in indexed and item['artifact'] in job['artifacts'],
            'OUTPUT_INVALID','N11 source raw inventory is ambiguous or foreign')
        indexed[item['path']]=item['artifact']
    def read(name):
        ensure(name in indexed,'OUTPUT_INVALID','Required structure source fact missing: '+name)
        return rt.artifact_bytes(job['job_id'],indexed[name]['artifact_id'])
    original=read('input.structure')
    ensure(sha(original)==source['binding']['structure_sha256'],'HASH_MISMATCH','Original structure hash differs')
    facts={};files={'input/structure-result.json':raw,'input/structure-request.json':request_raw,'input/structure-original.bin':original}
    for name in ('preflight','raw_metadata','raw_addresses'):
        data=read('output/result/'+name+'.json');facts[name]=decode(data)
        ensure(facts[name]['binding']==source['binding'],'OUTPUT_INVALID','Structure fact binding differs')
        files['input/'+name+'.json']=data
    mapping_raw=read('output/result/mapping.json')
    ensure(decode(mapping_raw)==source['analysis']['mapping'],'OUTPUT_INVALID','Structure mapping result differs')
    files['input/mapping.json']=mapping_raw
    files.update(project(body,source,original,facts,pdb_format_projection=pdb_format_projection))
    receipt=dict(artifact=ref,request_artifact=job['request_artifact'],source_sha256=sha(original),
        verified_fact_artifacts={name:indexed[name] for name in ('input.structure','output/result/preflight.json',
            'output/result/raw_metadata.json','output/result/raw_addresses.json','output/result/mapping.json')},
        qualification=source['qualification'],scientific_signoff=None,source_profile=job['execution_profile'],
        prepared_hashes={name:sha(data) for name,data in files.items()})
    return files,receipt
