"""Guard the expert diagram's N12 -> N13 -> N14 -> N15 service route."""
import copy
import pytest
from t01_phase1_real.common import RuntimeFault,encode
from t01_phase1_real.development.workflow import m1,policy,service
from t01_phase1_real.development.epitope_protection import policy as n13
from test_m1_service_p4 import RecordedInputs


def test_policy_has_one_final_n15_and_independent_post_n15_branches():
    rt=RecordedInputs();order=policy.order(rt.body)
    assert order.index('design_audit')<order.index('preselection')<order.index('protection')
    assert order.index('protection')<order.index('stability')<order.index('variant_report')
    assert order.index('variant_report')<order.index('codon')<order.index('wt_foldx')
    assert order.index('codon')<order.index('local_delivery')
    assert order.index('wt_reference')<order.index('local_delivery')
    assert [(name,policy.NODES[name]) for name in order if policy.NODES[name]=='N15']==[('variant_report','N15')]
    assert policy.NODES['preselection']=='N12' and policy.NODES['protection']=='N13'
    assert policy.NODES['stability']=='N14'


def test_n13_reads_n12_fact_and_rejects_n15_or_foldx_source():
    rt=RecordedInputs();req,_=service.request_for(rt,rt.body,rt.rows,'protection')
    assert n13.request(encode(req))==req
    assert req['upstream']=={'design_audit':service.source(rt,rt.rows['design_audit'])}
    assert req['preselection']==rt.rows['preselection']['fact']
    for wrong in ('base_report','foldx'):
        bad=copy.deepcopy(req);bad['upstream'][wrong]=service.source(rt,rt.rows['base_report' if wrong=='base_report' else 'stability'])
        with pytest.raises(RuntimeFault):n13.request(encode(bad))
    bad=copy.deepcopy(req);bad['preselection']['records_sha256']='0'*64
    # The admission schema cannot trust a caller-supplied digest; the recursive
    # source replay rejects it before the N13 calculation is published.
    assert n13.request(encode(bad))==bad


def test_n14_and_n15_require_prior_real_results_and_preserve_wt_base():
    rt=RecordedInputs();rows=copy.deepcopy(rt.rows)
    stability,_=service.request_for(rt,rt.body,rows,'stability')
    assert stability['mode']=='buildmodel' and stability['structure_artifact']==service.source(rt,rows['structure'])['artifact']
    assert [r['variant_id'] for r in stability['variants']]==[r['id'] for r in m1.selected(rt,rows)]
    rows['protection']['state']='skipped'
    assert service.request_for(rt,rt.body,rows,'stability')==(None,'N13_NOT_COMPLETE')
    assert service.request_for(rt,rt.body,rows,'variant_report')==(None,'N13_OR_N14_NOT_COMPLETE')
    rows['protection']['state']='succeeded';rows['stability']['state']='skipped'
    assert service.request_for(rt,rt.body,rows,'variant_report')==(None,'N13_OR_N14_NOT_COMPLETE')
    rows['stability']['state']='succeeded'
    final,_=service.request_for(rt,rt.body,rows,'variant_report')
    assert final['upstream']['foldx']==service.source(rt,rows['stability'])
    assert final['n13_source']==service.source(rt,rows['protection'])
    assert len(final['foldx_bindings'])==len(m1.selected(rt,rows))


def test_n17_needs_n15_but_not_n16_and_n18_waits_both_branches():
    rt=RecordedInputs();rows=copy.deepcopy(rt.rows)
    rows['codon']=dict(state='skipped',reason_code='NO_QUALIFIED_CANDIDATE',job_id=None)
    rows['wt_reference']['state']='succeeded'
    wt,_=service.request_for(rt,rt.body,rows,'wt_foldx')
    assert wt['mode']=='positionscan' and wt['structure_artifact']==service.source(rt,rows['structure'])['artifact']
    assert 'codon' not in wt and 'n16' not in wt
    local,_=service.request_for(rt,rt.body,rows,'local_delivery')
    assert local['upstream']['variant_report']==service.source(rt,rows['variant_report'])
    assert local['upstream']['wt_reference']==service.source(rt,rows['wt_reference'])
    rows['codon']['state']='not_executed'
    with pytest.raises(RuntimeFault):service.request_for(rt,rt.body,rows,'local_delivery')
    rows['codon']['state']='skipped';rows['variant_report']['state']='skipped'
    assert service.request_for(rt,rt.body,rows,'wt_foldx')==(None,'N15_NOT_COMPLETE')
