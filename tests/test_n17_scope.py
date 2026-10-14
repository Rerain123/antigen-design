"""Synthetic scope tests plus read-only real input request replay; no models."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode,decode,sha
from t01_phase1_real.development.workflow.stability_scope import scope,timeout
from t01_phase1_real.development.workflow import m1,policy
from t01_phase1_real.development.wt_reference.compute import evaluate


class Inputs:
    def __init__(self,length=9):
        self.body=dict(protein_sequence='A'*length,m1_test={'constraints':dict(source_id='synthetic',
            fixed_positions=[1],restricted_positions=[{'position':2}],open_positions=list(range(3,length+1)))})
        self.rows={n:dict(state='succeeded',job_id=n) for n in ('structure','topology','epitope_map','design_audit')}
        self.values=dict(structure={'analysis':dict(quality={'quality':{'confidence':'high'}},
            mapping=dict(entries=[dict(sequence_position=p,reason='mapped',structure_residue={'insertion_code':''}) for p in range(1,length+1)],chain_candidates=['A'],fixed_chain_ids=[]),rsa={'raw_normalized_ratios':[None]*length})},
            topology={'topology':{'tm_count':0}},epitope_map={'epitopes':{'b_cell_antigenic_hotspot_map':{'hotspots':[]}}},
            design_audit={'audit':{'domain_intervals':None}})
    def result(self,jid):return self.values[jid]
    def scan(self):return scope(self,self.body,self.rows)


def test_all_eligible_positions_no_single_site_truncation():
    rt=Inputs();fact,reason=rt.scan()
    assert reason is None and fact['positions']==list(range(3,10)) and fact['excluded']==[1,2]
    assert fact['scope_sha256']==sha(encode({k:v for k,v in fact.items() if k!='scope_sha256'}))
    assert decode(encode(fact))==fact
    mapping=rt.values['structure']['analysis']['mapping']['entries']
    mapping[2]['reason']='unmapped';mapping[3]['structure_residue']['insertion_code']='A'
    fact,reason=rt.scan()
    assert fact['positions']==list(range(5,10)) and fact['uncovered_selected_positions']==[3,4]
    assert 'INSERTION_CODES_UNSUPPORTED_NOT_SCANNED' in fact['warnings']


def test_protection_wins_over_open_and_empty_is_not_arbitrary_fallback():
    rt=Inputs();c=rt.body['m1_test']['constraints'];c['open_positions']=[1,2]
    fact,reason=rt.scan()
    assert reason=='NO_COVERED_EXPLICIT_OPEN_SCAN_POSITION' and fact['positions']==[]


@pytest.mark.parametrize('change,reason',[('structure','STRUCTURE_UNAVAILABLE'),('topology','TOPOLOGY_UNAVAILABLE'),
    ('low','LOW_CONFIDENCE_SCAN_SKIPPED'),('membrane','MEMBRANE_SCAN_DOMAIN_NOT_SUPPORTED')])
def test_conditional_skip_does_not_invent_a_scope(change,reason):
    rt=Inputs()
    if change in rt.rows:rt.rows[change]['state']='failed'
    elif change=='low':rt.values['structure']['analysis']['quality']['quality']['confidence']='low'
    else:rt.values['topology']['topology']['tm_count']=1
    assert rt.scan()==(None,reason)


def test_long_sequence_r41_priority_and_clamped_union():
    rt=Inputs(600);a=rt.values['structure']['analysis']
    rt.body['stability_scan']={'scan_region':[590,600]}
    a['rsa']['raw_normalized_ratios'][20:22]=[.20,.21]
    hotspots=rt.values['epitope_map']['epitopes']['b_cell_antigenic_hotspot_map']
    hotspots['hotspots']=[dict(start=570,end=580),dict(start=580,end=599)]
    rt.values['design_audit']['audit']['domain_intervals']=[dict(start=200,end=300)]
    assert rt.scan()[0]['positions']==list(range(590,601))
    rt.body.pop('stability_scan');f,_=rt.scan()
    assert f['positions']==[21,22] and f['selection_rule'].startswith('R41_RSA')
    a['rsa']['raw_normalized_ratios']=[None]*600
    assert rt.scan()[0]['positions']==list(range(550,601))
    hotspots['hotspots']=[]
    assert rt.scan()[0]['positions']==list(range(190,211))+list(range(290,311))
    rt.values['design_audit']['audit']['domain_intervals']=None
    f,_=rt.scan();assert f['positions']==list(range(3,501))
    assert 'DEFAULT_FIRST_500_PROVIDE_SCAN_REGION' in f['warnings']


def test_rsa_never_clamped_or_allowed_to_bypass_protected_scope():
    rt=Inputs(600);a=rt.values['structure']['analysis']
    a['rsa']['raw_normalized_ratios']=[2.,.8,.199,.2,None,float('nan')]+[None]*594
    f,_=rt.scan();assert f['positions']==[4]
    assert f['selection_regions']==[dict(start=2,end=2),dict(start=4,end=4)]
    assert 'RSA_PARTIAL_OR_OUT_OF_RANGE_VALUES_NOT_USED' in f['warnings']


def test_multichain_scope_retained_for_foldx_not_thermompnn():
    rt=Inputs();rt.values['structure']['analysis']['mapping']['chain_candidates']=['A','B']
    assert rt.scan()[0]['monomer'] is False and len(rt.scan()[0]['positions'])==7


@pytest.mark.parametrize('bad',[[0,3],[2,1],[1,10],[True,5],'1:3',[1,2,3]])
def test_invalid_backend_explicit_region_rejected(bad):
    from test_local_workflow import body
    b=body();b['stability_scan']={'scan_region':bad}
    # Test bounds on exact 9-aa input independently of the fixture's length.
    b['protein_sequence']='A'*9
    with pytest.raises(RuntimeFault):policy.request(encode(b))


def test_deadline_scales_with_complete_scope_but_is_bounded():
    assert timeout([1])==900
    assert timeout(list(range(40)))==3780
    assert timeout(list(range(500)))==28800


def test_real_archived_request_now_contains_all_permitted_sites():
    from test_m1_service_p4 import RecordedInputs
    from t01_phase1_real.development.workflow import service
    from t01_phase1_real.development.foldx import policy as foldx
    rt=RecordedInputs();f,reason=m1.scan_scope(rt,rt.body,rt.rows)
    assert reason is None and len(f['positions'])>1
    for name in ('wt_foldx','wt_thermompnn'):
        req,reason=service.request_for(rt,rt.body,rt.rows,name)
        assert reason is None and req['scan_positions']==f['positions']
        assert req['scope_source']['source_id'].endswith(f['scope_sha256'])
        if name=='wt_foldx':assert foldx.request(encode(req))==req


def test_reference_reports_missing_mutations_and_duplicate_records():
    req=dict(scan_positions=[1,2],fixed_positions=[],scope_source={})
    rows=[dict(position=p,wt='A',mut=aa) for p in (1,2) for aa in 'ACDEFGHIKLMNPQRSTVWY']
    receipts={n:dict(state='available' if n=='foldx' else 'missing') for n in ('structure','topology','foldx','thermompnn','design_audit')}
    files={'input/source-receipts.json':encode(receipts),'input/foldx-request.json':encode(req),
        'input/foldx-result.json':encode({'status':'positionscan_unreviewed'}),
        'input/foldx-verified-scan.json':encode({'rows':rows})}
    b=dict(protein_sequence='AA',upstream={'structure':None})
    r=evaluate(b,files);assert r['engines']['foldx']['coverage']['complete']
    assert not r['engines']['thermompnn']['coverage']['complete']
    files['input/foldx-verified-scan.json']=encode({'rows':rows[:-1]+[rows[0]]})
    c=evaluate(b,files)['engines']['foldx']['coverage']
    assert not c['complete'] and c['missing_mutation_count']==1 and c['duplicate_mutation_count']==1


def test_html_scan_coverage_never_claims_whole_protein():
    from t01_phase1_real.service_api.user_report import render
    html=render({'wt_reference':{'engines':{'foldx':dict(requested_positions=[1,2],effective_positions=[1],coverage={'complete':False})}}}).decode()
    assert '请求位点' in html and '未完成或覆盖未核验' in html and '不表示全蛋白' in html


def test_controller_persists_full_scope_clamps_remaining_time_and_does_not_resubmit(monkeypatch):
    from contextlib import nullcontext
    from test_m1_service_p4 import RecordedInputs
    from t01_phase1_real.development.workflow import service,confirmation
    class Controller(RecordedInputs):
        def __init__(self):
            super().__init__();self.ex={'nodes':copy.deepcopy(self.rows)};self.count=0
            self.ex['nodes']['wt_foldx']={'state':'ready'}
            self.parent=dict(job_id='parent',run_id='run',state='running',stop_reason=None,request_artifact={})
        def _tx(self):return nullcontext(None)
        def _job(self,*a):return self.parent
        def _execution(self,*a):return self.ex
        def _input(self,*a):return encode(self.body)
        def _stage(self,db,run,raw,tool):self.staged=decode(raw);return {}
        def _admit(self,*a):pass
        def _new_job(self,*a):self.count+=1;return {'job_id':'child'}
        def _execution_store(self,db,jid,ex):self.ex=ex
        def _store(self,*a):pass
    rt=Controller();req,reason=service.request_for(rt,rt.body,rt.rows,'wt_foldx')
    monkeypatch.setattr(confirmation,'elapsed',lambda ex:rt.body['timeout_seconds']-120)
    assert service._create_child(rt,'parent','wt_foldx',req)=='child'
    fact=copy.deepcopy(rt.ex['nodes']['wt_foldx']['scan_scope'])
    assert len(fact['positions'])==73 and rt.staged['scan_positions']==fact['positions']
    assert rt.staged['timeout_seconds']==120
    assert service._create_child(rt,'parent','wt_foldx',req)=='child' and rt.count==1
    service._record(rt,'parent','wt_foldx',dict(state='failed',job_id='child',error_code='TIMEOUT'))
    assert rt.ex['nodes']['wt_foldx']['scan_scope']==fact
    assert rt.ex['nodes']['wt_foldx']['error_code']=='TIMEOUT'
    rt.parent['stop_reason']='cancel'
    assert service._create_child(rt,'parent','wt_thermompnn',req) is None and rt.count==1
