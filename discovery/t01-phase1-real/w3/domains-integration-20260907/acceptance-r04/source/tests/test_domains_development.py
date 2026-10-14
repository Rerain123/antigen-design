"""N09 reference motifs, coordinates and source/lifecycle isolation."""
import copy
from pathlib import Path
import sys
import pytest
from t01_phase1_real.common import RuntimeFault,encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.domains import policy
from t01_phase1_real.development.domains.compute import compute,scan,L1,coordinates
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_domains_acceptance import database,entry,feature,SEQ
from t01_phase1_real.development.domains.geometry import geometry,core_state,contact_components


@pytest.mark.parametrize('seq,kind,start,end',[('AKKRKA','NLS',2,5),('ARRKRA','Furin',2,5),
    ('ALPATGA','Sortase',2,6),('ARGDA','RGD',2,4),('ADQEANPGPA','Picornavirus_2A',2,9)])
def test_independent_motif_coordinates(seq,kind,start,end):
    assert dict(type=kind,start=start,end=end,source='regex',confidence='low') in scan(seq)


def test_overlapping_motifs_not_lost():
    assert [(x['start'],x['end']) for x in scan('KKKKK') if x['type']=='NLS']==[(1,4),(2,5)]


@pytest.mark.parametrize('feature_type',list(L1))
def test_l1_exact_mapping(tmp_path,feature_type):
    body,_=database(tmp_path)
    out=compute(body,[entry(features=[feature(feature_type,1,5)])])
    assert any(d['type']==L1[feature_type] and d['confidence']=='high' for d in out['functional_domains'])


@pytest.mark.parametrize('text,kind',[('NUCLEAR LOCALIZATION','NLS'),('xxRBDxx','RBD'),('CAPSID protein','VLP_assembly')])
def test_l2_case_insensitive_substring(tmp_path,text,kind):
    body,_=database(tmp_path)
    out=compute(body,[entry(features=[feature('Other',1,5,text)])])
    assert any(d['type']==kind and d['confidence']=='medium' for d in out['functional_domains'])


def test_chain_does_not_double_remap(tmp_path):
    body,_=database(tmp_path);body['parent']=dict(id='parent',offset=25,sequence='A'*24+SEQ)
    audit=[]
    assert coordinates(feature('Chain',1,20),'mature',body,0,audit)==(1,20,'uniprot')
    assert coordinates(feature('Domain',25,35),'parent',body,0,audit)==(1,11,'uniprot_remapped')
    assert coordinates(feature('Chain',25,35),'parent',body,0,audit) is None


def test_coordinate_clipping_and_discard(tmp_path):
    body,_=database(tmp_path);body['parent']=dict(id='p',offset=10,sequence='A'*9+SEQ+'A'*9)
    audit=[]
    assert coordinates(feature('Domain',1,12),'parent',body,0,audit)==(1,3,'uniprot_remapped')
    assert coordinates(feature('Domain',1,5),'parent',body,0,audit) is None
    assert coordinates(feature('Domain',10,999),'parent',body,0,audit)==(1,len(SEQ),'uniprot_remapped')
    assert coordinates(feature('Domain',999,1000),'parent',body,0,audit) is None


def test_uncertain_feature_not_invented(tmp_path):
    body,_=database(tmp_path);f=feature('Domain',1,5);f['location']['start']['modifier']='UNKNOWN'
    value=compute(body,[entry(features=[f])])
    assert 'UNCERTAIN_FEATURE_COORDINATES' in value['review_reasons']


def test_exact_matching_multiple_and_unreviewed(tmp_path):
    body,_=database(tmp_path)
    value=compute(body,[entry(),entry(accession='SECOND')]);assert value['lookup']['status']=='ambiguous'
    unreviewed=entry();unreviewed['entryType']='UniProtKB unreviewed (TrEMBL)'
    value=compute(body,[unreviewed]);assert not any(x['source'].startswith('uniprot') for x in value['functional_domains'])
    assert 'UNREVIEWED_CONFIDENCE_DOWNGRADE_UNRESOLVED' in value['review_reasons']


def test_regex_overlap_at_80_percent_and_order_conflict(tmp_path):
    body,_=database(tmp_path);body['protein_sequence']='AAAAAKKRKAAAAAA'
    value=compute(body,[entry(seq=body['protein_sequence'],features=[feature('Domain',1,10)])])
    assert not any(x['source']=='regex' for x in value['functional_domains'])
    value=compute(body,[entry(seq=body['protein_sequence'],features=[feature('Domain',7,8)])])
    assert 'OVERLAP_SORT_ORDER_UNRESOLVED' in value['review_reasons']


def test_user_annotation_retains_identity(tmp_path):
    body,_=database(tmp_path);body['user_annotations']=[dict(type='domain',start=2,end=5,note='manual')]
    value=compute(body,[])
    assert dict(type='domain',start=2,end=5,source='user_annotation',confidence='user_high') in value['functional_domains']
    assert value['core_map'] is None


@pytest.mark.parametrize('change',[dict(protein_sequence='AX'),dict(database_id='../escape'),dict(timeout_seconds=True),
    dict(parent=dict(id='p',offset=2,sequence='AAAA')),dict(user_annotations=[dict(type='domain',start=0,end=2,note='')])])
def test_invalid_requests(tmp_path,change):
    body,_=database(tmp_path)
    with pytest.raises(RuntimeFault):policy.request(encode(dict(body,**change)))


def test_manifest_tamper(tmp_path):
    body,folder=database(tmp_path)
    receipt,_=policy.database(tmp_path,body);assert receipt['qualification']=='ENGINEERING_FIXTURE'
    (folder/'entries.json').write_bytes(b'[]')
    with pytest.raises(RuntimeFault):policy.database(tmp_path,body)


def test_submit_compute_idempotency_and_recovery(tmp_path):
    body,_=database(tmp_path/'data');rt=Runtime(tmp_path/'run',domains_database_root=tmp_path/'data')
    job=rt.submit_sequence(encode(body),'main',policy.TOOL);assert job['node_id']=='N09'
    assert rt.submit_sequence(encode(body),'main',policy.TOOL)['job_id']==job['job_id']
    final=rt.dispatch(job['job_id']);assert final['state']=='succeeded'
    assert rt.result(job['job_id'])['database']['qualification']=='ENGINEERING_FIXTURE'
    job=rt.submit_sequence(encode(body),'interrupted',policy.TOOL);rt._development_fault='interrupt_after_claim'
    rt.dispatch(job['job_id']);rt._development_fault=None
    rt.recover(job['job_id']);assert rt.get(job['job_id'])['error_code']=='INTERRUPTED'


def test_foreign_topology_reference_rejected(tmp_path):
    body,_=database(tmp_path/'data');rt=Runtime(tmp_path/'run',domains_database_root=tmp_path/'data')
    job=rt.submit_sequence(encode(body),'one',policy.TOOL);rt.dispatch(job['job_id'])
    body['topology_input']=dict(state='available',artifact=next(r for r in rt.get(job['job_id'])['artifacts'] if r['role']=='result'),reason_code=None)
    with pytest.raises(RuntimeFault):rt.submit_sequence(encode(body),'wrong-tool',policy.TOOL)


@pytest.mark.parametrize('values,expected',[((.8,.7,.6,True),'deep_critical'),((.8,.7,.6,False),'ordinary'),
    ((.49,None,None,None),'shallow'),((.5,.7,.6,True),'ordinary'),((None,1.,1.,True),None),((.9,None,1.,True),None)])
def test_core_numeric_rules(values,expected):assert core_state(*values)==expected


def test_graph_members_include_isolated_eligible_nodes():
    assert contact_components([{1},{0},set()],[3,3,3])==[[1,2],[3]]


def test_geometric_disulfide_strict_threshold_and_interface():
    def pdb(cb_distance):
        lines=[];serial=0
        for chain,values in [('A',[('CYS',0.),('CYS',cb_distance)]),('B',[('ALA',2.)])]:
            for pos,(name,x) in enumerate(values,1):
                for atom,dx,element in [('CA',-.5,'C'),('CB',0.,'C')]:
                    serial+=1
                    lines.append(f'ATOM  {serial:5d} {atom:^4s} {name} {chain}{pos:4d}    {x+dx:8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{10.:6.2f}          {element:>2s}  ')
        return ('\n'.join(lines)+'\nEND\n').encode()
    report=dict(input=dict(structure_artifact=dict(media_type='chemical/x-pdb')),rsa=None,
        mapping=dict(target_chain_id='A',model_index=0,entries=[dict(sequence_position=p,structure_residue=dict(
            chain_id='A',hetero_flag=' ',res_seq=p,insertion_code='',residue_name='CYS')) for p in (1,2)]))
    result=geometry(report,pdb(5.9))
    assert result['disulfide_pairs'][0]['start']==1 and result['disulfide_pairs'][0]['end']==2
    assert result['interface_positions']==[1,2]
    assert all(x['burial_score'] is None and x['core_state'] is None for x in result['components'])
    assert geometry(report,pdb(6.0))['disulfide_pairs']==[]


def test_deadline_and_cancel_after_claim(tmp_path,monkeypatch):
    from t01_phase1_real.development.domains import service
    body,_=database(tmp_path/'data');rt=Runtime(tmp_path/'run',domains_database_root=tmp_path/'data')
    job=rt.submit_sequence(encode(body),'deadline',policy.TOOL)
    times=iter([0.,61.]);monkeypatch.setattr(service.time,'perf_counter',lambda:next(times))
    final=rt.dispatch(job['job_id'])
    assert final['state']=='timed_out' and rt.result(job['job_id'])['analysis'] is None
    monkeypatch.undo()
    job=rt.submit_sequence(encode(body),'running-cancel',policy.TOOL);rt._development_fault='interrupt_after_claim'
    rt.dispatch(job['job_id']);rt._development_fault=None
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=job['job_id'],idempotency_key='cancel-claimed')))
    rt.recover(job['job_id']);assert rt.get(job['job_id'])['state']=='cancelled'
