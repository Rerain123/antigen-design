"""Fixed offline GPU execution of unmodified official ProteinMPNN scripts."""
import hashlib
import json
import os
from pathlib import Path
import platform
import runpy
import socket
import subprocess
import sys
import time
import traceback

OUT=Path('/out')
digest=lambda raw:hashlib.sha256(raw).hexdigest()


def write(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,sort_keys=True,allow_nan=False)


def main():
    started=time.monotonic();body=json.loads(Path('/input.json').read_bytes())
    runtime=dict(python=platform.python_version(),network_interfaces=socket.if_nameindex(),
        cpu_affinity=sorted(os.sched_getaffinity(0)),input_sha256=digest(Path('/input.json').read_bytes()),
        input_fasta_sha256=digest(Path('/input.fasta').read_bytes()),commands={},python_exit_code=None,
        official_source_modified=False,tool_invoked=False)
    write('runtime_started.json',runtime)
    try:
        import numpy as np
        import torch
        runtime.update(torch=torch.__version__,numpy=np.__version__,cuda=torch.version.cuda,
            gpu_available=torch.cuda.is_available())
        if not torch.cuda.is_available():raise RuntimeError('Registered CUDA device unavailable; no CPU fallback')
        runtime.update(gpu_name=torch.cuda.get_device_name(0),gpu_capability=list(torch.cuda.get_device_capability(0)),
            gpu_total_memory=torch.cuda.get_device_properties(0).total_memory)
        torch.cuda.reset_peak_memory_stats()
        if (OUT/'result').is_dir():raise RuntimeError('Controlled tool failure')
        if (OUT/'slow_worker').is_dir():time.sleep(60)
        runtime['source_sha256']={p.relative_to('/app').as_posix():digest(p.read_bytes())
            for p in sorted(Path('/app').rglob('*')) if p.is_file()}
        runtime['native_input_sha256']={p.name:digest(p.read_bytes()) for p in sorted(Path('/native').iterdir()) if p.is_file()}
        help_argv=[sys.executable,'-B','/app/protein_mpnn_run.py','--help']
        help_run=subprocess.run(help_argv,capture_output=True,check=True)
        (OUT/'native-help.txt').write_bytes(help_run.stdout);(OUT/'native-help.stderr.txt').write_bytes(help_run.stderr)
        supports_omit=b'--omit_AA_jsonl' in help_run.stdout
        runtime['commands']['help']=dict(argv=help_argv,exit_code=help_run.returncode)
        runtime['per_position_omit_available']=supports_omit
        parse_argv=[sys.executable,'-B','/app/helper_scripts/parse_multiple_chains.py','--input_path','/native/',
            '--output_path','/out/parsed.jsonl']
        parse_run=subprocess.run(parse_argv,capture_output=True,check=True)
        (OUT/'parser.stdout.txt').write_bytes(parse_run.stdout);(OUT/'parser.stderr.txt').write_bytes(parse_run.stderr)
        runtime['commands']['parse']=dict(argv=parse_argv,exit_code=parse_run.returncode)
        conversion=json.loads(Path('/native/conversion.json').read_bytes());parsed=json.loads((OUT/'parsed.jsonl').read_bytes())
        expected=conversion['chain_sequences'];target=conversion['target_chain']
        assert parsed['name']=='target' and parsed['num_of_chains']==len(expected)
        assert {k.removeprefix('seq_chain_'):v for k,v in parsed.items() if k.startswith('seq_chain_')}==expected
        for chain,sequence in expected.items():
            for name in ('N','CA','C','O'):
                coords=np.array(parsed['coords_chain_'+chain][name+'_chain_'+chain])
                assert coords.shape==(len(sequence),3) and np.isfinite(coords).all()
        fixed=json.loads(Path('/native/fixed_positions.jsonl').read_bytes())
        omit=json.loads(Path('/native/omit_AA.jsonl').read_bytes())
        warnings=[]
        if not supports_omit:
            fixed['target'][target]=sorted(set(fixed['target'][target])|{r['position'] for r in body['constraints']['restricted_positions']})
            omit['target'][target]=[];warnings.append('RESTRICTED_DEGRADED_TO_FIXED_NO_NATIVE_OMIT')
        write('effective-fixed.jsonl',fixed);write('effective-omit.jsonl',omit)
        # Inspect the fixed original featurizer's actual hard masks before sampling.
        sys.path.insert(0,'/app')
        from protein_mpnn_utils import tied_featurize
        chain_ids=json.loads(Path('/native/chain_id.jsonl').read_bytes())
        features=tied_featurize([parsed],torch.device('cuda:0'),chain_ids,fixed,omit)
        _,_,mask,_,chain_mask,_,chain_order,_,_,_,position_mask,omit_mask,*_=features
        audit=dict(chain_order=chain_order[0],backbone_mask=mask[0].cpu().tolist(),
            chain_mask=chain_mask[0].cpu().tolist(),position_mask=position_mask[0].cpu().tolist(),
            omit_mask=omit_mask[0].cpu().tolist(),warnings=warnings)
        write('native-mask-audit.json',audit)
        for chain in expected:
            offset=sum(len(expected[c]) for c in audit['chain_order'][:audit['chain_order'].index(chain)])
            for position in range(1,len(expected[chain])+1):
                i=offset+position-1
                assert audit['backbone_mask'][i]==1 and audit['chain_mask'][i]==(1 if chain==target else 0)
                if chain==target:assert audit['position_mask'][i]==(0 if position in fixed['target'][target] else 1)
        designable=len(expected[target])-len(fixed['target'][target])
        runtime['designable_positions']=designable
        if designable:
            argv=['/app/protein_mpnn_run.py','--path_to_model_weights','/app/vanilla_model_weights','--model_name','v_48_020',
                '--jsonl_path','/out/parsed.jsonl','--chain_id_jsonl','/native/chain_id.jsonl',
                '--fixed_positions_jsonl','/out/effective-fixed.jsonl','--num_seq_per_target',str(body['n_designs']),
                '--sampling_temp',str(body['sampling_temperature']),'--seed',str(body['seed']),
                '--batch_size','1','--backbone_noise','0.0','--omit_AAs','X','--out_folder','/out/generated',
                '--save_probs','1','--save_score','1','--max_length','1000']
            if supports_omit:argv+=['--omit_AA_jsonl','/out/effective-omit.jsonl']
            runtime['commands']['generate']=dict(argv=[sys.executable,'-B',*argv],execution='unmodified_cli_via_runpy')
            sys.argv=argv;runpy.run_path('/app/protein_mpnn_run.py',run_name='__main__')
            runtime['tool_invoked']=True
        torch.cuda.synchronize()
        runtime.update(gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved(),
            python_exit_code=0)
    except BaseException as exc:
        runtime.update(python_exit_code=1,error=str(exc),error_type=type(exc).__name__)
        (OUT/'exception.txt').write_text(traceback.format_exc());raise
    finally:
        runtime['elapsed_seconds']=time.monotonic()-started
        runtime['native_output_sha256']={p.relative_to(OUT).as_posix():digest(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()}
        write('runtime.json',runtime)


if __name__=='__main__':main()
