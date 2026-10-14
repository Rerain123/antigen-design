"""Project batch adapter checks; fixtures do not claim native model validation."""
from types import SimpleNamespace
import pytest
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.thermompnn import batch_adapter as batch,policy
from test_thermompnn_development import native_recording


class Scalar(float):
    def cpu(self):return self


class Model:
    def __init__(self):
        self.embeddings=0;self.calls=[];self.change=False
        self.prot_mpnn=SimpleNamespace(forward=self.embedding)
    def embedding(self,pdb):self.embeddings+=1;return 0.25
    def forward(self,pdb,mutations):
        self.calls.append((pdb,list(mutations)))
        value=self.prot_mpnn.forward('changed' if self.change and len(self.calls)>1 else pdb)
        return [None if m is None else {'ddG':Scalar(m-value)} for m in mutations],None


@pytest.mark.parametrize('count',[1,320,321,2000,19980])
def test_batched_head_equals_one_call_whole_structure_and_one_embedding(count):
    model=Model();original=model.prot_mpnn.forward;progress=[]
    mutations=list(range(count));mutations[0]=None
    expected=Model().forward('whole pdb',mutations)
    actual=batch.predict(model,'whole pdb',mutations,equal=lambda a,b:a==b,progress=progress.append)
    assert actual==expected and model.embeddings==1
    assert all(pdb=='whole pdb' and len(ms)<=320 for pdb,ms in model.calls)
    assert model.prot_mpnn.forward==original and progress[-1]['completed']==count


def test_changed_whole_structure_aborts_and_restores_embedding_method():
    model=Model();original=model.prot_mpnn.forward;model.change=True
    with pytest.raises(ValueError,match='features changed'):
        batch.predict(model,'whole pdb',list(range(321)),equal=lambda a,b:a==b,progress=lambda r:None)
    assert model.prot_mpnn.forward==original


@pytest.mark.parametrize('damage',[None,'hash','progress','csv','entrypoint'])
def test_batch_receipt_and_full_native_csv_both_required(native_recording,damage):
    from t01_phase1_real.development.thermompnn.result import result
    job,body,files,execution=native_recording;runtime=decode(files['output/runtime.json'])
    runtime['batch_adapter']=dict(mode=batch.MODE,sha256=sha((policy.HERE/'batch_adapter.py').read_bytes()),
        mutations_per_batch=320,official_files_modified=False)
    command=runtime['commands']['scan'];command['argv'][2]='/batch_adapter.py'
    command['execution']='official_cli_with_project_batch_adapter'
    total=len(body['protein_sequence'])*20
    files['output/batch-progress.json']=encode(dict(mode=batch.MODE,batches=[dict(start=0,count=total,completed=total,total=total)]))
    if damage=='hash':runtime['batch_adapter']['sha256']='0'*64
    if damage=='progress':files['output/batch-progress.json']=encode(dict(mode=batch.MODE,batches=[]))
    if damage=='csv':files['output/native/ThermoMPNN_inference_target.csv']=b''
    if damage=='entrypoint':command['argv'][2]='/unknown.py'
    runtime['native_output_sha256']={n[7:]:sha(v) for n,v in files.items() if n.startswith('output/') and n!='output/runtime.json'}
    files['output/runtime.json']=encode(runtime)
    value=result(job,body,files,execution)
    if damage:assert value['null_reason']=='OUTPUT_INVALID' and value['scan'] is None
    else:assert value['scan']['native_prediction_count']==180
