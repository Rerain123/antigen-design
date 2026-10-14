"""Validate complete execution-bound chain outputs before publishing a development result."""
import copy

from ...common import decode, encode, ensure, sha, RuntimeFault
from .policy import PROFILE, IMAGE
from .normalization import normalize
from ...resident_result import image_matches, isolation_matches


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),structure_sha256=body['structure_artifact']['sha256'])
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='LOCAL_STRUCTURE_ANALYSIS',evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',binding=binding,execution=execution,controlled_fault=fault,analysis=None,
        host_species=body['host_species'],usable_for_pipeline=False,automatic_handoff=False,requires_review=True,
        scientific_signoff=None,production_status='NOT_DEPLOYED',status='unreliable',null_reason=execution.get('error_code'),warnings=[])
    try:
        if execution.get('error_code'):raise RuntimeFault(execution['error_code'],execution.get('diagnostic') or 'Execution did not finish')
        runtime=decode(files['output/runtime.json'])
        if execution.get('backend')=='kubernetes':
            from ...deployment.target_result import validate_structure_execution
            validate_structure_execution(job,execution,runtime)
        else:
            ensure(execution.get('stopped_confirmed') is True and type(execution.get('exit_code')) is int and execution['exit_code']==0
                and not execution.get('oom_killed') and image_matches(execution,IMAGE),'OUTPUT_INVALID','No clean pinned stopped execution')
            ensure(runtime['python_exit_code']==0 and isolation_matches(runtime,files,IMAGE,[0,1]),
                'OUTPUT_INVALID','Runtime/isolation mismatch')
        ensure(sha(files['input.structure'])==binding['structure_sha256'] and decode(files['binding.json'])==binding,'OUTPUT_INVALID','Executed input/binding differs')
        profile=decode(PROFILE.read_bytes())
        ensure(all(v==profile['runtime'][k] for k,v in runtime['packages'].items()) and set(runtime['packages'])=={'python','freesasa','biopython','numpy'},
            'OUTPUT_INVALID','Pinned package versions differ')
        inventory=runtime['native_output_sha256']
        ensure(inventory and set(inventory)=={p[len('output/'):] for p in files if p.startswith('output/result/')},'OUTPUT_INVALID','Output inventory differs')
        ensure(all(sha(files['output/'+p])==h for p,h in inventory.items()),'OUTPUT_INVALID','Native output hash mismatch')
        report=decode(files['output/result/analysis.json'])
        if fault=='corrupt_output':
            report=copy.deepcopy(report);report['binding']['structure_sha256']='0'*64
            files['fault/invalid-analysis.json']=encode(report)
        ensure(report['binding']==binding and report['input']['structure_artifact']==body['structure_artifact']
            and report['input']['protein_sequence']==body['protein_sequence'] and report['input']['host_species']==body['host_species']
            and report['input']['source_declaration']==body['source_declaration'],'OUTPUT_INVALID','Result input identity changed')
        ensure(report['usable_for_pipeline'] is False and report['automatic_handoff'] is False and report['scientific_signoff'] is None,'OUTPUT_INVALID','Unapproved result promoted')
        for name in ['preflight','raw_metadata','raw_addresses']:
            fact=decode(files['output/result/'+name+'.json'])
            ensure(fact['binding']==binding and fact['structure_sha256']==binding['structure_sha256'],'OUTPUT_INVALID','Fact artifact binding mismatch')
        for name in ['mapping','quality','rsa']:
            if report[name] is not None:
                separate=decode(files['output/result/'+name+'.json'])
                ensure(separate.pop('binding')==binding,'OUTPUT_INVALID','Step artifact binding differs: '+name)
                embedded=copy.deepcopy(report[name]);embedded.pop('binding',None)
                ensure(separate==embedded,'OUTPUT_INVALID','Embedded step differs from artifact: '+name)
        if report['mapping'] is not None:
            mapping=report['mapping']
            ensure(mapping['binding']==binding and mapping['usable_for_pipeline'] is False and mapping['mapping_status'] in ('unverified','unreliable')
                and mapping['sequence']==body['protein_sequence'] and mapping['structure_sha256']==binding['structure_sha256'],
                'OUTPUT_INVALID','Mapping identity or approval changed')
            ensure([e['sequence_position'] for e in mapping['entries']]==list(range(1,len(body['protein_sequence'])+1)),'OUTPUT_INVALID','Mapping positions incomplete')
        if report['freesasa']['status']=='executed':
            ensure(report['quality']['s11_quality_condition'] is True and report['mapping']['target_chain_id'] is not None,'OUTPUT_INVALID','Calculation bypassed quality/mapping guard')
            for name in ['preparation','classifier','tool_atoms','verified_atoms','raw_areas','raw_residue_areas','rsa','calculation-started']:
                ensure('output/result/'+name+'.json' in files,'OUTPUT_INVALID','Missing computed-step artifact: '+name)
            rsa=report['rsa']
            ensure(len(rsa['aligned_absolute_sasa_a2'])==len(rsa['raw_normalized_ratios'])==len(body['protein_sequence'])
                and rsa['normal_rsa_result'] is None and not rsa['usable_for_pipeline'],'OUTPUT_INVALID','RSA length or qualification changed')
            ensure(not rsa['out_of_domain'] or rsa['development_result'] is None and rsa['error_code']=='OUTPUT_INVALID','OUTPUT_INVALID','Out-of-domain RSA became a normal result')
            expected=normalize(report['mapping'],decode(files['output/result/raw_addresses.json'])['residues'],
                decode(files['output/result/raw_residue_areas.json'])['residues'],profile['normalization']['max_asa_a2'])
            ensure(rsa==expected,'OUTPUT_INVALID','RSA identity join or normalization differs from raw areas')
        value.update(analysis=report,status='review_required',null_reason=None,warnings=report['warnings'])
        if report.get('status')=='input_rejected':
            value['status']='input_rejected'
            execution.update(error_code='INVALID_REQUEST',input_error_code=report['error_code'],diagnostic='Input preflight rejected; raw facts retained: '+report['error_code'])
    except (RuntimeFault,KeyError,ValueError,TypeError,OSError) as exc:
        error=execution.get('error_code') or ('PROFILE_NOT_APPROVED' if getattr(exc,'code',None)=='PROFILE_NOT_APPROVED' else 'OUTPUT_INVALID')
        execution.update(error_code=error,diagnostic=str(exc));value.update(analysis=None,status='unreliable',null_reason=error,
            warnings=[dict(code=error,level='failure',severity='WARNING',message=str(exc))])
    return value
