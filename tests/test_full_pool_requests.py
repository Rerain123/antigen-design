"""Full-pool capacity without relaxing source identity or other tools."""
import pytest
from t01_phase1_real.common import RuntimeFault,encode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.epitope_protection import policy


def full_body(rt):
    from test_epitope_protection_development import local_request
    b=local_request(rt);fact=b['preselection']
    fact['selection_scope']='ALL_VALIDATED'
    fact['validation_source']=dict(workflow_job_id='fixture',node='validation')
    fact['sample_numbers']=list(range(1,65))
    fact['selected']=[dict(id='s'+str(i),sample_number=i,sequence='A'*999,validation={'synthetic_capacity_only':'x'*2000}) for i in range(1,65)]
    b['pairs']=[dict(variant_id=r['id'],wt={n:None for n in policy.SIDE_PRODUCERS},variant={n:None for n in policy.SIDE_PRODUCERS}) for r in fact['selected']]
    return b


def test_registered_full_pool_roundtrip_and_hash_run_guards(tmp_path):
    rt=Runtime(tmp_path);b=full_body(rt);raw=encode(b)
    assert 65536<len(raw)<4*1024**2
    run=b['upstream']['design_audit']['artifact']['run_id']
    ref=rt.stage_request(run,raw,policy.TOOL)
    with rt._db() as db:
        assert rt._input(db,ref,run)==raw
        with pytest.raises(RuntimeFault):rt._input(db,dict(ref,sha256='0'*64),run)
        path=rt.root/db.execute('select relative_path from artifacts where id=?',(ref['artifact_id'],)).fetchone()[0]
    other=Runtime(tmp_path,scope='other')
    with other._db() as db:
        with pytest.raises(RuntimeFault):other._input(db,ref,run)
    path.write_bytes(b'changed')
    with rt._db() as db:
        with pytest.raises(RuntimeFault):rt._input(db,ref,run)


def test_bound_and_original_small_tool_limit(tmp_path):
    rt=Runtime(tmp_path);b=full_body(rt);run=b['upstream']['design_audit']['artifact']['run_id']
    b['preselection']['selected'][0]['validation']['synthetic_capacity_only']='x'*(4*1024**2)
    with pytest.raises(RuntimeFault):rt.stage_request(run,encode(b),policy.TOOL)
    from t01_phase1_real.development.codon import policy as cp
    with pytest.raises(RuntimeFault):rt.stage_request(run,b' '*65537,cp.TOOL)


def test_full_pool_l4_diagnostics_do_not_choose_an_unapproved_top20():
    from t01_phase1_real.development.epitope_protection.compute import evaluate
    from test_epitope_protection_development import side
    body=dict(protein_sequence='AAA',preselection={'selection_scope':'ALL_VALIDATED'})
    files={'input/paired-facts.json':encode({'pairs':[dict(variant_id='v',pair_id='p',sequence='ACA',sides={'wt':side(),'variant':side()})]}),
        'input/source-receipts.json':encode({})}
    r=evaluate(body,files)['records'][0]['observation']
    assert r['l4']['value'] is None and r['l4']['reason']=='OI_022_L4_TOP20_POOL_UNDEFINED'
    assert r['l4_diagnostic']['value']==0.


def test_64_long_candidates_keep_geometry_details_outside_summary():
    import copy
    from t01_phase1_real.common import sha
    from t01_phase1_real.development.epitope_protection.compute import compare,evaluate
    from test_epitope_protection_development import side
    s=side();s.update(sequence_sha256=sha(b'A'*999),structure_artifact=None,rsa=[.5]*999,
        hotspots=[dict(start=1,end=999,weighted_score=.6)],
        geometry={str(i):dict(atoms={'CA':[float(i),float(i%3),float(i%7)]}) for i in range(1,1000)})
    seq='A'*999;pair=dict(sequence=seq,sides={'wt':s,'variant':s})
    observed=compare(seq,seq,pair['sides']);files={};index=[]
    for i in range(1,65):
        p=f'input/pairs/{i}.json';d=f'input/pairs/{i}-observation.json'
        files[p]=encode(dict(pair,variant_id='v'+str(i),pair_id='p'+str(i)));files[d]=encode(observed)
        index.append(dict(path=p,sha256=sha(files[p]),observation_path=d,observation_sha256=sha(files[d])))
    files['input/paired-facts.json']=encode(dict(format='PER_PAIR_V1',pairs=index))
    files['input/source-receipts.json']=encode({})
    body=dict(protein_sequence=seq,preselection={'selection_scope':'ALL_VALIDATED'})
    result=evaluate(body,files)
    assert len(result['records'])==64 and len(encode(result))<8*1024**2
    r=result['records'][63]
    assert r['observation']['l3']['hotspot']['rmsd']==observed['l3']['hotspot']['rmsd']
    assert 'residues' not in r['observation']['l3']['hotspot']
    assert 'geometry' not in r['source_states']['wt']
    assert len(observed['l3']['hotspot']['residues'])==999
    files[index[-1]['observation_path']]=b'{}'
    with pytest.raises(RuntimeFault):evaluate(body,files)
