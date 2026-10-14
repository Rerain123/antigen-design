"""Controller contracts; archived inputs validate schemas, not new computation."""
import copy
import pytest
from t01_phase1_real.common import REPO,decode,encode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import service,policy,m1
from t01_phase1_real.development.variant_report.m1 import selection
from test_local_workflow import run
from test_m1_workflow import m1_body


class RecordedInputs:
    def __init__(self):
        p1=REPO/'discovery/t01-phase1-real/m1-p1-20260921/r01'
        p2=REPO/'discovery/t01-phase1-real/m1-p2-20260921/r01'
        self.body=policy.request(encode(decode((p1/'batch.json').read_bytes())['request']))
        names=dict(rescore='esm-if1',design_audit='design-audit',selection_report='selection-report',
            stability='foldx-extended',base_report='base-report',protection='protection',variant_report='final-report')
        self.records={p.stem:decode(p.read_bytes()) for p in p1.glob('*.json') if p.stem in policy.ORDER}
        self.records.update({n:decode((p2/(f+'.json')).read_bytes()) for n,f in names.items()})
        numbers=decode((p2/'selection.json').read_bytes())['sample_numbers']
        for label,stem in [('wt','wt')]+[('rep'+str(i),'sample-'+str(n)) for i,n in enumerate(numbers,1)]:
            for kind in m1.REASSESS+(('prediction','structure') if label!='wt' else ()):
                self.records[label+'_'+kind]=decode((p2/(stem+'-'+kind.replace('_','-')+'.json')).read_bytes())
        self.rows={n:dict(job_id=r['job']['job_id'],state='succeeded') for n,r in self.records.items()}
        self.jobs={r['job']['job_id']:r for r in self.records.values()}
        source=service.source(self,self.rows['design_audit'])
        recorded=self.records['selection_report']['result']['report']['records']
        projection=[{k:r[k] for k in ('id','sample_number','sequence','sequence_sha256','mutations',
            'esm_if1','disposition','exclusion_reasons')} for r in recorded]
        numbers=selection(recorded)
        self.rows['preselection']=dict(state='succeeded',job_id=None,origin='INTERNAL_FACT',fact=dict(
            kind='N12_REPRESENTATIVE_PRESELECTION',source=source,sample_numbers=numbers,
            records_sha256=sha(encode(projection)),total_records=len(recorded),
            selected=[next(r for r in projection if r['sample_number']==n) for n in numbers],
            scientific_eligible=False))

    def get(self,jid):return self.jobs[jid]['job']
    def result(self,jid):return self.jobs[jid]['result']
    def n06_hotspot_input(self,jid,seq):
        for n,row in self.records.items():
            if n.endswith('_glycosylation') and row['request']['protein_sequence']==seq:
                return row['request']['hotspot_input']
        raise AssertionError('No recorded glycosylation request')


def test_all_m1_child_requests_use_registered_tool_contracts():
    rt=RecordedInputs();b=rt.body
    for name in m1.TAIL:
        if name.endswith('_structure') or name in ('local_delivery',):continue
        request,reason=service.request_for(rt,b,rt.rows,name)
        if request is not None:
            assert service.worker(name,b).request(encode(request))==request,name
    assert service.request_for(rt,b,rt.rows,'codon')==(None,'NO_QUALIFIED_CANDIDATE')
    assert all(n in policy.NODES for n in policy.order(b))
    assert len(policy.order(b))==len(set(policy.order(b)))
    assert not {'selection_report','base_report'} & set(policy.order(b))


def test_m1_real_failure_is_parent_failure_without_export(tmp_path):
    rt=Runtime(tmp_path);rt._development_fault='compute_failure'
    j=run(rt,m1_body())
    assert j['state']=='failed' and j['error_code']=='TOOL_FAILED'
    result=rt.result(j['job_id'])
    assert all(r['path']!='output/package.zip' for r in result['raw_artifacts'])
    rows=result['workflow']['nodes']
    assert rows['epitope_map']['state']=='failed' and rows['design']['job_id'] is None
    assert rt.execution(j['job_id'])['tree_stopped']


def test_m1_cancel_fences_active_child_and_export(tmp_path,monkeypatch):
    rt=Runtime(tmp_path);j=rt.submit_workflow(encode(m1_body()),'cancel');original=rt.dispatch
    def dispatch(jid):
        if rt.get(jid)['tool_id']=='t01.real.epitope_map':
            rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=j['job_id'],idempotency_key='stop')))
        return original(jid)
    monkeypatch.setattr(rt,'dispatch',dispatch)
    end=rt.dispatch(j['job_id']);assert end['state']=='cancelled'
    assert not any(r['path']=='output/package.zip' for r in rt.result(j['job_id'])['raw_artifacts'])
    assert all(rt.get(r['job_id'])['state'] in ('succeeded','failed','cancelled','timed_out')
               for r in rt.execution(j['job_id'])['nodes'].values() if r.get('job_id'))


def test_representative_sequence_is_selected_from_internal_n12_fact():
    rt=RecordedInputs();b=rt.body
    seq=m1.sequence(rt,b,rt.rows,'rep1_prediction')
    assert seq!=b['protein_sequence'] and seq==m1.selected(rt,rt.rows)[0]['sequence']
    with pytest.raises(RuntimeFault):m1.sequence(rt,b,{},'rep1_prediction')


def test_m1_timeout_budget_is_explicit_and_bounded():
    b=m1_body();b['timeout_seconds']=28800;policy.request(encode(b))
    b['timeout_seconds']+=1
    with pytest.raises(RuntimeFault):policy.request(encode(b))


def test_wt_draft_is_initial_gate_not_representative_reassessment():
    rt=RecordedInputs();rows={k:v for k,v in rt.rows.items() if k in policy.ORDER[:10]}
    request,reason=service.request_for(rt,rt.body,rows,'wt_draft')
    assert reason is None and request['upstream']['structure'] is not None
    assert service.worker('wt_draft').request(encode(request))==request
