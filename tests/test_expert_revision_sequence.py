"""Prestructure sequence observations: no models and no new science threshold."""
import copy
import pytest
from t01_phase1_real.common import sha, RuntimeFault
from t01_phase1_real.development.workflow import revision_sequence as seq, revision_sampling as sampling
from t01_phase1_real.development.developability.compute import expressibility
from test_expert_revision_v2 import record


def candidate(count=1):
    r=record(count)
    r.update(content_hash=sha(r['sequence'].encode()),candidate_id='c'+str(count),generation_source={'artifact_id':'fixture'})
    return r


def test_metrics_required_before_structure_without_new_threshold_or_order():
    a,b=candidate(1),candidate(2)
    scores={r['candidate_id']:dict(check_status='PASS',score=-1.) for r in (a,b)}
    assert sampling.select_structure([b,a],scores,2,require_sequence_metrics=True)==[]
    assert sampling.select_structure([b,a],scores,1)==['c1']  # v1 unchanged
    seq.attach([b,a])
    assert a['sequence_developability']['expressibility']==expressibility(a['sequence'])
    assert a['sequence_developability']['threshold_applied'] is False
    assert sampling.select_structure([b,a],scores,2,require_sequence_metrics=True)==['c1','c2']
    scores['c2']['score']=0.
    assert sampling.select_structure([a,b],scores,1,require_sequence_metrics=True)==['c2']


@pytest.mark.parametrize('damage',['metrics','hash','source','config','identity'])
def test_sequence_provenance_and_observation_tamper_rejected(damage):
    r=candidate();seq.attach([r])
    if damage=='metrics':r['sequence_developability']['expressibility']['score']=99.
    elif damage=='hash':r['sequence']='A'*100
    elif damage=='source':r['generation_source']={'artifact_id':'foreign'}
    elif damage=='config':r['calculation_config_id']='foreign'
    else:r['candidate_id']='foreign'
    with pytest.raises(RuntimeFault):seq.ready(r)


def test_cache_does_not_share_mutable_values_and_invalid_observation_stops(monkeypatch):
    a=candidate();seq.attach([a]);b=candidate();seq.attach([b]);before=copy.deepcopy(b)
    a['sequence_developability']['expressibility']['score']=99.
    assert b==before and seq.ready(b)
    seq._metrics.cache_clear()
    from t01_phase1_real.development.developability import compute
    monkeypatch.setattr(compute,'expressibility',lambda _:dict(status='computed_unreviewed',score=float('nan')))
    with pytest.raises(RuntimeFault,match='incomplete'):seq.attach([candidate()])
    seq._metrics.cache_clear()


def test_rejected_and_duplicate_records_do_not_compute(monkeypatch):
    def fail(*a):pytest.fail('must not compute excluded records')
    monkeypatch.setattr(seq,'observation',fail)
    rows=[dict(disposition=s) for s in ('REJECTED','DUPLICATE','WT_CONTROL')]
    seq.attach(rows)
    assert all('sequence_developability' not in r for r in rows)
