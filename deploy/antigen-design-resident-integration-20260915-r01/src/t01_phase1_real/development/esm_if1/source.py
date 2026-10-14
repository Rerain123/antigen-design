"""Verified N11 generation records, WT source and optional execution-bound baseline."""
from ...common import encode,decode,ensure,sha
from ..proteinmpnn import policy as mpnn
from ..proteinmpnn.source import sources as structure_sources
from ..proteinmpnn.result import parse as parse_mpnn
from . import policy


def registered(rt,db,ref,tool):
    job,raw,value=rt._registered_result_artifact(db,ref,tool)
    ensure(job['state']=='succeeded' and value['qualification']=='DEVELOPMENT_UNREVIEWED'
        and value['scientific_signoff'] is None,'OUTPUT_INVALID','Successful unreviewed engineering source required')
    request_raw=rt._input(db,job['request_artifact'],job['run_id']);request=decode(request_raw)
    ensure(value['binding']['input_sha256']==sha(request_raw) and all(value['binding'][k]==job[k]
        for k in ('request_id','execution_identity','execution_profile','rule_profile')),
        'OUTPUT_INVALID','Source request/execution identity differs')
    files={}
    for item in value['raw_artifacts']:
        ensure(item['path'] not in files and item['artifact'] in job['artifacts'],'OUTPUT_INVALID','Foreign or duplicate source artifact')
        files[item['path']]=rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id'])
    ensure(files['input.json']==request_raw,'OUTPUT_INVALID','Source executed request differs')
    return job,raw,value,request,files


def sources(rt,db,body):
    job,raw,value,n11,native=registered(rt,db,body['n11_artifact'],mpnn.TOOL)
    ensure(n11['protein_sequence']==body['protein_sequence'] and n11['structure_artifact']==body['structure_artifact'],
        'OUTPUT_INVALID','N11 WT sequence/structure differs from N12 request')
    generated=parse_mpnn(n11,native)
    ensure(value['generation']==generated and value['binding']['sequence_sha256']==sha(body['protein_sequence'].encode()),
        'OUTPUT_INVALID','N11 records differ from verified native output')
    prepared,structure_receipt=structure_sources(rt,db,n11)
    ensure(all(native[name]==data for name,data in prepared.items()),'HASH_MISMATCH','N11 structure snapshot differs from current registered source')
    available={r['sample_number']:r for r in generated['records']}
    ensure(all(n in available for n in body['sample_numbers']),'INVALID_REQUEST','Requested N11 sample does not exist')
    records=[available[n] for n in body['sample_numbers']]
    for record in records:
        actual=[dict(position=p,wt_residue=w,mut_residue=m,source='ProteinMPNN')
            for p,(w,m) in enumerate(zip(body['protein_sequence'],record['sequence']),1) if w!=m]
        ensure(record['mutations']==actual,'OUTPUT_INVALID','N11 mutations differ from sequence')
    conversion=generated['conversion'];assets=decode((policy.HERE/'assets.json').read_bytes())
    signature=dict(wt_sequence_sha256=sha(body['protein_sequence'].encode()),
        source_structure_sha256=structure_receipt['source_sha256'],wt_pdb_sha256=sha(prepared['native/target.pdb']),
        conversion_sha256=sha(prepared['native/conversion.json']),mapping_sha256=sha(prepared['input/mapping.json']),
        target_chain=conversion['target_chain'],chain_sequences=conversion['chain_sequences'],
        chain_order=list(dict.fromkeys(r['chain_id'] for r in conversion['rows'])),model=policy.MODEL,commit=policy.COMMIT,image=policy.IMAGE,
        source_manifest_sha256=assets['archive_sha256'],parameters=policy.PARAMETERS,execution_profile=policy.registered_profile())
    files={'input/n11-result.json':raw,'input/n11-request.json':encode(n11),
        'native/wt.pdb':prepared['native/target.pdb'],'native/conversion.json':prepared['native/conversion.json']}
    # All N11 raw artifacts are checked above; retain its executed inputs/outputs used in semantic verification.
    for name,data in native.items():
        if name in ('input.json','input.fasta') or name.startswith(('input/','native/','output/','resident/')):files['input/n11/'+name]=data
    baseline=None;baseline_receipt=None
    if body['baseline_artifact'] is not None:
        bj,braw,bvalue,brequest,bfiles=registered(rt,db,body['baseline_artifact'],policy.TOOL)
        ensure(bj['execution_profile']==policy.registered_profile(),'OUTPUT_INVALID','Baseline execution profile/model has changed')
        from .result import validate_observation
        observation=validate_observation(brequest,bfiles)
        baseline=observation['baseline']
        ensure(baseline is not None and baseline['signature']==signature and bvalue['baseline']==baseline,
            'OUTPUT_INVALID','Baseline WT structure/chain/mapping/model/parameters differ')
        baseline_receipt=dict(artifact=body['baseline_artifact'],baseline_sha256=sha(encode(baseline)),
            original_job_id=baseline['origin_job_id'],reused_from_job_id=bj['job_id'])
        files['input/baseline-result.json']=braw
        files['input/baseline-observation.json']=bfiles['output/observation.json']
    payload=dict(protein_sequence=body['protein_sequence'],records=records,baseline=baseline,signature=signature,
        parameters=policy.PARAMETERS,source_n11=body['n11_artifact'],target_chain=conversion['target_chain'])
    files['native/payload.json']=encode(payload)
    receipt=dict(n11_artifact=body['n11_artifact'],n11_request=job['request_artifact'],
        n11_profile=job['execution_profile'],n11_raw_artifacts=value['raw_artifacts'],structure=structure_receipt,
        baseline=baseline_receipt,signature=signature,selected_sample_numbers=body['sample_numbers'],
        prepared_hashes={n:sha(v) for n,v in files.items()})
    return files,receipt
