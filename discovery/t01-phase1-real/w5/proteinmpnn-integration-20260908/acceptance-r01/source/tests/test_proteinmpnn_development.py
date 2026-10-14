"""ProteinMPNN engineering masks and source-coordinate conversion contracts."""
import copy
import io
import sys
from pathlib import Path
import pytest
import numpy as np

from t01_phase1_real.common import REPO, RuntimeFault, decode, encode,sha
from t01_phase1_real.development.proteinmpnn import policy
from t01_phase1_real.development.proteinmpnn.mapping import project
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.probe import parse_local, propose

sys.path.insert(0,str(REPO/'scripts'))
from structure_integration_cases import cases, SEQUENCE


def request(sequence=SEQUENCE,**updates):
    value=dict(protein_sequence=sequence,user_sequence_id='explicit-mask-test',structure_artifact=dict(
        artifact_id='t01p1r-artifact-'+'1'*32,run_id='t01p1r-run-'+'1'*32,job_id='t01p1r-job-'+'1'*32,
        attempt_id='t01p1r-attempt-'+'1'*32,role='result',media_type='application/json',evidence_kind='G0_REAL_OUTPUT',
        sha256='a'*64,size_bytes=100,contract_version='0.1.0'),
        constraints=dict(purpose='ENGINEERING_EXPLICIT_MASKS',source_id='CONTRACT_FIXTURE',fixed_positions=[1],
            restricted_positions=[dict(position=2,allowed_residues=sequence[1])],open_positions=list(range(3,len(sequence)+1))),
        n_designs=24,sampling_temperature=0.1,seed=17,timeout_seconds=60)
    # ArtifactRef has no contract_version in the preserved runtime schema.
    value['structure_artifact'].pop('contract_version')
    value.update(updates);return value


def source(tmp_path,name='normal-pdb',data=None,sequence=SEQUENCE):
    fixture=next(c for c in cases() if c['name']==name)
    data=data or fixture['data'];path=tmp_path/('source.pdb' if fixture['request']['declared_format']=='PDB' else 'source.cif')
    path.write_bytes(data);inventory=parse_local(path)
    mapping=propose(sequence,inventory,evidence_kind='G0_REAL_OUTPUT',model_index=0)
    facts=inspect_input(data,declared_format=fixture['request']['declared_format'],model_index=0,chain_selector='AUTO')
    return dict(analysis=dict(mapping=mapping)),data,facts


def test_exact_request_defaults_and_exhaustive_masks():
    value=request();assert policy.request(encode(value))==value
    assert value['n_designs']==24 and value['sampling_temperature']==0.1


@pytest.mark.parametrize('change',['missing_position','duplicate_position','out_of_range','empty_fixed','allowed_missing_wt',
    'allow_all','empty_allow','unknown_aa','self_signed','gate_override','seed_zero','count_zero','invalid_temperature','missing_structure'])
def test_reject_unspecified_permissions_and_unsupported_controls(change):
    body=request();c=body['constraints']
    if change=='missing_position':c['open_positions'].pop()
    elif change=='duplicate_position':c['open_positions'].append(1)
    elif change=='out_of_range':c['open_positions'][-1]=100
    elif change=='empty_fixed':c['open_positions'].append(1);c['fixed_positions']=[]
    elif change=='allowed_missing_wt':c['restricted_positions'][0]['allowed_residues']='A'
    elif change=='allow_all':c['restricted_positions'][0]['allowed_residues']=policy.ALPHABET
    elif change=='empty_allow':c['restricted_positions'][0]['allowed_residues']=''
    elif change=='unknown_aa':body['protein_sequence']='X'+SEQUENCE[1:]
    elif change=='self_signed':body['scientific_signoff']=True
    elif change=='gate_override':body['design_gate']='PASS'
    elif change=='seed_zero':body['seed']=0
    elif change=='count_zero':body['n_designs']=0
    elif change=='invalid_temperature':body['sampling_temperature']=0.5
    else:body['structure_artifact']=None
    with pytest.raises(RuntimeFault):policy.request(encode(body))


@pytest.mark.parametrize('fmt',['normal-pdb','normal-cif'])
def test_author_number_42_maps_to_native_position_1(tmp_path,fmt):
    src,data,facts=source(tmp_path,fmt);body=request();projected=project(body,src,data,facts)
    conversion=decode(projected['native/conversion.json'])
    assert conversion['rows'][0]['author_resseq']=='42' and conversion['rows'][0]['tool_position']==1
    assert decode(projected['native/fixed_positions.jsonl'])=={'target':{'A':[1]}}
    assert decode(projected['native/omit_AA.jsonl'])['target']['A']==[[[2],''.join(a for a in policy.ALPHABET+'X' if a!='K')]]
    assert projected['native/target.pdb'].decode().splitlines()[0][22:26]=='   1'
    assert len(conversion['rows'])==len(SEQUENCE) and conversion['mapping_failed_count']==0


def test_insertions_and_gaps_have_explicit_inverse_mapping(tmp_path):
    raw=next(c for c in cases() if c['name']=='normal-pdb')['data']
    lines=[]
    for line in raw.decode().splitlines():
        if line.startswith('ATOM'):
            pos=int(line[22:26])-42
            number,icode=(100,' ') if pos==0 else (100,'A') if pos==1 else (100+pos*3,' ')
            line=line[:22]+f'{number:4d}'+icode+line[27:]
        lines.append(line)
    src,data,facts=source(tmp_path,data=('\n'.join(lines)+'\n').encode())
    out=project(request(),src,data,facts);rows=decode(out['native/conversion.json'])['rows']
    assert [(r['author_resseq'],r['insertion_code'],r['tool_position']) for r in rows[:3]]==[('100','',1),('100','A',2),('106','',3)]


@pytest.mark.parametrize('name',['missing-residue','ambiguous-chains'])
def test_incomplete_or_ambiguous_mapping_does_not_start_chain(tmp_path,name):
    src,data,facts=source(tmp_path,name)
    with pytest.raises(RuntimeFault):project(request(),src,data,facts)


def test_no_designable_positions_remain_explicit(tmp_path):
    body=request();body['constraints'].update(fixed_positions=list(range(1,len(SEQUENCE)+1)),restricted_positions=[],open_positions=[])
    policy.request(encode(body));src,data,facts=source(tmp_path)
    assert decode(project(body,src,data,facts)['native/fixed_positions.jsonl'])['target']['A']==list(range(1,len(SEQUENCE)+1))


def test_fixed_conversion_failure_is_not_silently_omitted(tmp_path):
    src,data,facts=source(tmp_path);src['analysis']['mapping']['entries'][0]['structure_residue']['res_seq']=999
    with pytest.raises(RuntimeFault,match='conversion'):project(request(),src,data,facts)


def test_missing_backbone_is_rejected(tmp_path):
    raw=next(c for c in cases() if c['name']=='normal-pdb')['data']
    raw=b'\n'.join(line for line in raw.splitlines() if not(line.startswith(b'ATOM') and line[12:16].strip()==b'O'))+b'\n'
    src,data,facts=source(tmp_path,data=raw)
    with pytest.raises(RuntimeFault,match='Backbone'):project(request(),src,data,facts)


def test_gpu_command_has_hard_offline_mount_and_no_bias():
    from t01_phase1_real.development import docker
    job=dict(tool_id=policy.TOOL,run_id='test-run',job_id='test-job',attempt_id='test-attempt',execution_identity='test-exec')
    cmd=docker.proteinmpnn_command(REPO/'tmp',job,'mpnn-test',60)
    assert cmd[cmd.index('--network')+1]=='none' and '--read-only' in cmd and '--gpus' in cmd
    assert all('bias' not in arg for arg in cmd) and policy.IMAGE in cmd


def test_native_omit_code_is_hard_multiply_and_renormalize():
    code=(policy.PACKAGE/'protein_mpnn_utils.py').read_text()
    assert 'probs_masked = probs*(1.0-omit_AA_mask_gathered)' in code
    assert 'fixed_position_mask[np.array(fixed_pos_list)-1] = 0.0' in code


@pytest.mark.parametrize('damage',['missing','size','hash'])
def test_isolated_asset_registry_rejects_missing_or_changed_weight(tmp_path,monkeypatch,damage):
    # A private temporary registry tests the real verifier without touching official/frozen assets.
    asset=tmp_path/'weights.pt';raw=b'contract fixture weight bytes';asset.write_bytes(raw)
    registry=dict(commit=policy.COMMIT,image=policy.IMAGE,files=[dict(path='weights.pt',bytes=len(raw),sha256=sha(raw))])
    (tmp_path/'assets.json').write_bytes(encode(registry))
    monkeypatch.setattr(policy,'HERE',tmp_path);monkeypatch.setattr(policy,'REPO',tmp_path)
    assert policy.verify_assets()==registry
    if damage=='missing':asset.unlink()
    elif damage=='size':asset.write_bytes(raw+b'!')
    else:asset.write_bytes(b'X'+raw[1:])
    with pytest.raises(RuntimeFault) as error:policy.verify_assets()
    assert error.value.code==('HASH_MISMATCH' if damage=='hash' else 'ASSET_MISSING')


@pytest.fixture
def native_recording():
    # Recorded real offline GPU output. Tests mutate private in-memory copies only.
    folder=REPO/'discovery/t01-phase1-real/w5/proteinmpnn-integration-20260908/smoke-r01/cases/real-1ubq-default24'
    value=decode((folder/'result.json').read_bytes());job=decode((folder/'job.json').read_bytes())
    files={r['path']:(folder/'artifacts'/r['artifact']['artifact_id']).read_bytes() for r in value['raw_artifacts']}
    return job,decode(files['input.json']),files,value['execution']


def test_recorded_native_gpu_output_validates_all_24(native_recording):
    from t01_phase1_real.development.proteinmpnn.result import result
    value=result(*native_recording)
    assert value['generation']['generated_count']==24 and value['generation']['engine_runtime']['tool_invoked']
    assert value['formal_candidates'] is None and not value['automatic_handoff']


@pytest.mark.parametrize('damage',['missing_fasta','fasta_count','fixed_mutation','restricted_mutation','npz_damage','coordinates',
    'fixed_mask','no_omit','changed_seed','forbidden_probability','score','recovery','gpu_environment','native_source'])
def test_corrupt_native_records_are_quarantined(native_recording,damage):
    from t01_phase1_real.development.proteinmpnn.result import result
    job,body,files,execution=native_recording
    runtime=decode(files['output/runtime.json']);fasta='output/generated/seqs/target.fa';probs='output/generated/probs/target.npz'
    lines=files[fasta].decode().splitlines()
    if damage=='missing_fasta':files.pop(fasta)
    elif damage=='fasta_count':files[fasta]=('\n'.join(lines[:-2])+'\n').encode()
    elif damage in ('fixed_mutation','restricted_mutation','forbidden_probability'):
        data=dict(np.load(io.BytesIO(files[probs]),allow_pickle=False));position=0 if damage=='fixed_mutation' else 1
        changed='A' if damage=='fixed_mutation' else 'C'
        if damage=='forbidden_probability':data['probs'][0,position,policy.ALPHABET.index(changed)]=0.25
        else:
            lines[3]=lines[3][:position]+changed+lines[3][position+1:];files[fasta]=('\n'.join(lines)+'\n').encode()
            data['S'][0,position]=policy.ALPHABET.index(changed)
        out=io.BytesIO();np.savez(out,**data);files[probs]=out.getvalue()
    elif damage=='npz_damage':files[probs]=b'not an npz archive'
    elif damage=='coordinates':
        parsed=decode(files['output/parsed.jsonl']);parsed['coords_chain_A']['CA_chain_A'][0][0]+=1
        files['output/parsed.jsonl']=encode(parsed)
    elif damage=='fixed_mask':
        mask=decode(files['output/native-mask-audit.json']);mask['position_mask'][0]=1;files['output/native-mask-audit.json']=encode(mask)
    elif damage=='no_omit':runtime['per_position_omit_available']=False
    elif damage=='changed_seed':
        argv=runtime['commands']['generate']['argv'];argv[argv.index('--seed')+1]='18'
    elif damage=='gpu_environment':runtime['gpu_available']=False
    elif damage=='native_source':runtime['source_sha256']['protein_mpnn_run.py']='0'*64
    elif damage=='score':
        pieces=lines[2].split(', ');pieces[2]='score=99.0000';lines[2]=', '.join(pieces);files[fasta]=('\n'.join(lines)+'\n').encode()
        path='output/generated/scores/target.npz';data=dict(np.load(io.BytesIO(files[path]),allow_pickle=False));data['score'][0]=99
        out=io.BytesIO();np.savez(out,**data);files[path]=out.getvalue()
    elif damage=='recovery':
        parts=lines[2].split(', ');parts[-1]='seq_recovery=0.9876';lines[2]=', '.join(parts);files[fasta]=('\n'.join(lines)+'\n').encode()
    # Recompute the output inventory to exercise semantic checks beyond superficial file hash rejection.
    runtime['native_output_sha256']={n[7:]:sha(v) for n,v in files.items() if n.startswith('output/') and n!='output/runtime.json'}
    files['output/runtime.json']=encode(runtime)
    value=result(job,body,files,execution)
    assert value['generation'] is None and value['null_reason']=='OUTPUT_INVALID' and value['status']=='unreliable'
