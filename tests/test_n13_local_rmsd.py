"""Independent local RMSD reference and same-run evidence continuation guards."""
import copy
import numpy as np
import pytest
from Bio.PDB.qcprot import QCPSuperimposer
from t01_phase1_real.common import RuntimeFault
from t01_phase1_real.development.epitope_protection.compute import geometry,compare
from t01_phase1_real.development.workflow import m1,service,policy
from test_epitope_protection_development import side
from test_m1_service_p4 import RecordedInputs


def ledger(points):
    return {str(i):dict(atoms={'CA':list(map(float,p))},address=dict(chain_id='A',res_seq=100+i,insertion_code=''),
        raw_rows={'CA':i*5}) for i,p in enumerate(points,1)}


@pytest.mark.parametrize('seed',range(8))
def test_kabsch_against_independent_quaternion_reference(seed):
    rng=np.random.default_rng(seed);a=rng.normal(size=(20,3))*10
    b=a+rng.normal(size=a.shape)*2
    ref=QCPSuperimposer();ref.set(a,b);ref.run()
    observed=geometry(ledger(a),ledger(b),list(range(1,21)))
    assert observed['rmsd']==pytest.approx(ref.get_rms(),abs=1e-10)
    assert observed['fit_positions']==observed['score_positions']==list(range(1,21))
    assert observed['residues'][0]['wt_address']['res_seq']==101
    assert observed['residues'][0]['variant_raw_row']==5


@pytest.mark.parametrize('scale,passes',[(2.99,True),(3.01,False)])
def test_analytic_tetrahedron_threshold(scale,passes):
    a=np.array([[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1]],dtype=float)/np.sqrt(3)
    result=geometry(ledger(a),ledger(a*scale),[1,2,3,4])
    assert result['rmsd']==pytest.approx(scale-1,abs=1e-12)
    assert result['engineering_threshold_pass'] is passes and result['scientific_pass'] is None


def test_no_reflection_global_fit_or_silent_missing_positions():
    a=np.array([[1,1,1],[1,-1,-1],[-1,1,-1],[-1,-1,1]],dtype=float)
    mirrored=a.copy();mirrored[:,0]*=-1
    assert geometry(ledger(a),ledger(mirrored),[1,2,3,4])['rmsd']==pytest.approx(2.)
    w=ledger([*a,[100,100,100]]);v=ledger([*(a+[5,-8,10]),[-100,0,0]])
    assert geometry(w,v,[1,2,3,4])['rmsd']==pytest.approx(0,abs=1e-12)
    del v['3'];r=geometry(w,v,[1,2,3,4])
    assert r['value'] is None and r['missing_positions']==[3]


def test_degenerate_and_invalid_coordinates():
    g=ledger([[0,0,0],[1,0,0],[2,0,0]])
    assert geometry(g,g,[1,2,3])['reason']=='DEGENERATE_LOCAL_CA_GEOMETRY'
    for bad in (float('nan'),float('inf'),True):
        broken=copy.deepcopy(g);broken['1']['atoms']['CA'][0]=bad
        with pytest.raises(RuntimeFault):geometry(g,broken,[1,2,3])


def test_wt_functional_regions_do_not_require_variant_annotation_transfer():
    w=side();w['domains']=[dict(type='domain',start=1,end=3,source='uniprot')]
    v=side();v['domains']=None
    r=compare('AAA','AGA',dict(wt=w,variant=v))
    assert r['l3']['functional_rmsd']==pytest.approx(0,abs=1e-12)
    assert r['l3']['functional_reason'] is None
    del v['geometry']['2']
    r=compare('AAA','AGA',dict(wt=w,variant=v))
    assert r['l3']['functional_rmsd'] is None and r['l3']['functional_reason']=='FUNCTIONAL_DOMAIN_NOT_EVALUATED'


def test_hotspot_e4_union_same_for_l2_l3_and_missing_hotspot_not_pass():
    w=side();v=side();w['hotspots']=[dict(start=1,end=2,weighted_score=.6)];w['e4_positions']=[2,3]
    r=compare('AAA','AAA',dict(wt=w,variant=v))
    assert r['validation_positions']==r['l3']['hotspot']['score_positions']==[1,2,3]
    assert [x['position'] for x in r['l2']['residues']]==[1,2,3]
    w['hotspots']=None
    assert compare('AAA','AAA',dict(wt=w,variant=v))['l3']['hotspot']['value'] is None


def test_workflow_reuses_wt_blast_and_domains_and_requeries_variants():
    rt=RecordedInputs();b=rt.body
    wt,_=service.request_for(rt,b,rt.rows,'wt_epitope_map')
    assert wt['blast_input']==service.typed(rt,rt.rows,'blast')
    query,_=service.request_for(rt,b,rt.rows,'rep1_blast')
    assert query['protein_sequence']==m1.selected(rt,rt.rows)[0]['sequence']
    for k,v in b['analysis']['blast'].items():assert query[k]==v
    order=policy.order(b)
    assert order.index('rep1_blast')<order.index('rep1_epitope_map')<order.index('protection')
    # Recorded controller fixture: routing only, not new scientific evidence.
    rt.rows['rep1_blast']=rt.rows['blast']
    req,_=service.request_for(rt,b,rt.rows,'rep1_epitope_map')
    assert req['blast_input']==service.typed(rt,rt.rows,'rep1_blast')
    paired,_=service.request_for(rt,b,rt.rows,'protection')
    assert paired['pairs'][0]['wt']['domains']==service.source(rt,rt.rows.get('domains'))
    assert paired['pairs'][0]['variant']['domains'] is None
    b['analysis']['blast']=None
    assert service.request_for(rt,b,rt.rows,'rep1_blast')==(None,'DATABASE_NOT_PROVIDED')


def test_nested_receipt_run_guard():
    from t01_phase1_real.development.epitope_protection.source import same_run_receipts
    receipts=dict(epitope_map=dict(verified=True,run_id='current',predictors=dict(
        blast=dict(verified=True,run_id='current'))),domains=dict(verified=False))
    same_run_receipts(receipts,'current')
    receipts['epitope_map']['predictors']['blast']['run_id']='foreign'
    with pytest.raises(RuntimeFault,match='another run'):same_run_receipts(receipts,'current')


def test_iedb_prior_and_domain_source_survive_facts_without_hotspot_invention():
    from t01_phase1_real.development.epitope_protection.source import facts
    from test_iedb_evidence import SEQ,evidence,hsp
    from t01_phase1_real.development.blast.iedb import map_evidence
    prior=map_evidence(SEQ,[hsp()],evidence())
    source=dict(epitopes=dict(b_cell_antigenic_hotspot_map=dict(hotspots=None)),
        blast_similarity=dict(state='available',iedb_evidence=prior),binding=dict(rule_profile={'sha256':'a'*64}))
    domain=dict(lookup=dict(status='hit'),functional_domains=[dict(type='domain',start=2,end=8,source='uniprot')])
    observed=facts(dict(protein_sequence=SEQ,upstream=dict(structure=None)),{},
        dict(epitope_map=source,domains=dict(analysis=domain)),{})
    assert observed['iedb_prior']==prior and observed['hotspots'] is None
    assert observed['domains']==domain['functional_domains'] and observed['domain_analysis']==domain
    assert observed['e4_positions']==[]
    assert observed['iedb_prior']['epitope_regions'][0]['source_iedb_id']=='99'
