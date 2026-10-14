import copy
import pytest
from t01_phase1_real.common import RuntimeFault,decode,encode
from t01_phase1_real.development.epitope_protection.compute import identity,rsa_delta,geometry,prediction,compare,positions
from t01_phase1_real.development.epitope_protection import policy
from t01_phase1_real.development import Runtime

def local_request(rt):
    from t01_phase1_real.development.design_backend import policy as design
    from t01_phase1_real.development.variant_report.m1 import verified_preselection
    seq='ACDEFGHIK'
    audit=dict(protein_sequence=seq,user_sequence_id='empty N12 audit',upstream={n:None for n in design.PRODUCERS},
        user_regions=[],objective='general',epitope_policy='PRESERVE',epitope_mode='both',
        membrane_design_confirm=False,sample_numbers=[],timeout_seconds=30)
    dj=rt.submit_sequence(encode(audit),'n12',design.TOOL);rt.dispatch(dj['job_id']);dj=rt.get(dj['job_id'])
    assert dj['state']=='succeeded'
    src=dict(job_id=dj['job_id'],artifact=next(r for r in dj['artifacts'] if r['role']=='result'))
    with rt._db() as db:fact=verified_preselection(rt,db,seq,'empty paired audit',src)
    return dict(protein_sequence=seq,user_sequence_id='empty paired audit',upstream=dict(design_audit=src),
        preselection=fact,pairs=[],timeout_seconds=30)

def test_empty_pairs_query_and_idempotency(tmp_path):
    rt=Runtime(tmp_path);b=local_request(rt);j=rt.submit_sequence(encode(b),'n13',policy.TOOL)
    assert rt.dispatch(j['job_id'])['state']=='succeeded';v=rt.result(j['job_id'])
    assert v['protection']['records']==[] and v['protection']['scientific_pass'] is None
    assert rt.submit_sequence(encode(b),'n13',policy.TOOL)['job_id']==j['job_id']

@pytest.mark.parametrize('fault,code',[('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')])
def test_local_failure_and_retry(tmp_path,fault,code):
    rt=Runtime(tmp_path);b=local_request(rt);j=rt.submit_sequence(encode(b),'n13',policy.TOOL);rt._development_fault=fault
    rt.dispatch(j['job_id']);rt._development_fault=None
    if fault=='interrupt_after_claim':rt.recover(j['job_id'])
    assert rt.get(j['job_id'])['error_code']==code and rt.result(j['job_id'])['protection'] is None
    retry=rt.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='retry')))
    assert rt.dispatch(retry['job_id'])['state']=='succeeded'

def test_elapsed_deadline_and_queued_cancel(tmp_path,monkeypatch):
    from t01_phase1_real.development.epitope_protection import service
    rt=Runtime(tmp_path);b=local_request(rt);b['timeout_seconds']=1;j=rt.submit_sequence(encode(b),'n13',policy.TOOL)
    ticks=iter([0.,2.]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(ticks))
    assert rt.dispatch(j['job_id'])['state']=='timed_out' and rt.result(j['job_id'])['protection'] is None
    j=rt.submit_sequence(encode(b),'queued',policy.TOOL)
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='cancel')))
    assert rt.dispatch(j['job_id'])['state']=='cancelled'

def test_publication_tamper_and_failed_n13_report_link(tmp_path):
    from t01_phase1_real.development.variant_report import policy as report
    rt=Runtime(tmp_path);b=local_request(rt);j=rt.submit_sequence(encode(b),'n13',policy.TOOL);rt._development_fault='compute_failure'
    rt.dispatch(j['job_id']);rt._development_fault=None;j=rt.get(j['job_id'])
    rb=dict(protein_sequence=b['protein_sequence'],user_sequence_id=b['user_sequence_id'],
        upstream=dict(design_audit=b['upstream']['design_audit'],foldx=None),
        variant_source='N11_DESIGN_AUDIT',foldx_bindings=[],timeout_seconds=30)
    rb['n13_source']=dict(job_id=j['job_id'],artifact=next(r for r in j['artifacts'] if r['role']=='diagnostic'))
    rj=rt.submit_sequence(encode(rb),'failed-n13-report',report.TOOL);rt.dispatch(rj['job_id'])
    assert rt.result(rj['job_id'])['report']['n13']=='failed'
    ref=rb['n13_source']['artifact']
    with rt._db() as db:path=rt.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    path.write_bytes(b'{}')
    with pytest.raises(RuntimeFault):rt.result(j['job_id'])

def test_source_cycle_and_unknown_variant_rejected(tmp_path):
    rt=Runtime(tmp_path);b=local_request(rt)
    b['pairs']=[dict(variant_id='not-in-batch',wt={n:None for n in policy.SIDE_PRODUCERS},variant={n:None for n in policy.SIDE_PRODUCERS})]
    with pytest.raises(RuntimeFault):rt.submit_sequence(encode(b),'wrong',policy.TOOL)

@pytest.mark.parametrize('damage',['selection_hash','wt_sequence','early_n15'])
def test_n13_rejects_unverified_n12_or_early_n15_source(tmp_path,damage):
    from t01_phase1_real.development.variant_report import policy as report
    rt=Runtime(tmp_path);b=local_request(rt)
    if damage=='selection_hash':b['preselection']['records_sha256']='0'*64
    elif damage=='wt_sequence':b['protein_sequence']='AAAAAAAAA'
    else:
        old=dict(protein_sequence=b['protein_sequence'],user_sequence_id='early N15',
            upstream=dict(design_audit=None,foldx=None),variant_source='N11_DESIGN_AUDIT',
            foldx_bindings=[],timeout_seconds=30)
        j=rt.submit_sequence(encode(old),'early-n15',report.TOOL);rt.dispatch(j['job_id']);j=rt.get(j['job_id'])
        src=dict(job_id=j['job_id'],artifact=next(r for r in j['artifacts'] if r['role']=='result'))
        b['upstream']['design_audit']=src;b['preselection']['source']=src
    with pytest.raises(RuntimeFault) as exc:rt.submit_sequence(encode(b),'damaged-'+damage,policy.TOOL)
    assert exc.value.code in ('OUTPUT_INVALID','FORBIDDEN')

def side():return dict(hotspots=[dict(start=1,end=3,weighted_score=.6)],rsa=[.5,.5,.5],quality_condition=True,
    geometry={str(i):dict(atoms={'CA':p}) for i,p in enumerate(([0.,0.,0.],[3.,0.,0.],[0.,4.,0.]),1)},domains=[],reasons=[])

def test_l1_identity_and_union():
    ps=positions([dict(start=1,end=2),dict(start=2,end=3)],3);assert ps==[1,2,3]
    assert identity('AAA','AGA',ps)['value'] is False
    assert identity('AAA','AGA',[1,3])['value'] is True
    assert identity('AAA','AAA',[])['value'] is None

@pytest.mark.parametrize('delta,passes',[(-.149,True),(-.15,False),(-.151,False),(0,True)])
def test_rsa_strict_threshold(delta,passes):
    value=rsa_delta([.5],[float(__import__('decimal').Decimal('.5')+__import__('decimal').Decimal(str(delta)))],[1])
    assert value['value']==pytest.approx(delta) and value['engineering_threshold_pass']==passes

def test_rsa_missing_and_outside():
    assert rsa_delta([None],[.2],[1])['reason']=='RSA_MISSING_AT_VALIDATION_POSITION'
    for bad in (-.01,1.1,float('nan'),True):
        with pytest.raises(RuntimeFault):rsa_delta([bad],[.2],[1])

def test_rigid_motion_is_not_deformation():
    a=side()['geometry'];b=copy.deepcopy(a)
    for row in b.values():
        x,y,z=row['atoms']['CA'];row['atoms']['CA']=[-y+10,x+20,z-3]
    result=geometry(a,b,[1,2,3]);assert result['value']==pytest.approx(0,abs=1e-12) and result['rmsd']==result['value']
    b['2']['atoms']['CA']=[10.,26.,-3.]
    result=geometry(a,b,[1,2,3]);assert result['value']>0.5

def test_geometry_missing_single_and_empty():
    a=side()['geometry'];assert geometry(a,a,[1])['reason']=='INSUFFICIENT_MATCHED_CA'
    assert geometry(a,a,[])['value'] is None
    del a['2']['atoms']['CA'];assert geometry(a,a,[1,2])['reason']=='MATCHED_CA_MISSING'

@pytest.mark.parametrize('score,passes',[(.799,True),(.8,False),(.801,False)])
def test_prediction_strict_boundary(score,passes):
    a=[dict(start=1,end=3,weighted_score=.6)];b=[dict(start=1,end=3,weighted_score=score)]
    assert prediction(a,b)['engineering_threshold_pass']==passes

def test_prediction_no_shift_guess_and_missing_score():
    a=[dict(start=1,end=3,weighted_score=.6)]
    assert prediction(a,[dict(start=2,end=4,weighted_score=.6)])['value'] is None
    assert prediction(a,[dict(start=1,end=3)])['reason']=='WEIGHTED_SCORE_UNAVAILABLE'
    assert prediction([],[])['value'] is None and prediction(None,a)['value'] is None

@pytest.mark.parametrize('hotspots',[None,[]])
def test_empty_or_missing_never_pass(hotspots):
    s=side();s['hotspots']=hotspots;r=compare('AAA','AAA',dict(wt=s,variant=copy.deepcopy(s)))
    assert r['scientific_pass'] is None and r['formal_structural_preservation'] is None
    assert r['l1']['value'] is None and r['l4']['value'] is None

def test_low_quality_stops_geometric_and_rsa_but_not_sequence():
    s=side();s['quality_condition']=False;r=compare('AAA','AAA',dict(wt=s,variant=copy.deepcopy(s)))
    assert r['l1']['value'] is True and r['l2']['value'] is None and r['l3']['hotspot']['value'] is None
    assert r['epitope_violation'] is None

def test_four_engineering_observations_do_not_sign_protection():
    s=side();s['domains']=[dict(type='domain',start=1,end=3)]
    r=compare('AAA','AAA',dict(wt=s,variant=copy.deepcopy(s)))
    assert r['l1']['value'] is True and r['l2']['value']==0 and r['l3']['hotspot']['value']==pytest.approx(0,abs=1e-12) and r['l4']['value']==0
    assert r['l3']['functional_domains'][0]['observation']['value']==pytest.approx(0,abs=1e-12)
    assert r['formal_prediction_preservation'] is None and r['l3']['shape_similarity']['value'] is None

def test_rule_profiles_cannot_mix_and_large_geometry_not_truncated():
    a,b=side(),side();a['prediction_rule_profile']='old';b['prediction_rule_profile']='new'
    assert compare('AAA','AAA',dict(wt=a,variant=b))['l4']['reason']=='PREDICTION_RULE_PROFILES_DIFFER'
    g={str(i):dict(atoms={'CA':[float(i),float(i%3),float(i%7)]}) for i in range(1,145)}
    assert geometry(g,g,list(range(1,145)))['matched_count']==144
