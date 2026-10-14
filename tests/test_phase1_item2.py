"""Expert item 2: complete partitions, truthful missing branches and S-19 math."""
import copy
import hashlib

import pytest

from t01_phase1_real.common import RuntimeFault, encode, new_id, now, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.netmhc import pan, policy, service
from t01_phase1_real.development.epitope_map.composition import synthesize
from t01_phase1_real.development.blast.iedb import complex_contacts, map_evidence

SEQ='ACDEFGHIKLMNPQRSTVWY'


def small_panel():
    p=copy.deepcopy(pan.manifest())
    for kind,count in [('mhc_i',21),('mhc_ii',16)]:
        p['channels'][kind]['alleles']=p['channels'][kind]['alleles'][:count]
        p['channels'][kind]['count']=count
    p.pop('sha256');p['sha256']=sha(encode(p));return p


def test_pan_inventory_all_alleles_and_bounded_lossless_partitions():
    p=pan.manifest()
    assert [p['channels'][k]['count'] for k in ('mhc_i','mhc_ii')]==[12642,11069]
    assert p['channels']['mhc_i']['availability']['declared_count']==12651
    assert len(p['channels']['mhc_i']['availability']['excluded_alleles'])==9
    for seq in [SEQ,'A'*999]:
        batches=pan.batches(seq,p)
        for kind,lengths,limit in [('mhc_i',policy.MHC_I_LENGTHS,20),('mhc_ii',policy.MHC_II_LENGTHS,15)]:
            names=[a for b in batches for a in b[kind+'_alleles']]
            assert names==p['channels'][kind]['alleles']
            assert all(1<=len(b[kind+'_alleles'])<=limit and
                len(b[kind+'_alleles'])*sum(len(seq)-n+1 for n in lengths)<=policy.MAX_CHANNEL_ROWS for b in batches)
    with pytest.raises(RuntimeFault,match='partitioned'):pan.batches('A'*20000,p)
    body=dict(protein_sequence=SEQ,user_sequence_id='test',host_species='Sus scrofa',**pan.options())
    assert policy.request(encode(body))==body
    body['panel_manifest_sha256']='0'*64
    with pytest.raises(RuntimeFault,match='inventory'):policy.request(encode(body))


def test_executable_support_receipt_is_reproducible_from_original_archives():
    import json
    import sys
    from t01_phase1_real.common import REPO
    sys.path.insert(0,str(REPO/'scripts'))
    from build_netmhc_pan_support import build
    assert build()==json.loads((policy.HERE/'pan-support.json').read_bytes())


def channel(seq,kind,names):
    lengths=policy.MHC_I_LENGTHS if kind=='mhc_i' else policy.MHC_II_LENGTHS
    inventory=policy.allele_inventory(kind)
    rows=[dict(start=i+1,end=i+n,peptide_seq=seq[i:i+n],allele=inventory[a],percent_rank=.1+i,
               classification='SB' if i==0 else 'NB',core=seq[i:i+9])
          for a in names for n in lengths for i in range(len(seq)-n+1)]
    return dict(status='parsed_unreviewed',hits=rows,observed_rows=len(rows),skipped_inverted_rows=0)


def test_pan_aggregate_exact_grid_and_incomplete_channel():
    p=small_panel();rows=[]
    for part in pan.batches(SEQ,p):
        req=dict(protein_sequence=SEQ,**{k+'_alleles':part[k+'_alleles'] for k in p['channels']})
        r=dict(binding=dict(sequence_sha256=sha(SEQ.encode())),panel_selection=dict(mode='explicit_alleles'),
               channels={k:channel(SEQ,k,req[k+'_alleles']) for k in p['channels']})
        rows.append((req,r,dict(job_id=str(part['index']))))
    channels,refs=pan.aggregate(SEQ,p,iter(rows))
    assert len(refs)==2 and channels['mhc_i']['hits'] is None
    assert len(next(pan.summary_sb(channels['mhc_i']['residue_summary'],len(SEQ))))==21
    with pytest.raises(RuntimeFault,match='incomplete'):pan.aggregate(SEQ,p,rows[:-1])
    bad=copy.deepcopy(rows);bad[0][0]['mhc_i_alleles'].reverse()
    with pytest.raises(RuntimeFault,match='partition'):pan.aggregate(SEQ,p,bad)
    bad=copy.deepcopy(rows);bad[0][1]['channels']['mhc_i']['status']='partial'
    out,_=pan.aggregate(SEQ,p,bad)
    assert out['mhc_i']['status']=='unavailable' and out['mhc_i']['residue_summary'] is None
    assert out['mhc_ii']['status']=='parsed_unreviewed'


def finish_fixture(rt,jid):
    before=rt.get(jid);body=policy.request(rt._request_bytes(before));j=copy.deepcopy(before)
    j.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
    with rt._tx() as db:rt._store(db,j,before,'test_fixture_claim')
    binding={k:j[k] for k in ('run_id','job_id','attempt_id','execution_identity','execution_profile')}
    binding['sequence_sha256']=sha(body['protein_sequence'].encode())
    result=dict(tool_id=policy.TOOL,binding=binding,usable_for_pipeline=False,automatic_handoff=False,
        panel_selection=dict(mode='explicit_alleles'),execution=dict(error_code=None,exit_code=0,stopped_confirmed=True),
        channels={k:channel(body['protein_sequence'],k,body[k+'_alleles']) for k in ('mhc_i','mhc_ii')})
    return rt._finish_development(jid,dict(tree_stopped=True),{},result)


def test_pan_resume_idempotency_recursive_evidence_and_cancel(tmp_path,monkeypatch):
    p=small_panel();monkeypatch.setattr(pan,'manifest',lambda:p);monkeypatch.setattr(service,'manifest',lambda:p)
    rt=Runtime(tmp_path/'rt');original=rt.dispatch
    monkeypatch.setattr(rt,'dispatch',lambda jid: original(jid) if service.selected(rt,rt.get(jid)) else rt.get(jid))
    body=dict(protein_sequence=SEQ,user_sequence_id='fixture',host_species='pig',**pan.options())
    parent=rt.submit_sequence(encode(body),'pan',policy.TOOL)
    assert rt.submit_sequence(encode(body),'pan',policy.TOOL)==parent
    rt.dispatch(parent['job_id']);ids=rt.execution(parent['job_id'])['batches'];assert len(ids)==1
    rt.recover(parent['job_id']);assert rt.execution(parent['job_id'])['batches']==ids
    finish_fixture(rt,ids[0]);rt.recover(parent['job_id'])
    ids=rt.execution(parent['job_id'])['batches'];assert len(ids)==2
    finish_fixture(rt,ids[1]);rt.recover(parent['job_id'])
    final=rt.get(parent['job_id']);assert final['state']=='succeeded'
    result=rt.result(final['job_id']);assert result['panel_selection']['completed_batches']==2
    assert result['panel_selection']['pan_allele_warning'] and not result['usable_for_pipeline']
    service.verify_sources(rt,final,result)
    altered=copy.deepcopy(result);altered['channels']['mhc_i']['residue_summary']['min_percent_rank'][0]=50
    with pytest.raises(RuntimeFault,match='aggregate differs'):service.verify_sources(rt,final,altered)
    other=rt.submit_sequence(encode(body),'cancel-pan',policy.TOOL);rt.dispatch(other['job_id'])
    rt.control(encode(dict(contract_version='0.1.0',operation='cancel',job_id=other['job_id'],idempotency_key='stop-pan')))
    rt.recover(other['job_id'])
    assert rt.get(other['job_id'])['state']=='cancelled'
    assert all(rt.get(j)['state']=='cancelled' for j in rt.execution(other['job_id'])['batches'])


def test_pan_storage_failure_does_not_launch_a_subset_and_workflow_continues(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from test_local_workflow import body as workflow_body,run
    monkeypatch.setattr(service.shutil,'disk_usage',lambda _:SimpleNamespace(free=1))
    rt=Runtime(tmp_path/'rt');body=workflow_body();body['analysis']['netmhc']=pan.options()
    final=run(rt,body)
    assert final['state']=='succeeded'
    nodes=rt.workflow(final['job_id'])['nodes'];parent=rt.get(nodes['netmhc']['job_id'])
    assert parent['state']=='failed' and parent['error_code']=='ASSET_MISSING'
    assert rt.execution(parent['job_id'])['batches']==[]
    assert nodes['glycosylation']['state']==nodes['local_delivery']['state']=='succeeded'


def test_pan_deadline_stops_active_native_child(tmp_path,monkeypatch):
    panel=small_panel();monkeypatch.setattr(pan,'manifest',lambda:panel);monkeypatch.setattr(service,'manifest',lambda:panel)
    rt=Runtime(tmp_path/'rt');original=rt.dispatch
    monkeypatch.setattr(rt,'dispatch',lambda jid:original(jid) if service.selected(rt,rt.get(jid)) else rt.get(jid))
    body=dict(protein_sequence=SEQ,user_sequence_id='deadline-fixture',host_species='pig',**pan.options(1))
    job=rt.submit_sequence(encode(body),'deadline-pan',policy.TOOL);rt.dispatch(job['job_id'])
    with rt._tx() as db:
        ex=rt._execution(db,job['job_id']);ex['started_at']='2000-01-01T00:00:00Z';rt._execution_store(db,job['job_id'],ex)
    rt.recover(job['job_id'])
    assert rt.get(job['job_id'])['state']=='timed_out'
    assert all(rt.get(j)['state']=='cancelled' for j in rt.execution(job['job_id'])['batches'])


def tmap(regions,rank):
    return dict(presentation_hotspots=[],evidence_regions=regions,residue_inverse_minmax_score=rank)


def test_s19_weights_highest_evidence_overlap_threshold_and_topology():
    r=lambda start,end,level:dict(start=start,end=end,epitope_level=level)
    t=tmap([r(1,20,'E1-single'),r(1,10,'E3-region'),r(1,10,'E3-region')],[1]*20)
    c=synthesize(20,None,t,['outside']+['inside']*19)
    assert c['density']==[.8]*10+[.2]*10
    assert c['hotspots']==[dict(start=1,end=10,weighted_score=.8,in_outside_region=True)]
    assert c['channel_weights']=={'tcell':1}
    assert synthesize(20,None,tmap([r(1,20,'E2-consensus')],[1]*20))['hotspots']==[]
    assert synthesize(20,None,tmap([r(1,7,'E4-contact')],[1]*20))['hotspots']==[]
    assert synthesize(20,None,tmap([r(1,20,'E3-region')],None))['density'] is None
    with pytest.raises(RuntimeFault):synthesize(20,None,None)


def test_s19_bcell_unknown_is_not_silently_zero():
    c=synthesize(20,dict(selected_project_score=None,regions=None),tmap([],None))
    assert c['density'] is None and c['channel_density']['tcell']==[0]*20
    assert c['channel_weights']==dict(bcell=.5,tcell=.5)


def test_s19_explicit_threshold_weights_and_default_bound_are_separate():
    from t01_phase1_real.development.epitope_map.composition import settings
    from t01_phase1_real.development.epitope_map.result import _empty_hotspot_proof
    t=tmap([dict(start=1,end=20,epitope_level='E2-consensus')],[1]*20)
    custom=dict(channel_weights=dict(bcell=.8,tcell=.2),hotspot_threshold=.3)
    calculated=synthesize(20,None,t,parameters=custom)
    assert calculated['channel_weights']==dict(tcell=1)
    assert calculated['hotspots']==[dict(start=1,end=20,weighted_score=.5)]
    assert _empty_hotspot_proof(None,t,custom) is None
    assert _empty_hotspot_proof(None,t,settings())['hotspot_threshold']==.5
    custom['channel_weights']=dict(bcell=0,tcell=1)
    assert synthesize(20,dict(selected_project_score=None),t,parameters=custom)['density']==[.5]*20
    for threshold in (.299,.701,True,float('nan')):
        with pytest.raises(RuntimeFault):settings(dict(custom,hotspot_threshold=threshold))
    with pytest.raises(RuntimeFault):settings(dict(custom,channel_weights=dict(bcell=.8,tcell=.8)))


def test_s19_configured_request_is_persisted_and_non20_window_stays_closed(tmp_path):
    from test_epitope_map_development import finish_source,SEQ as sequence
    from t01_phase1_real.development.epitope_map import policy as mapping
    rt=Runtime(tmp_path/'rt');native=finish_source(rt,policy.TOOL,'configured-source-fixture')
    parameters=dict(channel_weights=dict(bcell=.5,tcell=.5),hotspot_threshold=.3)
    body=dict(protein_sequence=sequence,user_sequence_id='configured-engineering-fixture',timeout_seconds=30,
        bepipred_input=dict(state='not_provided',artifact=None,reason_code=None),
        netmhc_input=rt.source_input(native['job_id'],policy.TOOL),
        blast_input=dict(state='not_executed',artifact=None,reason_code='ENGINEERING_FIXTURE'),
        composition_parameters=parameters)
    job=rt.submit_sequence_in_run(native['run_id'],encode(body),'configured',mapping.TOOL)
    assert rt.dispatch(job['job_id'])['state']=='succeeded'
    result=rt.result(job['job_id'])
    assert result['method_summary']['composition_parameters']==parameters
    assert result['epitopes']['b_cell_antigenic_hotspot_map']['hotspots']==[dict(start=1,end=9,weighted_score=.5)]
    context=rt.n06_hotspot_input(job['job_id'],sequence)
    assert context['hotspots'] is None and context['reason_code']=='OI_029_WINDOW_CONVERSION_REQUIRED'


def atom(serial,residue,chain,resseq,x,icode='',element='C'):
    return f'ATOM  {serial:5d}  CA  {residue:3s} {chain}{resseq:4d}{icode or " "}   {x:8.3f}{0:8.3f}{0:8.3f}{1:6.2f}{20:6.2f}          {element:>2s}\n'


def complex_package(x=4):
    pdb=atom(1,'ALA','A',7,0,'B')+atom(2,'CYS','A',8,20)+atom(3,'GLY','B',1,x)
    return dict(pdb_text=pdb,coordinate_sha256=hashlib.sha256(pdb.encode()).hexdigest(),
        source_iedb_id='99',subject_id='iedb_1',complex_id='12',reference_id='456',
        residue_map=[dict(chain='A',resseq=7,icode='B',residue='A',subject_position=1),
                     dict(chain='A',resseq=8,icode='',residue='C',subject_position=2)])


def test_e4_heavy_atoms_cutoff_original_address_fallback_and_hash():
    p=complex_package();rows,notes=complex_contacts(p,dict(ant_pdb_chain='A'),'AC')
    assert len(rows)==1 and rows[0]['minimum_heavy_atom_distance_angstrom']==4
    assert (rows[0]['chain'],rows[0]['resseq'],rows[0]['icode'],rows[0]['evidence_source'])==('A',7,'B','99')
    assert not notes
    assert not complex_contacts(complex_package(4.001),dict(ant_pdb_chain='A'),'AC')[0]
    rows,notes=complex_contacts(p,{},'AC');assert rows and notes[0]['code']=='IEDB_SHORTER_CHAIN_ANTIBODY_ASSUMPTION'
    p['pdb_text']+='REMARK changed\n'
    with pytest.raises(ValueError,match='digest'):complex_contacts(p,{},'AC')


def test_e4_excludes_hydrogen_and_does_not_invent_ambiguous_chain_roles():
    p=complex_package(40)
    p['pdb_text']+=atom(4,'GLY','B',1,1,element='H').replace('  CA ','  H  ')
    p['coordinate_sha256']=hashlib.sha256(p['pdb_text'].encode()).hexdigest()
    assert not complex_contacts(p,dict(ant_pdb_chain='A'),'AC')[0]
    p=complex_package()
    p['pdb_text']+=atom(4,'ALA','B',2,30)
    p['coordinate_sha256']=hashlib.sha256(p['pdb_text'].encode()).hexdigest()
    rows,notes=complex_contacts(p,{},'AC')
    assert rows==[] and notes==[dict(code='IEDB_COMPLEX_CHAIN_ROLE_UNRESOLVED')]


def test_e4_contacts_transfer_to_query_and_keep_source():
    from test_iedb_evidence import evidence,hsp
    e=evidence();p=complex_package();e['complex_coordinates']=[p]
    e['structures']=[dict(subject_id='iedb_1',complex_id='12',ant_pdb_chain='A',reference_id='456')]
    r=map_evidence(SEQ,[hsp()],e)
    assert r['e4_status']=='computed'
    assert r['contact_residues'][0]['sequence_position']==1
    assert r['contact_residues'][0]['reference_id']=='456'
    e['structures'][0]['reference_id']='another-publication'
    with pytest.raises(ValueError,match='bound to the IEDB metadata'):map_evidence(SEQ,[hsp()],e)


def test_n06_tcell_literature_computes_real_density_and_nonempty_hotspot():
    from test_epitope_map_development import _source_result, SEQ as sequence
    def source(tool):
        return _source_result(dict(tool_id=tool,run_id='run',request_id='request',job_id='job',attempt_id='attempt',
            execution_identity='exec',execution_profile={},request_artifact=dict(sha256='0'*64)))
    from t01_phase1_real.development.epitope_map.result import compute
    blast=source('t01.real.blast');mhc=source('t01.real.netmhc')
    prior=dict(database_id='engineering-n03',iedb_hit=True,evidence_level='literature_supported',
        epitope_regions=[dict(start=1,end=9,e_level='E3-region',source_iedb_id='99',reference_id='123',epitope_type='T')],
        contact_residues=[])
    blast.update(scope='N03_LOCAL_IEDB_PRIOR',iedb_prior=prior)
    blast['search'].update({n:prior[n] for n in ('iedb_hit','evidence_level','epitope_regions','contact_residues')})
    body=dict(protein_sequence=sequence,blast_input=dict(state='available',artifact=dict(sha256='a'*64),reason_code=None))
    topology=dict(binding=dict(sequence_sha256=sha(sequence.encode())),topology=dict(labels=['outside']*len(sequence)))
    r=compute(body,dict(blast=blast,netmhc=mhc,topology=topology))
    h=r['epitopes']['b_cell_antigenic_hotspot_map']
    assert h['proof'] is None and h['status']=='computed_unreviewed'
    assert h['hotspots']==[dict(start=1,end=9,weighted_score=.8,in_outside_region=True)]
    assert r['epitopes']['density_per_residue'][:9]==[.8]*9
    assert not any(w['code']=='IEDB_WEIGHTED_HOTSPOT_REVIEW_REQUIRED' for w in r['warnings'])


def test_overlay_scoped_immutable_preserves_worker_and_resource_settings():
    import sys
    from t01_phase1_real.common import REPO
    sys.path.insert(0,str(REPO/'scripts'))
    import prepare_phase1_item2 as deploy
    from test_n13_deployment import live
    before=live();before['spec']['template']['spec']['containers'].append(
        dict(name='worker-blast',volumeMounts=[dict(name='db',mountPath='/database',readOnly=True)]))
    original=copy.deepcopy(before);cm,patch,rollback=deploy.render(before)
    assert before==original and cm['immutable']
    assert len(cm['binaryData'])==len(deploy.FILES)
    assert all('resources' not in op['path'] and 'image' not in op['path'] for op in patch)
    assert all(m['readOnly'] for op in patch if op['op']=='replace' for m in op['value'])
    assert patch[:2]==[dict(op='test',path='/metadata/uid',value='test-uid'),
                      dict(op='test',path='/metadata/resourceVersion',value='42')]
    assert rollback
