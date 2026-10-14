"""Native output identity, scores, full-chain samples and hard-mask validation."""
import ast
import io
import math
import re
import zipfile
import numpy as np
from ...common import RuntimeFault, encode, decode, ensure, sha
from . import policy
from .mapping import project, BACKBONE


def _finite(value):
    value=float(value);ensure(math.isfinite(value),'OUTPUT_INVALID','Nonfinite native score');return value


def parse(body,files):
    runtime=decode(files['output/runtime.json']);receipt=decode((policy.HERE/'assets.json').read_bytes())
    ensure(runtime['python_exit_code']==0 and runtime['official_source_modified'] is False
        and runtime['network_interfaces']==[[1,'lo']] and runtime['cpu_affinity']==[0,1],
        'OUTPUT_INVALID','No clean offline ProteinMPNN execution')
    ensure(runtime['torch']==receipt['environment']['torch'] and runtime['numpy']==receipt['environment']['numpy']
        and runtime['python']==receipt['environment']['python'] and runtime['cuda']==receipt['environment']['cuda']
        and runtime['gpu_available'] is True,'OUTPUT_INVALID','GPU environment differs from locked profile')
    ensure(runtime['input_sha256']==sha(files['input.json']) and runtime['input_fasta_sha256']==sha(files['input.fasta']),
        'OUTPUT_INVALID','Executed request identity differs')
    expected_assets={p['package_path']:p['sha256'] for p in receipt['files']}
    ensure(runtime['source_sha256']==expected_assets,'OUTPUT_INVALID','Executed official code/weights differ')
    inventory=runtime['native_output_sha256']
    ensure(set(inventory)=={n[7:] for n in files if n.startswith('output/') and n!='output/runtime.json'}
        and all(sha(files['output/'+n])==h for n,h in inventory.items()),'OUTPUT_INVALID','Native output inventory/hash mismatch')
    source=decode(files['input/structure-result.json'])
    facts={n:decode(files['input/'+n+'.json']) for n in ('preflight','raw_metadata','raw_addresses')}
    native=project(body,source,files['input/structure-original.bin'],facts)
    ensure(all(files[n]==v for n,v in native.items()) and runtime['native_input_sha256']=={n[7:]:sha(v) for n,v in native.items()},
        'OUTPUT_INVALID','Native input/coordinate conversion differs from verified source')
    conversion=decode(native['native/conversion.json']);chains=conversion['chain_sequences'];target=conversion['target_chain']
    parsed=decode(files['output/parsed.jsonl'])
    ensure(parsed['name']=='target' and parsed['num_of_chains']==len(chains)
        and {k[10:]:v for k,v in parsed.items() if k.startswith('seq_chain_')}==chains,'OUTPUT_INVALID','Official parsed chain identity differs')
    # Compare actual parser coordinates, not just lengths or finiteness.
    expected_coords={c:{a:[] for a in BACKBONE} for c in chains}
    for line in native['native/target.pdb'].decode().splitlines():
        if line.startswith('ATOM'):
            expected_coords[line[21]][line[12:16].strip()].append([float(line[k:k+8]) for k in (30,38,46)])
    for chain in chains:
        for atom in BACKBONE:ensure(parsed['coords_chain_'+chain][atom+'_chain_'+chain]==expected_coords[chain][atom],
            'OUTPUT_INVALID','Official parsed backbone coordinates changed')
    fixed=decode(files['output/effective-fixed.jsonl']);omit=decode(files['output/effective-omit.jsonl'])
    ensure(runtime['per_position_omit_available'] is True and b'--omit_AA_jsonl' in files['output/native-help.txt'],
        'OUTPUT_INVALID','Pinned native omit capability changed; this profile requires a new capability review')
    ensure(fixed==decode(native['native/fixed_positions.jsonl']) and omit==decode(native['native/omit_AA.jsonl']),
        'OUTPUT_INVALID','Native hard masks differ')
    audit=decode(files['output/native-mask-audit.json']);order=audit['chain_order']
    ensure(len(order)==len(chains) and set(order)==set(chains),'OUTPUT_INVALID','Featurizer chain order changed')
    alphabet=policy.ALPHABET+'X';offsets={};offset=0
    for chain in order:offsets[chain]=offset;offset+=len(chains[chain])
    ensure(all(len(audit[k])==offset for k in ('backbone_mask','chain_mask','position_mask','omit_mask')),
        'OUTPUT_INVALID','Native mask dimensions changed')
    restricted={r['position']:set(r['allowed_residues']) for r in body['constraints']['restricted_positions']}
    for chain in order:
        for pos in range(1,len(chains[chain])+1):
            i=offsets[chain]+pos-1
            ensure(audit['backbone_mask'][i]==1 and audit['chain_mask'][i]==int(chain==target),
                'OUTPUT_INVALID','Native chain/backbone mask violates context')
            if chain==target:
                ensure(audit['position_mask'][i]==int(pos not in fixed['target'][target]),'OUTPUT_INVALID','Native FIXED mask differs')
                expected=[int(a not in restricted[pos]) for a in alphabet] if pos in restricted else [0]*21
                ensure(audit['omit_mask'][i]==expected,'OUTPUT_INVALID','Native per-position hard omit differs')
    count=len(chains[target])-len(fixed['target'][target])
    ensure(runtime['designable_positions']==count,'OUTPUT_INVALID','Native designable count differs')
    if not count:
        ensure(runtime['tool_invoked'] is False and not any(n.startswith('output/generated/') for n in files),
            'OUTPUT_INVALID','No-designable-position path must not claim generation')
        return dict(status='not_generated_no_designable_positions',records=[],generated_count=0,
            conversion=conversion,engine_runtime=runtime,reason_code='NO_DESIGNABLE_POSITIONS',native_wt=None)
    ensure(runtime['tool_invoked'] is True,'OUTPUT_INVALID','Native generation did not execute')
    command=runtime['commands']['generate']['argv']
    pairs={command[i]:command[i+1] for i in range(3,len(command),2)}
    expected={'--path_to_model_weights':'/app/vanilla_model_weights','--model_name':policy.MODEL,
        '--jsonl_path':'/out/parsed.jsonl','--chain_id_jsonl':'/native/chain_id.jsonl',
        '--fixed_positions_jsonl':'/out/effective-fixed.jsonl','--num_seq_per_target':str(body['n_designs']),
        '--sampling_temp':str(body['sampling_temperature']),'--seed':str(body['seed']),'--batch_size':'1',
        '--backbone_noise':'0.0','--omit_AAs':'X','--out_folder':'/out/generated','--save_probs':'1',
        '--save_score':'1','--max_length':'1000','--omit_AA_jsonl':'/out/effective-omit.jsonl'}
    ensure(command[1:3]==['-B','/app/protein_mpnn_run.py'] and pairs==expected and len(command)==3+2*len(expected),
        'OUTPUT_INVALID','Native generation arguments differ')
    lines=files['output/generated/seqs/target.fa'].decode().splitlines()
    ensure(len(lines)==2*(body['n_designs']+1) and all(lines[i].startswith('>') for i in range(0,len(lines),2)),
        'OUTPUT_INVALID','Native FASTA record count/format differs')
    ensure(lines[1]==body['protein_sequence'],'OUTPUT_INVALID','Native WT target sequence differs')
    header=lines[0]
    for label,expected_chains in (('fixed_chains',sorted(conversion['fixed_chains'])),('designed_chains',[target])):
        match=re.search(label+r'=(\[[^\]]*\])',header)
        ensure(match and ast.literal_eval(match[1])==expected_chains,'OUTPUT_INVALID','Native FASTA chain identity differs')
    ensure('model_name='+policy.MODEL in header and header.endswith('seed='+str(body['seed'])),
        'OUTPUT_INVALID','Native model/seed differs')
    native_scores=np.load(io.BytesIO(files['output/generated/scores/target.npz']),allow_pickle=False)
    sample_data=np.load(io.BytesIO(files['output/generated/probs/target.npz']),allow_pickle=False)
    samples=sample_data['S'];probabilities=sample_data['probs'];mask=sample_data['mask'];log_probs=sample_data['log_probs']
    sample_order=sample_data['chain_order'].tolist()
    ensure(len(sample_order)==1 and set(sample_order[0])==set(chains) and len(sample_order[0])==len(chains),
        'OUTPUT_INVALID','Sample chain order differs')
    sample_offsets={};k=0
    for chain in sample_order[0]:sample_offsets[chain]=k;k+=len(chains[chain])
    n=body['n_designs'];ensure(samples.shape==(n,k) and samples.dtype.kind in 'iu' and probabilities.shape==(n,k,21)
        and log_probs.shape==(n,k,21) and mask.shape==(1,k) and np.isfinite(log_probs).all() and (log_probs<=0).all()
        and np.isfinite(probabilities).all() and ((probabilities>=0)&(probabilities<=1)).all()
        and ((samples>=0)&(samples<20)).all() and all(native_scores[key].shape==(n,) for key in ('score','global_score')),
        'OUTPUT_INVALID','Native sampled tensor dimensions/alphabet differ')
    ensure(np.allclose(probabilities.sum(axis=-1)[:,mask[0]==1],1,atol=1e-6,rtol=0),
        'OUTPUT_INVALID','Native sampling probabilities do not sum to one on designable positions')
    for chain in chains:
        start=sample_offsets[chain];stop=start+len(chains[chain])
        expected_mask=[int(chain==target and pos not in fixed['target'][target]) for pos in range(1,len(chains[chain])+1)]
        ensure(mask[0,start:stop].tolist()==expected_mask,'OUTPUT_INVALID','Sample loss mask differs from explicit permissions')
        if chain!=target:
            wt=[alphabet.index(a) for a in chains[chain]]
            ensure((samples[:,start:stop]==wt).all(),'OUTPUT_INVALID','Fixed context chain mutated')
    records=[]
    for i in range(n):
        match=re.fullmatch(r'>T=([^,]+), sample=(\d+), score=([^,]+), global_score=([^,]+), seq_recovery=([^,]+)',lines[2+2*i])
        ensure(match and int(match[2])==i+1 and _finite(match[1])==body['sampling_temperature'],
            'OUTPUT_INVALID','Native sample identity/temperature differs')
        seq=lines[3+2*i];ensure(len(seq)==len(body['protein_sequence']) and set(seq)<=set(policy.ALPHABET),
            'OUTPUT_INVALID','Native sample length/alphabet invalid; sample set is quarantined')
        start=sample_offsets[target]
        ensure(seq==''.join(alphabet[int(a)] for a in samples[i,start:start+len(seq)]),'OUTPUT_INVALID','FASTA differs from native sample tensor')
        for pos in fixed['target'][target]:ensure(seq[pos-1]==body['protein_sequence'][pos-1],'OUTPUT_INVALID','FIXED position mutated')
        for pos,allowed in restricted.items():
            ensure(seq[pos-1] in allowed,'OUTPUT_INVALID','RESTRICTED position sampled forbidden residue')
            ensure(all(probabilities[i,start+pos-1,a]==0 for a,residue in enumerate(alphabet) if residue not in allowed),
                'OUTPUT_INVALID','Forbidden restricted residues have nonzero native sampling probability')
        score,global_score,recovery=map(_finite,(match[3],match[4],match[5]))
        ensure(0<=recovery<=1 and all(abs(_finite(native_scores[key][i])-value)<=.000051
            for key,value in (('score',score),('global_score',global_score))), 'OUTPUT_INVALID','Native score NPZ/FASTA mismatch')
        losses=-log_probs[i,np.arange(k),samples[i]]
        ensure(abs(float((losses*mask[0]).sum()/mask[0].sum())-score)<=.00006
            and abs(float(losses.mean())-global_score)<=.00006,'OUTPUT_INVALID','Native scores do not agree with saved residue log probabilities')
        expected_recovery=sum(seq[p-1]==body['protein_sequence'][p-1] for p in range(1,len(seq)+1) if p not in fixed['target'][target])/count
        ensure(abs(expected_recovery-recovery)<=.000051,'OUTPUT_INVALID','Native seq_recovery differs from designable-position identity')
        records.append(dict(sample_number=i+1,sequence=seq,score=score,global_score=global_score,seq_recovery=recovery,
            is_wt=seq==body['protein_sequence'],duplicate_of_sample=next((r['sample_number'] for r in records if r['sequence']==seq),None),
            mutations=[dict(position=p,wt_residue=w,mut_residue=m,source='ProteinMPNN')
                for p,(w,m) in enumerate(zip(body['protein_sequence'],seq),1) if w!=m],engine='ProteinMPNN'))
    return dict(status='generated_unreviewed',records=records,generated_count=len(records),native_wt=dict(header=header,sequence=lines[1]),
        conversion=conversion,engine_runtime=runtime,reason_code=None)


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        structure_artifact=body['structure_artifact'],constraints_sha256=sha(encode(body['constraints'])))
    value=dict(contract_version='0.1.0',tool_id=policy.TOOL,binding=binding,evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,
        production_status='NOT_DEPLOYED',requires_review=True,execution=execution,controlled_fault=fault,status='unreliable',
        generation=None,design_permissions=None,formal_candidates=None,scientific_gate='NOT_EVALUATED',
        null_reason=execution.get('error_code'),warnings=[],source_receipt=execution.get('source_receipt'),
        method_summary=dict(engine='ProteinMPNN',commit=policy.COMMIT,model=policy.MODEL,rule_profile=job['rule_profile'],
            parameters={k:body[k] for k in ('n_designs','sampling_temperature','seed')},permission_source=body['constraints'],
            scientific_permission_synthesis=False,score_semantics=dict(score='native designed-residue negative log probability',
                global_score='native all-chain all-residue negative log probability'),ranking_performed=False))
    if execution.get('error_code'):
        value['warnings']=[dict(code=execution['error_code'],level='failure',severity='WARNING',
            message='序列设计失败——变体生成未完成；'+str(execution.get('diagnostic') or execution['error_code']))]
        return value
    try:
        ensure(execution['stopped_confirmed'] and execution['exit_code']==0 and execution['image_id']==policy.IMAGE,
            'OUTPUT_INVALID','No clean stopped pinned ProteinMPNN run')
        if fault=='corrupt_output':raise RuntimeFault('OUTPUT_INVALID','Controlled native output corruption')
        generated=parse(body,files)
        value.update(status=generated['status'],generation=generated,null_reason=None,
            warnings=[dict(code='ENGINEERING_MASKS_NOT_SCIENTIFIC_PERMISSIONS',level='quality',severity='WARNING',
                message='仅为明确工程掩码的真实生成，科学 Gate、权限合成与正式候选交接均未放行')])
    except (RuntimeFault,KeyError,ValueError,TypeError,IndexError,OSError,EOFError,zipfile.BadZipFile,OverflowError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID')
        value['warnings']=[dict(code='OUTPUT_INVALID',level='failure',severity='WARNING',
            message='序列设计失败——原生输出未通过校验，整组隔离；'+str(exc))]
    return value
