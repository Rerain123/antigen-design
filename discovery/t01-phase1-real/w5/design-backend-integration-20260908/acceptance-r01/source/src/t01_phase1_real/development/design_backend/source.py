"""Registered historical source bytes with live hash checks; no scientific promotion."""
from ...common import TERMINAL,decode,encode,ensure,sha
from ...files import read_verified
from . import policy

def sources(rt,db,body):
    files={};values={};receipts={}
    for name,tool in policy.PRODUCERS.items():
        source=body['upstream'][name]
        if source is None:
            receipts[name]=dict(state='missing',verified=False,artifact=None,attempt_id=None)
            continue
        job=rt._job(db,source['job_id'])
        ensure(job['tool_id']==tool and job['run_mode']=='g0_probe' and job['usable_for_pipeline'] is False
            and job['evidence_kind']=='G0_REAL_OUTPUT','FORBIDDEN','Design source tool/scope/qualification differs')
        request_raw=rt._input(db,job['request_artifact'],job['run_id']);up_request=decode(request_raw)
        ensure(isinstance(up_request,dict) and up_request.get('protein_sequence')==body['protein_sequence'],
            'OUTPUT_INVALID','Design upstream request sequence differs')
        if up_request.get('host_species') is not None and body.get('host_species') is not None:
            ensure(up_request['host_species']==body.get('host_species'),'OUTPUT_INVALID','Design upstream host fact differs')
        files['input/'+name+'-request.json']=request_raw
        refs=[r for r in job['artifacts'] if r['role'] in ('result','diagnostic')]
        ensure(len(refs)<=1 and source['artifact']==(refs[0] if refs else None),
            'FORBIDDEN','Design source must name the exact published result or diagnostic')
        value=None;verified_artifacts=[]
        if refs:
            _,raw,value=rt._registered_result_artifact(db,refs[0],tool)
            binding=value['binding']
            ensure(all(binding.get(k)==job[k] for k in ('request_id','execution_identity','execution_profile'))
                and binding.get('input_sha256')==sha(request_raw)
                and binding.get('sequence_sha256')==sha(body['protein_sequence'].encode()),
                'OUTPUT_INVALID','Design upstream binding/request/profile differs')
            ensure(value.get('qualification')=='DEVELOPMENT_UNREVIEWED' and value.get('scientific_signoff') is None
                and value.get('evidence_kind')=='G0_REAL_OUTPUT' and value.get('production_status')=='NOT_DEPLOYED',
                'OUTPUT_INVALID','Design upstream scientific qualification is not registered')
            ensure(refs[0]['role']==('result' if job['state']=='succeeded' else 'diagnostic')
                and value.get('execution',{}).get('error_code')==job['error_code'],
                'OUTPUT_INVALID','Design upstream failure state differs')
            # Verify published raw evidence too; a valid result hash cannot hide damaged tool files.
            raw_refs=value.get('raw_artifacts')
            ensure(isinstance(raw_refs,list),'OUTPUT_INVALID','Upstream raw artifact manifest missing')
            for item in raw_refs:
                ensure(isinstance(item,dict) and isinstance(item.get('artifact'),dict)
                    and item['artifact'] in job['artifacts'] and item['artifact']['role'] in ('raw','log'),
                    'OUTPUT_INVALID','Design raw provenance references a foreign artifact')
            for ref in job['artifacts']:
                row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
                ensure(row and decode(row['data'])==ref,'FORBIDDEN','Design upstream publication registry differs')
                read_verified(rt.root,row['relative_path'],ref['sha256'],ref['size_bytes'],32*1024**2)
                verified_artifacts.append(ref)
            files['input/'+name+'-result.json']=raw
        ensure(job['state']!='succeeded' or value is not None,'OUTPUT_INVALID','Successful upstream has no result')
        state='available' if job['state']=='succeeded' else 'failed' if job['state'] in TERMINAL else 'pending'
        if state=='available':values[name]=value
        receipts[name]=dict(state=state,verified=True,artifact=source['artifact'],job_id=job['job_id'],
            run_id=job['run_id'],attempt_id=job['attempt_id'],job_state=job['state'],revision=job['revision'],
            error_code=job['error_code'],request_artifact=job['request_artifact'],
            sequence_sha256=sha(body['protein_sequence'].encode()),qualification=job['scientific_disposition'],
            result_status=value.get('status') if value else None,execution_profile=job['execution_profile'],
            rule_profile=job['rule_profile'],verified_artifacts=verified_artifacts)
    enrich(rt,db,body,files,values,receipts)
    files['input/source-receipts.json']=encode(receipts)
    return files,values,receipts


def enrich(rt,db,body,files,values,receipts):
    def originals(name):
        value=values[name];job=rt._job(db,body['upstream'][name]['job_id']);result={}
        for item in value['raw_artifacts']:
            ensure(item['path'] not in result and item['artifact'] in job['artifacts'],'OUTPUT_INVALID','Duplicate/foreign raw source path')
            result[item['path']]=rt.artifact_bytes(job['job_id'],item['artifact']['artifact_id'])
        return result
    if 'structure' in values:
        raw=originals('structure');source=values['structure']
        ensure(sha(raw['input.structure'])==source['binding']['structure_sha256'],'HASH_MISMATCH','Original WT structure differs')
        files['input/structure-original.bin']=raw['input.structure']
        for name in ('preflight','raw_metadata','raw_addresses','mapping'):
            files['input/'+name+'.json']=raw['output/result/'+name+'.json']
        ensure(decode(files['input/mapping.json'])==source['analysis']['mapping'],'OUTPUT_INVALID','WT mapping snapshot differs')
    if 'n11' in values:
        from ..proteinmpnn.result import parse
        native=originals('n11');request=decode(files['input/n11-request.json']);value=values['n11']
        generated=parse(request,native)
        ensure(value['generation']==generated,'OUTPUT_INVALID','N11 generated records differ from native source')
        explicit=body['upstream']['structure']
        ensure(explicit is not None and request['structure_artifact']==explicit['artifact'] and 'structure' in values,
            'OUTPUT_INVALID','N11 and burden must bind the same successful WT structure')
        ensure(native['input/structure-original.bin']==files['input/structure-original.bin']
            and native['input/mapping.json']==files['input/mapping.json'],'HASH_MISMATCH','N11 WT structure snapshot differs')
        available={r['sample_number'] for r in generated['records']}
        ensure(set(body['sample_numbers'])<=available,'INVALID_REQUEST','Selected N11 record absent')
        for name,data in native.items():
            if name.startswith(('input/','native/','output/')) or name in ('input.json','input.fasta'):
                files['input/n11-native/'+name]=data
    if 'esm_if1' in values:
        ensure('n11' in values,'OUTPUT_INVALID','N12 scoring requires the original successful N11 source')
        native=originals('esm_if1');request=decode(files['input/esm_if1-request.json']);value=values['esm_if1']
        ensure(request['n11_artifact']==body['upstream']['n11']['artifact'] and request['structure_artifact']==body['upstream']['structure']['artifact'],
            'OUTPUT_INVALID','N12 scoring belongs to a different N11 or WT structure')
        observation=decode(native['output/observation.json'])
        ensure(observation==value['scoring'] and value['baseline']==observation['baseline'],'OUTPUT_INVALID','Published N12 scoring differs from original observation')
        # Historical execution profile stays historical. Verify source-native measurements,
        # signature and model identities without rewriting profiles or rerunning ESM-IF1.
        from ..esm_if1.result import measurement
        from ..esm_if1.rules import evaluate as r35
        from ..esm_if1 import policy as esm
        signature=observation['signature'];runtime=decode(native['output/runtime.json'])
        ensure(signature['execution_profile']==receipts['esm_if1']['execution_profile'] and signature['model']==esm.MODEL
            and signature['image']==esm.IMAGE and signature['parameters']==esm.PARAMETERS
            and signature['wt_sequence_sha256']==sha(body['protein_sequence'].encode())
            and signature['source_structure_sha256']==sha(files['input/structure-original.bin'])
            and signature['mapping_sha256']==sha(files['input/mapping.json']),
            'OUTPUT_INVALID','Historical N12 source signature differs')
        ensure(runtime['native_output_sha256']=={n[7:]:sha(data) for n,data in native.items() if n.startswith('output/') and n!='output/runtime.json'},
            'OUTPUT_INVALID','Historical N12 native output hashes differ')
        baseline=observation['baseline']
        if baseline:
            measurement(baseline,body['protein_sequence'])
            ensure(value['engineering_rules']==r35(baseline['score'],observation['records']),'OUTPUT_INVALID','Recorded R35 rules differ')
        by_number={r['sample_number']:r for r in values['n11']['generation']['records']}
        for row in observation['records']:
            original=by_number[row['sample_number']]
            ensure(all(row[k]==original[k] for k in ('sequence','mutations')),'OUTPUT_INVALID','N12/N11 variant diff mismatch')
            if row['score'] is not None:ensure(measurement(row['measurement'],row['sequence'])==row['score'],'OUTPUT_INVALID','Historical N12 loss mean differs')
        for name in ('output/observation.json','output/runtime.json'):
            files['input/n12-native/'+name]=native[name]
    scales=decode((policy.HERE/'scales.json').read_bytes())
    for receipt in scales['source_receipts'].values():
        from ...common import REPO
        raw=read_verified(REPO,receipt['path'],receipt['sha256'],receipt['bytes'],4*1024**2)
    files['input/scales.json']=encode(scales)

