"""Native loss/coordinate/call-count validation and separate R-35 engineering rules."""
import math
import numpy as np
from ...common import RuntimeFault,encode,decode,ensure,sha
from . import policy
from .rules import evaluate


def measurement(row,sequence):
    ensure(isinstance(row,dict) and row['sequence_sha256']==sha(sequence.encode()) and row['residue_count']==len(sequence),
        'OUTPUT_INVALID','Score sequence identity/length differs')
    losses=np.asarray(row['per_residue_nll']);mask=row['target_padding_mask']
    ensure(losses.shape==(len(sequence),) and np.isfinite(losses).all() and (losses>=0).all()
        and mask==[False]*len(sequence),'OUTPUT_INVALID','Incomplete or nonfinite native residue losses')
    score=row['score'];ensure(type(score) in (float,int) and math.isfinite(score) and score<=0
        and abs(-float(losses.mean())-score)<=1e-6,'OUTPUT_INVALID','Signed native score differs from full-target mean loss')
    return score


def validate_observation(body,files):
    runtime=decode(files['output/runtime.json']);payload=decode(files['native/payload.json'])
    assets=decode((policy.HERE/'assets.json').read_bytes());value=decode(files['output/observation.json'])
    ensure(runtime['python_exit_code']==0 and runtime['official_source_modified'] is False and runtime['network_interfaces']==[[1,'lo']]
        and runtime['cpu_affinity']==[0,1] and runtime['gpu_available'] is True,'OUTPUT_INVALID','No clean offline GPU scoring execution')
    ensure(all(runtime[k]==assets['environment'][k] for k in ('python','torch','numpy','cuda','scipy','biotite','torch_geometric')),
        'OUTPUT_INVALID','Native environment differs from fixed ESM-IF1 profile')
    ensure(runtime['parameters']==policy.PARAMETERS and runtime['source_sha256']=={r['package_path']:r['sha256'] for r in assets['files']},
        'OUTPUT_INVALID','Executed ESM-IF1 code/weight/parameters differ')
    ensure(runtime['input_sha256']==sha(files['input.json']) and runtime['input_fasta_sha256']==sha(files['input.fasta'])
        and decode(files['input.json'])==body,'OUTPUT_INVALID','Executed request identity differs')
    ensure(runtime['native_input_sha256']=={n[7:]:sha(v) for n,v in files.items() if n.startswith('native/')},
        'OUTPUT_INVALID','Native source input hash differs')
    ensure(runtime['native_output_sha256']=={n[7:]:sha(v) for n,v in files.items() if n.startswith('output/') and n!='output/runtime.json'},
        'OUTPUT_INVALID','Native scoring output inventory differs')
    conversion=decode(files['native/conversion.json']);parsed=decode(files['output/parsed-coordinates.json'])
    ensure(parsed['sequences']==conversion['chain_sequences'] and parsed['target_chain']==conversion['target_chain']
        and parsed['atom_order']==['N','CA','C'] and parsed['chain_order']==list(dict.fromkeys(r['chain_id'] for r in conversion['rows'])),
        'OUTPUT_INVALID','Official ESM-IF1 chain/sequence parsing differs')
    expected={c:{a:[] for a in ('N','CA','C')} for c in parsed['chain_order']}
    for line in files['native/wt.pdb'].decode().splitlines():
        if line.startswith('ATOM') and line[12:16].strip() in ('N','CA','C'):
            expected[line[21]][line[12:16].strip()].append([float(line[k:k+8]) for k in (30,38,46)])
    for chain in expected:
        coordinates=np.stack([expected[chain][atom] for atom in ('N','CA','C')],axis=1).astype(np.float32)
        ensure(np.array_equal(coordinates,np.array(parsed['coordinates'][chain],dtype=np.float32)),
            'OUTPUT_INVALID','ESM-IF1 coordinates differ from verified WT backbone')
    signature=payload['signature']
    ensure(value['signature']==signature and signature['wt_sequence_sha256']==sha(body['protein_sequence'].encode())
        and signature['wt_pdb_sha256']==sha(files['native/wt.pdb']) and signature['conversion_sha256']==sha(files['native/conversion.json'])
        and signature['target_chain']==conversion['target_chain'] and signature['chain_sequences']==conversion['chain_sequences']
        and signature['model']==policy.MODEL and signature['image']==policy.IMAGE and signature['parameters']==policy.PARAMETERS
        and signature['execution_profile']==policy.registered_profile(),'OUTPUT_INVALID','WT baseline signature differs')
    ensure(value['native_api']=='esm.inverse_folding.util.get_sequence_loss' and value['score_mean_scope']=='all_target_chain_residues'
        and value['backbone_context']=='all_protein_chains_target_first_padding10' and value['structure_prediction_executed'] is False,
        'OUTPUT_INVALID','Scoring semantics/structure execution changed')
    ensure([r['sample_number'] for r in payload['records']]==body['sample_numbers']
        and len(value['records'])==len(payload['records']),'OUTPUT_INVALID','Selected N11 record count/order differs')
    if not body['sample_numbers']:
        ensure(value['baseline'] is None and value['baseline_status']=='not_needed_empty_input' and runtime['model_loaded'] is False
            and runtime['baseline_model_calls']==runtime['variant_model_calls']==0,'OUTPUT_INVALID','Empty selection must not run model')
        return value
    baseline=value['baseline'];measurement(baseline,body['protein_sequence'])
    ensure(baseline['score']<0 and baseline['signature']==signature and isinstance(baseline['origin_job_id'],str),
        'OUTPUT_INVALID','WT baseline is zero/nonnegative or has a different identity')
    reused=payload['baseline'] is not None
    ensure(runtime['model_loaded'] is True and runtime['model_training'] is False and runtime['baseline_reused']==reused
        and runtime['baseline_model_calls']==(0 if reused else 1)
        and value['baseline_status']==('verified_reuse' if reused else 'computed_once'),
        'OUTPUT_INVALID','WT baseline call count/reuse differs')
    if reused:ensure(baseline==payload['baseline'],'OUTPUT_INVALID','Reused baseline differs from verified source artifact')
    successes=0
    for recorded,original in zip(value['records'],payload['records']):
        ensure(all(recorded[k]==original[k] for k in ('sample_number','sequence','mutations')),'OUTPUT_INVALID','Scored variant differs from N11 record')
        if recorded['error_code'] is None:
            ensure(recorded['measurement'] is not None and measurement(recorded['measurement'],original['sequence'])==recorded['score'],
                'OUTPUT_INVALID','Variant native score differs');successes+=1
        else:ensure(recorded['error_code']=='VARIANT_SCORE_FAILED' and recorded['score'] is None and recorded['measurement'] is None
            and isinstance(recorded['diagnostic'],str),'OUTPUT_INVALID','Invalid partial-failure record')
    ensure(successes<=runtime['variant_model_calls']<=len(value['records']),'OUTPUT_INVALID','Invalid variant model invocation count')
    return value


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        structure_artifact=body['structure_artifact'],n11_artifact=body['n11_artifact'])
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',qualification='DEVELOPMENT_UNREVIEWED',
        scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',requires_review=True,
        controlled_fault=fault,execution=execution,status='unreliable',null_reason=execution.get('error_code'),baseline=None,scoring=None,
        engineering_rules=None,validation=None,formal_candidates=None,scientific_gate='NOT_EVALUATED',source_receipt=execution.get('source_receipt'),
        structure_recheck=dict(status='NOT_EXECUTED',structure=None,plddt=None),mutation_burden=None,warnings=[],
        method_summary=dict(engine='ESM-IF1',model=policy.MODEL,commit=policy.COMMIT,parameters=policy.PARAMETERS,
            score_semantics='conditional autoregressive mean log-likelihood over every target-chain residue; higher is more likely under this backbone'))
    try:
        if execution.get('error_code'):raise RuntimeFault(execution['error_code'],execution.get('diagnostic') or execution['error_code'])
        ensure(execution['exit_code']==0 and execution['stopped_confirmed'] and execution['image_id']==policy.IMAGE,
            'OUTPUT_INVALID','No clean stopped pinned ESM-IF1 execution')
        if fault=='corrupt_output':raise RuntimeFault('OUTPUT_INVALID','Controlled scoring output corruption')
        observation=validate_observation(body,files)
        baseline=observation['baseline']
        if baseline and observation['baseline_status']=='computed_once':
            ensure(baseline['origin_job_id']==job['job_id'],'OUTPUT_INVALID','Computed WT baseline origin differs')
        successful=sum(r['score'] is not None for r in observation['records'])
        value.update(status='not_scored_empty_selection' if not body['sample_numbers'] else 'scored_partial_unreviewed'
            if successful<len(body['sample_numbers']) else 'scored_unreviewed',baseline=baseline,scoring=observation,null_reason=None,
            engineering_rules=evaluate(baseline['score'],observation['records']) if baseline else None,
            warnings=[dict(code='ENGINEERING_VALIDATION_ONLY',level='quality',severity='WARNING',
                message='仅为同一 WT 骨架的逆折叠工程打分；完整结构复核、burden 和科学验证未执行或未签收')])
        if body['sample_numbers'] and not successful:
            execution.update(error_code='TOOL_FAILED',diagnostic='All variant scores failed')
            value.update(status='unreliable',null_reason='TOOL_FAILED')
        for row in observation['records']:
            if row['error_code']:value['warnings'].append(dict(code=row['error_code'],level='failure',severity='WARNING',
                message='变体 '+str(row['sample_number'])+' 打分失败，未作为 R-35 正常淘汰样本'))
    except (RuntimeFault,KeyError,ValueError,TypeError,IndexError,OverflowError) as exc:
        code=execution.get('error_code') or 'OUTPUT_INVALID';execution.update(error_code=code,diagnostic=str(exc))
        value.update(null_reason=code,warnings=[dict(code=code,level='failure',severity='WARNING',message=str(exc))])
    return value
