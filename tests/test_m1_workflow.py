"""M1 routing contracts; fixtures here are not native computation evidence."""
import copy
import pytest

from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.workflow import policy, service
from test_local_workflow import body, run
from test_proteinmpnn_development import request as mpnn_request


def m1_body():
    b=body()
    n11=mpnn_request(b['protein_sequence'])
    b['m1_test']={k:n11[k] for k in ('constraints','n_designs','sampling_temperature','seed','timeout_seconds')}
    return b


@pytest.mark.parametrize('change',['implicit','extra','reuse','duplicate','missing','temperature','seed','count'])
def test_reject_implicit_or_incomplete_design_input(change):
    b=m1_body();opt=b['m1_test']
    if change=='implicit':b['m1_test']=True
    elif change=='extra':opt['scientific_release_gate']='OPEN'
    elif change=='reuse':b['reuse_jobs']['structure']='t01p1r-job-'+'a'*32
    elif change=='duplicate':opt['constraints']['open_positions'].append(1)
    elif change=='missing':opt['constraints']['open_positions'].pop()
    elif change=='temperature':opt['sampling_temperature']=0.5
    elif change=='seed':opt['seed']=0
    else:opt['n_designs']=25
    with pytest.raises(RuntimeFault):policy.request(encode(b))


class GateRuntime:
    def __init__(self,status='SUITABLE_FOR_DESIGN',constraints=None):
        self.gate=dict(status=status,constraints=constraints or [],design_skip_reason='membrane_expected_poor')

    def result(self,jid):
        return dict(draft=dict(gate=self.gate))

    def get(self,jid):
        return dict(job_id=jid,artifacts=[mpnn_request()['structure_artifact']])


ROWS=dict(wt_draft=dict(state='succeeded',job_id='wt'),structure=dict(state='succeeded',job_id='structure'))


def test_explicit_route_invokes_existing_mpnn_and_default_stays_closed():
    b=policy.request(encode(m1_body()));rt=GateRuntime()
    req,reason=service.request_for(rt,b,ROWS,'design')
    assert reason is None and req['constraints']==b['m1_test']['constraints']
    assert service.worker('design').TOOL=='t01.real.proteinmpnn'
    assert service.worker('design').request(encode(req))==req
    assert service.request_for(rt,body(),ROWS,'design')==(None,'DESIGN_CONSTRAINTS_NOT_REGISTERED')
    assert rt.gate['status']=='SUITABLE_FOR_DESIGN'


@pytest.mark.parametrize('status,constraints,reason',[
    ('NOT_SUITABLE_FOR_DESIGN',[],'R57_MEMBRANE_DESIGN_SKIPPED'),
    ('INPUT_INSUFFICIENT_OR_NOT_EVALUATED',[],'DESIGN_APPLICABILITY_INPUT_INSUFFICIENT'),
    ('SUITABLE_FOR_DESIGN',['EXTRACELLULAR_ONLY'],'M1_DESIGN_DOMAIN_NOT_SUPPORTED')])
def test_m1_does_not_override_known_inapplicability_or_required_input(status,constraints,reason):
    assert service.request_for(GateRuntime(status,constraints),m1_body(),ROWS,'design')==(None,reason)


def test_missing_databases_remain_unavailable_and_no_hit_is_not_inferred(tmp_path):
    rt=Runtime(tmp_path);j=run(rt,m1_body());snap=rt.workflow(j['job_id'])
    assert snap['internal_test']==dict(selected=True,eligible_for_n11=False,scope='M1_P1_P3_SAME_RUN')
    assert snap['nodes']['blast']['state']=='unavailable'
    # No N04/N05 input: N06 really fails. The M1 controller must retain that
    # failure and stop before scheduling later database/design nodes.
    assert j['state']=='failed' and snap['nodes']['epitope_map']['state']=='failed'
    assert all(snap['nodes'][name]['state']=='not_executed' for name in ('homology','domains'))
    assert snap['nodes']['design']['job_id'] is None
    assert snap['scientific_release_gate']=='CLOSED' and not snap['usable_for_pipeline']


@pytest.mark.parametrize('foreign_sequence',[False,True])
def test_m1_rejects_wrong_run_even_same_sequence(tmp_path,foreign_sequence):
    rt=Runtime(tmp_path);j=run(rt)
    child=rt.workflow(j['job_id'])['nodes']['glycosylation']['job_id']
    b=m1_body()
    if foreign_sequence:b['protein_sequence']='A'*len(b['protein_sequence'])
    with pytest.raises(RuntimeFault) as exc:
        service.verified(rt,b,'glycosylation',child,'t01p1r-run-'+'f'*32)
    assert exc.value.code=='FORBIDDEN'
    if foreign_sequence:
        with pytest.raises(RuntimeFault) as exc:
            service.verified(rt,b,'glycosylation',child,j['run_id'])
        assert exc.value.code=='OUTPUT_INVALID'
    else:
        assert service.verified(rt,b,'glycosylation',child,j['run_id'])['state']=='succeeded'


def test_m1_upstream_hash_tamper_is_fatal(tmp_path):
    rt=Runtime(tmp_path);j=run(rt)
    child=rt.workflow(j['job_id'])['nodes']['glycosylation']['job_id']
    ref=rt.get(child)['artifacts'][0]
    with rt._db() as db:
        path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(b'tampered')
    with pytest.raises(RuntimeFault):service.verified(rt,m1_body(),'glycosylation',child,j['run_id'])


def test_mask_change_conflicts_with_idempotency_key(tmp_path):
    rt=Runtime(tmp_path);b=m1_body();rt.submit_workflow(encode(b),'same')
    changed=copy.deepcopy(b);changed['m1_test']['seed']+=1
    with pytest.raises(RuntimeFault) as exc:rt.submit_workflow(encode(changed),'same')
    assert exc.value.code=='IDEMPOTENCY_CONFLICT'
