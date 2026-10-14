import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.variant_report import policy,service
from t01_phase1_real.development.variant_report.compute import variants
from t01_phase1_real.development.variant_report.ranking import rank_fixture,hard_filter,stability,COUNTS

def request():
    return dict(protein_sequence='ACDE',user_sequence_id='test report',upstream=dict(design_audit=None,foldx=None),
        variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=30)

def fixture(id='a',**changes):
    value=dict(id=id,overall=.8,count=6,ddg=0.,epitope=1.3,epitope_state='VERIFIED',soft_penalty=False,host_medium=False,
        flags={n:False for n in ('epitope_violation','safety_excluded','constraint_override','host_similarity_high','burden_exceeded')})
    value.update(changes);return value

def rank(rows,objective='general'):return rank_fixture(rows,objective,evidence_kind='SYNTHETIC_CONTRACT_FIXTURE')

def test_missing_query_and_idempotency(tmp_path):
    rt=Runtime(tmp_path);body=request();j=rt.submit_sequence(encode(body),'empty',policy.TOOL)
    assert rt.dispatch(j['job_id'])['state']=='succeeded'
    v=rt.result(j['job_id']);assert v['report']['outcome']=='INPUTS_UNAVAILABLE'
    assert v['report']['best_candidate'] is None and not v['usable_for_pipeline']
    assert rt.submit_sequence(encode(body),'empty',policy.TOOL)['job_id']==j['job_id']

@pytest.mark.parametrize('fault,code',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_failure_recovery_retry(tmp_path,fault,code):
    rt=Runtime(tmp_path);j=rt.submit_sequence(encode(request()),'fault',policy.TOOL);rt._development_fault=fault
    rt.dispatch(j['job_id']);rt._development_fault=None
    if fault=='interrupt_after_claim':rt.recover(j['job_id'])
    assert rt.get(j['job_id'])['error_code']==code and rt.result(j['job_id'])['report'] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry')))
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'

@pytest.mark.parametrize('stop',['cancel','timeout'])
def test_running_stop_cannot_publish_report(tmp_path,monkeypatch,stop):
    rt=Runtime(tmp_path);j=rt.submit_sequence(encode(request()),'stop',policy.TOOL);original=service.evaluate
    def evaluate(*args):
        with rt._tx() as db:rt._stop(db,rt._job(db,j['job_id']),stop)
        return original(*args)
    monkeypatch.setattr(service,'evaluate',evaluate);rt.dispatch(j['job_id'])
    assert rt.get(j['job_id'])['state']==('cancelled' if stop=='cancel' else 'timed_out')
    assert rt.result(j['job_id'])['report'] is None

def test_real_deadline_elapsed(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);body=request();body['timeout_seconds']=1;j=rt.submit_sequence(encode(body),'deadline',policy.TOOL)
    ticks=iter([0.,2.]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(ticks))
    rt.dispatch(j['job_id']);assert rt.get(j['job_id'])['state']=='timed_out'

def test_queued_cancel_and_publication_hash(tmp_path):
    rt=Runtime(tmp_path);j=rt.submit_sequence(encode(request()),'cancel',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    assert rt.dispatch(j['job_id'])['state']=='cancelled'
    j=rt.submit_sequence(encode(request()),'tamper',policy.TOOL);rt.dispatch(j['job_id'])
    ref=next(r for r in rt.get(j['job_id'])['artifacts'] if r['role']=='result')
    with rt._db() as db:p=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    (tmp_path/p).write_bytes(b'{}')
    with pytest.raises(RuntimeFault):rt.result(j['job_id'])

def test_manual_score_and_pareto_tie_group():
    v=rank([fixture(),fixture('b'),fixture('dominated',overall=.7,count=7)])
    assert v['pareto_ids']==['a','b']
    assert v['score_groups']==[dict(score=.89,ids=['a','b'])]
    assert v['best_candidate'] is None and v['top20'] is None

@pytest.mark.parametrize('objective',['general','solubility','thermostability'])
def test_burden_denominator_matches_registered_authority(objective):
    from t01_phase1_real.development.design_backend import policy as design
    scales=decode((design.HERE/'scales.json').read_bytes())
    assert COUNTS[objective]==scales['thresholds'][objective]['count']

def test_penalties_null_rules_and_overflow():
    a=rank([fixture(soft_penalty=True,host_medium=True)])['computed'][0]
    assert a['score']==pytest.approx(.74)
    r=rank([fixture(ddg=None,epitope=None,epitope_state='NO_STRUCTURE_DEGRADED',count=None)])
    assert r['computed'][0]['score']==pytest.approx(.85)
    assert stability(-100000)==1. and stability(100000)==0.
    assert stability(-2)>stability(0)>stability(2)

@pytest.mark.parametrize('field',['epitope_violation','safety_excluded','constraint_override','host_similarity_high','burden_exceeded'])
def test_each_exclusion_and_unknown(field):
    f=fixture()['flags'];f[field]=True;assert hard_filter(f)['state']=='EXCLUDED'
    f[field]=None;assert hard_filter(f)['state']=='UNDETERMINED'

@pytest.mark.parametrize('changes',[dict(overall=None),dict(overall=float('nan')),dict(ddg=float('inf')),dict(count=-1),dict(epitope_state='NOT_EXECUTED')])
def test_bad_ranking_input(changes):
    with pytest.raises(RuntimeFault):rank([fixture(**changes)])

def test_cannot_promote_fixture_or_inject_scores():
    with pytest.raises(RuntimeFault):rank_fixture([fixture()],'general',evidence_kind='G0_REAL_OUTPUT')
    body=request();body['scores']=[1.]
    with pytest.raises(RuntimeFault):policy.request(encode(body))

def test_exact_join_and_wrong_diff():
    body=request();body['foldx_bindings']=[dict(sample_number=1,variant_id='v')]
    mutation=dict(position=1,wt_residue='A',mut_residue='G')
    audit=dict(burden_records=[dict(sample_number=1,mutations=[mutation])])
    values=dict(design_audit=dict(audit=audit),foldx=dict(variant_ddg=[dict(variant_id='v',ddg_foldx=-1.)]))
    files={'input/foldx-request.json':encode(dict(variants=[dict(variant_id='v',mutations=[dict(position=1,wt='A',mut='G')])])),
        'input/design/input/n11-result.json':encode(dict(binding={},generation=dict(records=[dict(sample_number=1,sequence='GCDE')]))) }
    row=variants(body,files,values)[0];assert row['foldx']['ddg_foldx']==-1. and row['sequence']=='GCDE'
    files['input/foldx-request.json']=encode(dict(variants=[dict(variant_id='v',mutations=[dict(position=1,wt='A',mut='S')])]))
    with pytest.raises(RuntimeFault):variants(body,files,values)
