"""N12 rule boundaries, fixed profiles, provenance and native output semantics."""
import copy
from pathlib import Path
import pytest
from t01_phase1_real.common import REPO,RuntimeFault,encode,decode,sha
from t01_phase1_real.development.esm_if1 import policy
from t01_phase1_real.development.esm_if1.rules import evaluate
from t01_phase1_real.development.esm_if1.result import measurement


def rows(*scores):return [dict(sample_number=i+1,score=s,error_code='VARIANT_SCORE_FAILED' if s is None else None) for i,s in enumerate(scores)]


@pytest.mark.parametrize('score,threshold,passed,quality',[(-1.9,.1,True,'standard'),(-2.2,.1,True,'standard'),
    (-2.20000001,.15,True,'relaxed'),(-2.3,.15,True,'relaxed'),(-2.30000001,.2,True,'minimal'),
    (-2.36,.2,True,'minimal'),(-2.4,.2,True,'minimal'),(-2.40000001,.2,False,'minimal'),(-2.5,.2,False,'minimal')])
def test_negative_scores_and_exact_threshold_boundaries(score,threshold,passed,quality):
    result=evaluate(-2,rows(score))
    assert result['threshold']==threshold and result['records'][0]['passed']==passed and result['quality_flag']==quality
    assert result['records'][0]['delta_pct']==pytest.approx((score+2)/2*100)
    assert len(result['rounds'])<=3 and result['complete_validation_passed'] is None


@pytest.mark.parametrize('baseline',[0,0.0,1,float('nan'),float('inf'),None,True])
def test_zero_nonnegative_nonfinite_baseline_never_used(baseline):
    with pytest.raises(RuntimeFault):evaluate(baseline,rows(-2))


@pytest.mark.parametrize('scores',[(-2.1,-2.5),(None,-2.5),(None,None),()])
def test_relaxation_only_when_every_variant_is_normally_excluded(scores):
    result=evaluate(-2,rows(*scores));assert result['relaxation_history']==[]
    assert result['all_excluded'] is False


def test_full_exclusion_uses_exactly_two_relaxation_records():
    result=evaluate(-2,rows(-2.5,-2.6));assert result['failure_report']=='ALL_EXCLUDED_AFTER_20_PERCENT'
    assert result['relaxation_history']==[
        dict(step='validate_design',parameter='esm_if1恶化容忍',original_value=.1,relaxed_value=.15,quality_flag='relaxed'),
        dict(step='validate_design',parameter='esm_if1恶化容忍',original_value=.1,relaxed_value=.2,quality_flag='minimal')]


def body():
    ref=dict(artifact_id='t01p1r-artifact-'+'1'*32,run_id='t01p1r-run-'+'1'*32,job_id='t01p1r-job-'+'1'*32,
        attempt_id='t01p1r-attempt-'+'1'*32,role='result',media_type='application/json',evidence_kind='G0_REAL_OUTPUT',sha256='a'*64,size_bytes=100)
    return dict(protein_sequence='ACDEFGHIK',user_sequence_id='engineering',structure_artifact=copy.deepcopy(ref),
        n11_artifact=copy.deepcopy(ref),sample_numbers=[1,2],baseline_artifact=None,timeout_seconds=60)


@pytest.mark.parametrize('field,value',[('baseline_artifact',-2.),('baseline_artifact',{}),('structure_artifact',None),
    ('n11_artifact',None),('protein_sequence','AX'),('sample_numbers',[True]),('sample_numbers',[0]),('sample_numbers',[65]),
    ('sample_numbers',[1,1]),('timeout_seconds',0),('timeout_seconds',True),('model','different'),('baseline_score',-2.)])
def test_exact_source_selection_contract(field,value):
    request=body();request[field]=value
    with pytest.raises(RuntimeFault):policy.request(encode(request))


def test_empty_selection_is_explicitly_legal():
    request=body();request['sample_numbers']=[];assert policy.request(encode(request))==request


@pytest.mark.parametrize('damage',['missing','hash','size'])
def test_weight_integrity_verifier_with_private_registry(tmp_path,monkeypatch,damage):
    data=b'isolated contract weight fixture';path=tmp_path/'weight.pt';path.write_bytes(data)
    registry=dict(commit=policy.COMMIT,image=policy.IMAGE,model=policy.MODEL,files=[dict(path='weight.pt',bytes=len(data),sha256=sha(data))])
    (tmp_path/'assets.json').write_bytes(encode(registry));monkeypatch.setattr(policy,'HERE',tmp_path);monkeypatch.setattr(policy,'REPO',tmp_path)
    assert policy.verify_assets()==registry
    if damage=='missing':path.unlink()
    elif damage=='size':path.write_bytes(data+b'x')
    else:path.write_bytes(b'X'+data[1:])
    with pytest.raises(RuntimeFault):policy.verify_assets()


@pytest.mark.parametrize('damage',['nan','score','padding','length','identity'])
def test_native_loss_mean_is_checked_without_model(damage):
    row=dict(sequence_sha256=sha(b'AAA'),residue_count=3,per_residue_nll=[1.,2.,3.],target_padding_mask=[False]*3,score=-2.)
    assert measurement(row,'AAA')==-2.
    if damage=='nan':row['per_residue_nll'][0]=float('nan')
    elif damage=='score':row['score']=2.
    elif damage=='padding':row['target_padding_mask'][1]=True
    elif damage=='length':row['per_residue_nll'].pop()
    else:row['sequence_sha256']='0'*64
    with pytest.raises(RuntimeFault):measurement(row,'AAA')


def test_gpu_offline_command_and_registry():
    from t01_phase1_real.development import docker
    from t01_phase1_real.development.registry import spec
    job=dict(tool_id=policy.TOOL,run_id='run',job_id='job',attempt_id='attempt',execution_identity='execution')
    command=docker.esm_if1_command(REPO/'tmp',job,'n12-test',60)
    assert command[command.index('--network')+1]=='none' and '--read-only' in command
    assert command[command.index('--gpus')+1]=='device=0' and policy.IMAGE in command and spec(policy.TOOL).NODE=='N12'


@pytest.fixture
def native_recording(monkeypatch):
    folder=REPO/'discovery/t01-phase1-real/w5/esm-if1-integration-20260908/smoke-r02/cases/native-baseline-and24'
    job=decode((folder/'job.json').read_bytes());value=decode((folder/'result.json').read_bytes())
    files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
    # Recorded execution keeps its immutable original profile when current source gains tests/guards.
    monkeypatch.setattr(policy,'registered_profile',lambda:job['execution_profile'])
    return job,decode(files['input.json']),files,value['execution']


def test_recorded_real_baseline_and24(native_recording):
    from t01_phase1_real.development.esm_if1.result import result
    value=result(*native_recording)
    assert value['scoring']['baseline_status']=='computed_once' and len(value['scoring']['records'])==24
    assert value['engineering_rules']['all_excluded'] and value['validation'] is None


@pytest.mark.parametrize('damage',['baseline_score','zero_baseline','native_nan','coordinates','target_chain','model',
    'source_structure','mapping','loss_range','score_sign','missing_variant','sequence','mutations','baseline_calls',
    'variant_calls','source_hash','native_score_scope','network','baseline_reuse_fake','source_n11_sequence'])
def test_semantic_native_corruption_is_quarantined(native_recording,damage):
    from t01_phase1_real.development.esm_if1.result import result
    job,body,files,execution=native_recording
    obs=decode(files['output/observation.json']);payload=decode(files['native/payload.json']);runtime=decode(files['output/runtime.json'])
    if damage=='baseline_score':obs['baseline']['score']-=1
    elif damage=='zero_baseline':obs['baseline'].update(score=0.,per_residue_nll=[0.]*len(body['protein_sequence']))
    elif damage=='native_nan':
        # JSON NaN is a native corruption fixture, not a supported API input.
        import json
        obs['records'][0]['measurement']['per_residue_nll'][0]=float('nan')
        files['output/observation.json']=json.dumps(obs).encode()
    elif damage=='coordinates':
        parsed=decode(files['output/parsed-coordinates.json']);parsed['coordinates']['A'][0][0][0]+=1;files['output/parsed-coordinates.json']=encode(parsed)
    elif damage in ('target_chain','model','source_structure','mapping'):
        key={'target_chain':'target_chain','model':'model','source_structure':'source_structure_sha256','mapping':'mapping_sha256'}[damage]
        for sig in (payload['signature'],obs['signature'],obs['baseline']['signature']):sig[key]='WRONG'
    elif damage=='loss_range':obs['records'][0]['measurement']['per_residue_nll'].pop()
    elif damage=='score_sign':obs['records'][0]['score']=abs(obs['records'][0]['score'])
    elif damage=='missing_variant':obs['records'].pop()
    elif damage in ('sequence','mutations'):
        if damage=='sequence':
            payload['records'][0]['sequence']='A'+payload['records'][0]['sequence'][1:]
            obs['records'][0]['sequence']=payload['records'][0]['sequence']
        else:payload['records'][0]['mutations']=[];obs['records'][0]['mutations']=[]
    elif damage=='baseline_calls':runtime['baseline_model_calls']=24
    elif damage=='variant_calls':runtime['variant_model_calls']=0
    elif damage=='source_hash':runtime['source_sha256']['esm/inverse_folding/util.py']='0'*64
    elif damage=='native_score_scope':obs['score_mean_scope']='mutations_only'
    elif damage=='network':runtime['network_interfaces'].append([2,'eth0'])
    elif damage=='baseline_reuse_fake':runtime['baseline_reused']=True
    elif damage=='source_n11_sequence':
        n11=decode(files['input/n11-result.json']);n11['generation']['records'][0]['sequence']='A'*len(body['protein_sequence']);files['input/n11-result.json']=encode(n11)
    if damage!='native_nan':files['output/observation.json']=encode(obs)
    files['native/payload.json']=encode(payload)
    # Rehash the controlled copy to ensure deeper semantic/binding checks detect corruption.
    execution['source_receipt']['prepared_hashes']={n:sha(files[n]) for n in execution['source_receipt']['prepared_hashes']}
    runtime['native_input_sha256']={n[7:]:sha(v) for n,v in files.items() if n.startswith('native/')}
    runtime['native_output_sha256']={n[7:]:sha(v) for n,v in files.items() if n.startswith('output/') and n!='output/runtime.json'}
    files['output/runtime.json']=encode(runtime)
    value=result(job,body,files,execution)
    assert value['scoring'] is None and value['baseline'] is None and value['null_reason']=='OUTPUT_INVALID'
