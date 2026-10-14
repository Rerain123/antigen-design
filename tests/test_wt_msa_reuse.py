"""MSA reuse and preparation: control/format tests, no scientific inference."""
import copy
from contextlib import nullcontext
import pytest
from t01_phase1_real.common import encode, decode, sha
from t01_phase1_real.development.af3 import msa, policy, standard
from t01_phase1_real.development.workflow import msa_reuse, service, validation

WT='ACDEFGHIK'
VAR='CCDEFGHIK'
SOURCE=dict(job_id='wt',artifact=dict(job_id='wt',role='result'))


def request(**kwargs):
    return dict(protein_sequence=WT,user_sequence_id='test',host_species='pig',seed=1,timeout_seconds=60,**kwargs)


def prepared():
    return dict(sequence=WT,sequence_sha256=sha(WT.encode()),source=SOURCE,
                msas=dict(unpairedMsa='>query\n'+WT+'\n>homolog\nACdDE-GHIK\n',pairedMsa=''))


def native_msa_only():
    body=request(mode='msa_only');profile=policy.profile();binding={'job_id':'test'}
    fold=msa.folding(WT,1)
    data=copy.deepcopy(fold);data['sequences'][0]['protein'].update(prepared()['msas'])
    native={'request.json':encode(policy.native_request(body,binding)),'profile.json':encode(profile),
            'fold-input.json':encode(fold),'app-output/test/test_data.json':encode(data),
            'command.json':encode(dict(argv=['/alphafold3_venv/bin/python','/opt/t01/af3-app/alphafold/run_alphafold.py',
                '--run_data_pipeline=true','--run_inference=false','--num_diffusion_samples=5','--gpu_device=0',
                *policy.hmmer_arguments()],network='INHERITED_SECCOMP_AND_POD_DENY_ALL',input_sha256=sha(encode(fold)))),
            'execution.json':encode(dict(source_image_id=policy.IMAGE,model_sha256=profile['model']['sha256'],
                hmmer=policy.HMMER_BINARIES,packages={'alphafold3':'3.0.2','jax':'0.9.1'},gpu=profile['device'],
                scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',samples=[],
                msa_strategy=dict(mode='prepare_only',source=None,staged_sha256=None),
                database_receipt=dict(decompressed=True,output_root='unpacked-r03',
                    file_count=profile['database']['file_count'],total_bytes=profile['database']['total_bytes'])))}
    return body,binding,native


def manifest(native):
    native['manifest.json']=encode(dict(schema='t01.af3-native-files/1',files=[
        dict(path=n,size_bytes=len(v),sha256=sha(v)) for n,v in sorted(native.items()) if n!='manifest.json']))


def test_substitutes_only_query_and_keeps_homolog_columns():
    protein=msa.folding(VAR,1,prepared())['sequences'][0]['protein']
    assert protein['unpairedMsa']=='>query\n'+VAR+'\n>homolog\nACdDE-GHIK\n'
    assert protein['pairedMsa']=='' and 'templates' not in protein


@pytest.mark.parametrize('raw',['>q\n'+VAR+'\n','>q\n'+WT+'\n>bad\nACD\n','bad\n'+WT,'>q\n'+WT+'\n>bad\nAC*EFGHIK'])
def test_bad_query_or_alignment_rejected(raw):
    with pytest.raises(Exception):msa.alignment(raw,WT,VAR)


def test_no_indel_or_corrupt_wt_hash():
    with pytest.raises(Exception):msa.folding(VAR+'A',1,prepared())
    p=prepared();p['sequence_sha256']='0'*64
    with pytest.raises(Exception):msa.folding(VAR,1,p)


def test_msa_only_no_predictions_and_native_command_enforced():
    b,binding,native=native_msa_only();manifest(native)
    result=standard.normalize(native,b,binding)
    assert set(result)=={'msa.json'}
    assert decode(result['msa.json'])['model_inference_executed'] is False
    command=decode(native['command.json']);command['argv'].append('--run_inference=true')
    native['command.json']=encode(command);manifest(native)
    with pytest.raises(Exception,match='command differs'):standard.normalize(native,b,binding)


@pytest.mark.parametrize('change',['samples','sequence','missing','duplicate','hash'])
def test_preparation_refuses_incomplete_or_mismatched_outputs(change):
    b,binding,native=native_msa_only()
    if change=='samples':
        ex=decode(native['execution.json']);ex['samples']=[{}];native['execution.json']=encode(ex)
    elif change=='sequence':
        data=decode(native['app-output/test/test_data.json']);data['sequences'][0]['protein']['sequence']=VAR
        native['app-output/test/test_data.json']=encode(data)
    elif change=='missing':del native['app-output/test/test_data.json']
    elif change=='duplicate':native['app-output/other_data.json']=native['app-output/test/test_data.json']
    manifest(native)
    if change=='hash':native['fold-input.json']+=b' '
    with pytest.raises(Exception):standard.normalize(native,b,binding)


def test_requests_cannot_mix_preparation_and_reuse():
    assert policy.request(encode(request(mode='msa_only')))['mode']=='msa_only'
    assert policy.request(encode(request(msa_source=SOURCE)))['msa_source']==SOURCE
    with pytest.raises(Exception):policy.request(encode(request(mode='msa_only',msa_source=SOURCE)))


@pytest.mark.parametrize('wrong',['run','host','length','ancestor','raw','replay','none'])
def test_registered_source_guards_and_verified_native_extraction(monkeypatch,wrong):
    import importlib
    result_module=importlib.import_module('t01_phase1_real.development.af3.result')
    _,_,native=native_msa_only();raw=native['app-output/test/test_data.json']
    artifact={'artifact_id':'raw'}
    job=dict(job_id='wt',run_id='foreign' if wrong=='run' else 'run',state='succeeded',
             request_artifact={},artifacts=[] if wrong=='raw' else [artifact])
    original=request()
    if wrong=='host':original['host_species']='human'
    if wrong=='length':original['protein_sequence']+='A'
    if wrong=='ancestor':original['msa_source']=SOURCE
    value=dict(raw_artifacts=[dict(path='output/raw/app-output/test/test_data.json',artifact=artifact)],
               execution={},binding={},prediction={'valid':True},scientific_signoff=None)
    class SourceRuntime:
        def _registered_result_artifact(self,*a):return job,None,value
        def _input(self,*a):return encode(original)
        def artifact_bytes(self,*a):return raw
    monkeypatch.setattr(result_module,'result',lambda *a,**k:dict(value,execution=dict(error_code='OUTPUT_INVALID') if wrong=='replay' else {}))
    if wrong!='none':
        with pytest.raises(Exception):msa.sources(SourceRuntime(),None,request(msa_source=SOURCE),'run')
    else:
        files,receipt=msa.sources(SourceRuntime(),None,request(msa_source=SOURCE),'run')
        assert decode(files['msa-source.json'])['msas']==prepared()['msas']
        assert receipt['staged_sha256']==sha(files['msa-source.json'])


def test_existing_wt_af3_alignment_is_replayed_without_new_child(monkeypatch):
    rt=Runtime();controller(monkeypatch,rt)
    rt.nodes['prediction']=dict(state='succeeded',job_id='wt');rt.state='succeeded'
    rt.result=lambda jid:dict(raw_artifacts=[dict(path='output/raw/app-output/wt_data.json')])
    assert msa_reuse.ready(rt,'parent',request())==(SOURCE,None)
    assert rt.created==rt.dispatched==0


class Runtime:
    def __init__(self):self.nodes={};self.state='queued';self.created=0;self.dispatched=0;self.stopped=True
    def get(self,jid):
        return dict(run_id='run',job_id=jid,state=self.state if jid=='wt' else 'running',
                    tool_id=policy.TOOL,error_code=None if self.state!='failed' else 'TOOL_FAILED')
    def execution(self,jid):return dict(nodes=self.nodes) if jid=='parent' else dict(tree_stopped=self.stopped)
    def dispatch(self,jid):self.dispatched+=1;self.state='running'
    def recover(self,jid):pass
    def _db(self):return nullcontext(None)


def controller(monkeypatch,rt):
    def create(runtime,jid,name,req):
        assert req['mode']=='msa_only' and req['protein_sequence']==WT
        rt.created+=1;rt.nodes[name]=dict(job_id='wt',state='queued');return 'wt'
    monkeypatch.setattr(service,'_create_child',create)
    monkeypatch.setattr(service,'_record',lambda rt,jid,name,value:rt.nodes.update({name:value}))
    monkeypatch.setattr(service,'source',lambda *a:SOURCE)
    monkeypatch.setattr(service,'verified',lambda *a:rt.get(a[3]))
    monkeypatch.setattr(msa,'sources',lambda *a:({},{}))


def test_one_preparation_wait_resume_and_reuse_for_all_rounds(monkeypatch):
    rt=Runtime();controller(monkeypatch,rt)
    for _ in range(3):assert msa_reuse.ready(rt,'parent',request())==(None,'WAITING')
    assert rt.created==rt.dispatched==1
    rt.state='succeeded'
    for _ in range(3):assert msa_reuse.ready(rt,'parent',request())==(SOURCE,None)
    assert rt.created==rt.dispatched==1


def test_completed_wt_af3_supplies_msa_without_a_second_preparation(monkeypatch):
    rt=Runtime();controller(monkeypatch,rt);rt.state='succeeded'
    rt.nodes['prediction']=dict(job_id='wt',state='succeeded')
    monkeypatch.setattr(rt,'result',lambda jid:dict(raw_artifacts=[dict(path='output/raw/app-output/wt_data.json')]),raising=False)
    for _ in range(3):assert msa_reuse.ready(rt,'parent',request())==(SOURCE,None)
    assert rt.created==rt.dispatched==0 and 'wt_msa' not in rt.nodes


def test_failed_preparation_not_resubmitted_and_unstopped_not_consumed(monkeypatch):
    rt=Runtime();controller(monkeypatch,rt);msa_reuse.ready(rt,'parent',request());rt.state='failed'
    for _ in range(3):assert msa_reuse.ready(rt,'parent',request())==(None,'WT_MSA_TOOL_FAILED')
    assert rt.created==1
    rt.state='succeeded';rt.stopped=False
    with pytest.raises(Exception,match='stop not confirmed'):msa_reuse.ready(rt,'parent',request())


def test_report_distinguishes_archived_local_msa_from_reuse(monkeypatch):
    from test_s28_validation import inventory
    monkeypatch.setattr(validation,'inputs',lambda *a:inventory(24))
    monkeypatch.setattr(validation,'route',lambda *a:dict(engines=['af3'],reason='R04_SMALL_HIGH_IDENTITY'))
    obs=dict(state='succeeded',plddt=.9,structure={})
    monkeypatch.setattr(validation,'observation',lambda *a:dict(obs))
    old=validation.assemble(None,{}, {},'validation','run')
    assert 'AF3_LOCAL_MSA_NOT_WT_REUSE' in old['records'][0]['warnings']
    obs['msa_source']=SOURCE
    current=validation.assemble(None,{}, {},'validation','run')
    assert 'AF3_LOCAL_MSA_NOT_WT_REUSE' not in current['records'][0]['warnings']
    assert 'Same-run WT MSA' in current['method_summary']['af3_msa']


@pytest.mark.parametrize('damage', [None, 'missing_observation', 'different_uuid', 'invalid_memory', 'unknown_policy', 'software'])
def test_assigned_af3_hardware_is_bound_to_native_observation(damage):
    from t01_phase1_real.gpu_device import POLICY
    b, binding, native = native_msa_only()
    ex = decode(native['execution.json'])
    device = dict(name='NVIDIA A100-SXM4-40GB', uuid='GPU-53cfb869-cb43-8ac4-6a0c-b46b4d5202a8', memory_mib=40960)
    ex.update(gpu_allocation_policy=POLICY, gpu=device)
    native['gpu.json'] = encode(device)
    if damage == 'missing_observation': del native['gpu.json']
    elif damage == 'different_uuid': native['gpu.json'] = encode(dict(device, uuid='GPU-63cfb869-cb43-8ac4-6a0c-b46b4d5202a8'))
    elif damage == 'invalid_memory': ex['gpu']['memory_mib'] = 0; native['gpu.json'] = encode(ex['gpu'])
    elif damage == 'unknown_policy': ex['gpu_allocation_policy'] = 'unregistered'
    elif damage == 'software': ex['packages']['jax'] = 'unregistered'
    native['execution.json'] = encode(ex); manifest(native)
    if damage:
        with pytest.raises(Exception, match='environment|allocation policy'):
            standard.normalize(native, b, binding)
    else:
        result = standard.normalize(native, b, binding)
        assert decode(result['msa.json'])['model_inference_executed'] is False
