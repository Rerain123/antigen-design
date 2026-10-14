"""Local structure chain admission, adopted quality rules and execution-bound output guards."""
from concurrent.futures import ThreadPoolExecutor
import copy
import math
import os
from pathlib import Path

import pytest

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode, sha
from t01_phase1_real.development import Runtime, docker
from t01_phase1_real.development.structure import policy
from t01_phase1_real.development.structure.quality import assess, experimental
from t01_phase1_real.development.structure.normalization import normalize
from t01_phase1_real.development.structure.result import result, verified_prediction_quality
from t01_phase1_real.development.supervisor import inspect_contract
from t01_phase1_real.development.esmfold2.quality import assess as assess_prediction

BATCH=REPO/'discovery/t01-phase1-real/w1/structure-integration-20260906/acceptance-r02'


def metadata(**changes):
    value=dict(protein_sequence='RKDEQLIVF',host_species='Escherichia coli',structure_name='../metadata only | 原结构',
        declared_format='MMCIF',selection=dict(model_index=None,chain_selector='AUTO'),context_chain_ids=['A'],
        source_declaration=dict(kind='experimental',note=None),timeout_seconds=60)
    value.update(changes);return encode(value)


@pytest.fixture
def rt(tmp_path):
    if os.name!='nt':pytest.skip('Windows development runtime')
    return Runtime(tmp_path/'runtime')


@pytest.mark.parametrize('changes',[
    dict(protein_sequence='A'*8),dict(protein_sequence='A'*2001),dict(protein_sequence='ACDEFGHIK*'),dict(protein_sequence='ACDEFGHIKX'),
    dict(protein_sequence='acdefghik'),dict(protein_sequence='ACDEFGHIK\n'),dict(protein_sequence=None),
    dict(host_species=' '),dict(host_species='A'*257),dict(host_species=None),dict(structure_name=''),dict(declared_format='auto'),
    dict(selection={}),dict(selection=dict(model_index=True,chain_selector='AUTO')),dict(selection=dict(model_index=-1,chain_selector='A')),
    dict(context_chain_ids=None),dict(context_chain_ids=[]),dict(context_chain_ids=['A','A']),dict(context_chain_ids=[1]),
    dict(source_declaration=dict(kind='guessed',note=None)),dict(source_declaration=dict(kind='experimental')),
    dict(timeout_seconds=True),dict(timeout_seconds=121),dict(timeout_seconds=0),dict(command='injected'),
])
def test_invalid_metadata_before_admission(rt,changes):
    with pytest.raises(RuntimeFault):rt.submit_structure(metadata(**changes),'bad',b'local-file')
    with rt._db() as db:
        assert all(db.execute('SELECT count(*) FROM '+t).fetchone()[0]==0 for t in ['runs','jobs','artifacts','idempotency'])


@pytest.mark.parametrize('data',[b'',b'a'*(policy.MAX_STRUCTURE_BYTES+1),None,'text'],ids=['empty','oversized','null','text'])
def test_invalid_file_before_admission(rt,data):
    with pytest.raises(RuntimeFault):rt.submit_structure(metadata(),'bad',data)
    with rt._db() as db:assert db.execute('SELECT count(*) FROM runs').fetchone()[0]==0


def test_structure_atomic_idempotency_tracks_both_original_byte_streams(rt):
    raw=metadata();data=b'exact original bytes\r\n'
    with ThreadPoolExecutor(4) as pool:jobs=list(pool.map(lambda _:Runtime(rt.root).submit_structure(raw,'same',data),range(8)))
    assert len({j['job_id'] for j in jobs})==1
    with rt._db() as db:assert [db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['runs','jobs','artifacts']]==[1,1,2]
    for modified_raw,modified_data in [(raw+b' ',data),(raw,data+b' '),(metadata(host_species='other'),data)]:
        with pytest.raises(RuntimeFault) as err:rt.submit_structure(modified_raw,'same',modified_data)
        assert err.value.code=='IDEMPOTENCY_CONFLICT'
    body=policy.request(rt._request_bytes(jobs[0]))
    assert body['structure_name']=='../metadata only | 原结构' and body['host_species']=='Escherichia coli'
    assert body['structure_artifact']['sha256']==sha(data) and body['structure_artifact']['evidence_kind']=='LOCAL_INPUT'


def test_changed_structure_fails_before_attempt(rt):
    job=rt.submit_structure(metadata(),'tamper',b'original');body=policy.request(rt._request_bytes(job))
    with rt._db() as db:path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(body['structure_artifact']['artifact_id'],)).fetchone()[0]
    (rt.root/path).write_bytes(b'changed!')
    final=rt.dispatch(job['job_id'])
    assert final['state']=='failed' and final['error_code']=='HASH_MISMATCH' and final['attempt_id'] is None


def test_foreign_run_structure_ref_is_forbidden(rt):
    job=rt.submit_structure(metadata(),'one',b'structure');body=policy.request(rt._request_bytes(job))
    other=rt.create_run('other')['run_id']
    with rt._db() as db:
        with pytest.raises(RuntimeFault):rt._structure_bytes(db,body,other)
    body['structure_artifact']['sha256']='0'*64
    with rt._db() as db:
        with pytest.raises(RuntimeFault):rt._structure_bytes(db,body,job['run_id'])


@pytest.mark.parametrize('change',[dict(run_mode='pipeline'),dict(node_id='N02'),dict(tool_id='t01.real.foldx'),dict(execution_profile=dict(id='wrong',version='0.1.0',sha256='0'*64))])
def test_structure_cannot_promote_or_select_arbitrary_tool(rt,change):
    job=rt.submit_structure(metadata(),'one',b'structure')
    fields=['contract_version','run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile']
    body={k:job[k] for k in fields};body.update(idempotency_key='forbidden',**change)
    with pytest.raises(RuntimeFault):rt.submit(encode(body))


def test_queued_cancel_retry_reuses_exact_structure_and_metadata(rt):
    job=rt.submit_structure(metadata(),'queued',b'structure')
    command=lambda op,key:encode(dict(contract_version='0.1.0',operation=op,job_id=job['job_id'],idempotency_key=key))
    final=rt.control(command('cancel','cancel'));assert final['state']=='cancelled' and final['attempt_id'] is None
    retried=rt.control(command('retry','retry'))
    assert retried['request_artifact']==job['request_artifact'] and retried['retry_of_job_id']==job['job_id']
    assert rt._request_bytes(retried)==rt._request_bytes(job)


@pytest.mark.parametrize('method,resolution,confidence,topology',[
    ('X-ray',2.9999,'high',True),('X-ray',3.,'medium',True),('X-ray',4.,'medium',True),('X-ray',4.0001,'low',False),
    ('cryo-EM',3.4999,'high',True),('cryo-EM',3.5,'medium',True),('cryo-EM',4.,'medium',True),('cryo-EM',4.0001,'low',False),
    ('X-ray',None,'medium',False),('cryo-EM',None,'medium',False),('NMR',None,'medium',False),('NMR',2.9999,'high',True),
])
def test_adopted_quality_bins(method,resolution,confidence,topology):
    value=experimental(method,resolution)
    assert value['quality']==dict(confidence=confidence,topology_reliable=topology,low_confidence_regions=None)
    assert value['s11_quality_condition']==(confidence!='low')
    assert bool(value['warnings'])==(resolution is None)


@pytest.mark.parametrize('method,resolution',[('NMR',3.),('NMR',5.),('unknown',2.),(None,None)])
def test_uncovered_quality_is_null_review_not_invented_low(method,resolution):
    value=experimental(method,resolution)
    assert value['quality'] is None and value['s11_quality_condition'] is None
    assert value['warnings'][0]['severity']=='WARNING'


def raw_metadata(method='X-RAY DIFFRACTION',resolution=2.):
    return dict(entries=[dict(group='method',parse_status='text',value=method,origin={'line':1}),
        dict(group='resolution',parse_status='missing' if resolution is None else 'numeric',parsed_number=resolution,origin={'line':2})])


@pytest.mark.parametrize('source',['unknown','predicted','experimental'])
def test_user_source_is_preserved_and_bfactor_never_becomes_plddt(source):
    raw=raw_metadata();raw['entries'].append(dict(group='b_factor',parse_status='numeric',parsed_number=95.))
    value=assess(dict(kind=source,note='original user declaration'),raw)
    assert value['structure']['declaration']['kind']==source and value['structure']['mean_plddt'] is None and value['structure']['missing_atom_fraction'] is None
    assert value['s11_quality_condition']=={'unknown':False,'predicted':None,'experimental':True}[source]
    assert not value['usable_for_pipeline'] and not value['automatic_handoff']


@pytest.mark.parametrize('conflict',[
    dict(group='resolution',parse_status='numeric',parsed_number=5.),dict(group='resolution',parse_status='unparseable',parsed_number=None),
    dict(group='method',parse_status='text',value='SOLUTION NMR')])
def test_conflicting_quality_keeps_all_origins(conflict):
    raw=raw_metadata();raw['entries'].append(conflict)
    value=assess(dict(kind='experimental',note=None),raw)
    assert value['quality'] is None and len(value['structure']['metadata_origins'])==3


def test_plain_electron_microscopy_is_not_silently_cryo():
    assert assess(dict(kind='experimental',note=None),raw_metadata('ELECTRON MICROSCOPY'))['quality'] is None


@pytest.mark.parametrize('source',['esmfold2_predicted','af3_predicted'])
def test_prediction_quality_revalidation_preserves_registered_engine(source):
    quality=assess_prediction([.91,.72,.48,.83,.95],.81,source=source)
    assert verified_prediction_quality(quality)==quality


def join_fixture():
    mapping=dict(sequence='AAA',model_index=0,target_chain_id='A',entries=[]);residues=[];areas=[]
    for pos,num in [(1,42),(3,44)]:
        address=dict(chain_id='A',res_seq=num,insertion_code='')
        mapping['entries'].append(dict(sequence_position=pos,sequence_residue='A',structure_residue=dict(address,residue_name='ALA'),reason=None))
        residues.append(dict(model_index=0,residue_id='raw'+str(num),residue_name='ALA',residue_class='protein',address=dict(auth_asym_id=['A']),
            consumers=dict(integer_mapping_v0_1=dict(representable=True,address=address))))
        areas.append(dict(raw_residue_id='raw'+str(num),absolute_sasa_a2=10. if pos==1 else 20.,raw_address={'auth_seq_id':str(num)}))
    mapping['entries'].insert(1,dict(sequence_position=2,sequence_residue='A',structure_residue=None,reason='missing_structure_residue'))
    return mapping,residues,areas,{'A':100.}


def test_rsa_identity_join_missing_null_full_denominator_and_strict_buried_threshold():
    mapping,residues,areas,table=join_fixture();value=normalize(mapping,list(reversed(residues)),list(reversed(areas)),table)
    assert value['aligned_absolute_sasa_a2']==[10.,None,20.] and value['development_result']==dict(per_residue=[.1,None,.2],buried_fraction=1/3)
    assert value['missing_positions']==[2] and value['normal_rsa_result'] is None
    assert value['identity_join'][0]['raw_residue_id']=='raw42'


@pytest.mark.parametrize('area',[100.,100.0000001,141.3241])
def test_rsa_no_clamp_and_no_tolerance_extension(area):
    mapping,residues,areas,table=join_fixture();areas[0]['absolute_sasa_a2']=area
    value=normalize(mapping,residues,areas,table)
    assert value['raw_normalized_ratios'][0]==area/100.
    assert (value['development_result'] is None)==(area>100.)
    assert value['normal_rsa_result'] is None


@pytest.mark.parametrize('damage',['nan','negative','bool','missing-area','duplicate-area','duplicate-projection','unresolved','duplicate-mapping'])
def test_bad_area_or_join_never_creates_rsa(damage):
    mapping,residues,areas,table=join_fixture()
    if damage in ('nan','negative','bool'):areas[0]['absolute_sasa_a2']={'nan':math.nan,'negative':-1.,'bool':True}[damage]
    elif damage=='missing-area':areas.pop()
    elif damage=='duplicate-area':areas.append(areas[0])
    elif damage=='duplicate-projection':residues.append(residues[0])
    elif damage=='unresolved':mapping['entries'][1]['reason']='unmapped'
    else:mapping['entries'][2]=copy.deepcopy(mapping['entries'][0])
    with pytest.raises((ValueError,KeyError)):normalize(mapping,residues,areas,table)


@pytest.fixture
def actual():
    folder=BATCH/'cases/normal-cif';job=decode((folder/'job.json').read_bytes());value=decode((folder/'result.json').read_bytes())
    files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
    return job,decode(files['input.json']),files,copy.deepcopy(value['execution'])


def test_actual_chain_outputs_revalidate_on_host(actual):
    value=result(*actual)
    assert value['analysis']['freesasa']['status']=='executed' and value['analysis']['rsa']['status']=='computed_unverified'
    assert value['analysis']['mapping']['mapping_status']=='unverified' and value['analysis']['rsa']['normal_rsa_result'] is None
    assert not value['usable_for_pipeline'] and value['production_status']=='NOT_DEPLOYED'


@pytest.mark.parametrize('path',['input.structure','binding.json','output/runtime.json','output/result/analysis.json','output/result/quality.json',
    'output/result/mapping.json','output/result/preparation.json','output/result/raw_areas.json','output/result/raw_residue_areas.json','output/result/rsa.json'])
def test_missing_output_rejects_whole_analysis(actual,path):
    job,body,files,execution=actual;del files[path]
    value=result(job,body,files,execution)
    assert value['analysis'] is None and value['null_reason']=='OUTPUT_INVALID'


@pytest.mark.parametrize('damage',['file-hash','foreign-input','binding','promotion','embedded-step','raw-rsa','network','packages','exit','stop','oom','invalid-json'])
def test_corruption_cannot_publish_a_partial_valid_result(actual,damage):
    job,body,files,execution=actual
    def modify(path,update):
        value=decode(files[path]);update(value);files[path]=encode(value)
    if damage=='file-hash':files['output/result/raw_areas.json']+=b' '
    elif damage=='foreign-input':files['input.structure']+=b' '
    elif damage=='binding':modify('output/result/analysis.json',lambda v:v['binding'].update(job_id='foreign'))
    elif damage=='promotion':modify('output/result/analysis.json',lambda v:v.update(usable_for_pipeline=True))
    elif damage=='embedded-step':modify('output/result/analysis.json',lambda v:v['quality'].update(status='foreign'))
    elif damage=='raw-rsa':
        for path in ['output/result/rsa.json','output/result/analysis.json']:
            modify(path,lambda v:(v['rsa'] if 'rsa' in v else v)['raw_normalized_ratios'].__setitem__(0,.99))
    elif damage=='network':modify('output/runtime.json',lambda v:v['network_interfaces'].append([2,'eth0']))
    elif damage=='packages':modify('output/runtime.json',lambda v:v['packages'].update(freesasa='future'))
    elif damage=='exit':execution['exit_code']=1
    elif damage=='stop':execution['stopped_confirmed']=False
    elif damage=='oom':execution['oom_killed']=True
    elif damage=='invalid-json':files['output/runtime.json']=b'{broken'
    # For semantic mutations, recompute the native checksum to prove the host checks more than hashes.
    if damage in ('binding','promotion','embedded-step','raw-rsa'):
        modify('output/runtime.json',lambda v:v.update(native_output_sha256={n[len('output/'):]:sha(raw) for n,raw in files.items() if n.startswith('output/result/')}))
    value=result(job,body,files,execution)
    assert value['analysis'] is None and value['null_reason']=='OUTPUT_INVALID' and value['warnings']


def test_actual_container_has_registered_isolation_and_immutable_ownership(actual,tmp_path):
    job,body,files,_=actual;info=decode(files['container-inspect.json'])
    inspect_contract(info,policy.TOOL)
    assert info['HostConfig']['NetworkMode']=='none'
    wrong=copy.deepcopy(info);wrong['HostConfig']['Memory']=10*1024**3
    with pytest.raises(RuntimeFault):inspect_contract(wrong,policy.TOOL)
    info['Config']['Labels']=docker.labels(tmp_path,job);assert docker.owned(tmp_path,job,info)
    info['Config']['Image']='unregistered';assert not docker.owned(tmp_path,job,info)


def test_protected_original_sources_match():
    assert len(policy.verify_assets()['files'])==15
