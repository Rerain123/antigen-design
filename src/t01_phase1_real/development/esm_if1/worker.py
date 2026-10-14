"""Offline GPU calls to the original ESM-IF1 API; no rule evaluation or structure prediction."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import socket
import sys
import time
import traceback

OUT=Path('/out')
def digest(raw):return hashlib.sha256(raw).hexdigest()
def filehash(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024**2),b''):value.update(block)
    return value.hexdigest()
def write(name,value):
    with (OUT/name).open('x') as stream:json.dump(value,stream,sort_keys=True,allow_nan=False)


def main():
    started=time.monotonic();payload=json.loads(Path('/native/payload.json').read_bytes())
    runtime=dict(python=platform.python_version(),network_interfaces=socket.if_nameindex(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        input_sha256=filehash(Path('/input.json')),input_fasta_sha256=filehash(Path('/input.fasta')),
        native_input_sha256={p.name:filehash(p) for p in Path('/native').iterdir() if p.is_file()},
        source_sha256={p.relative_to('/app').as_posix():filehash(p) for p in sorted(Path('/app').rglob('*')) if p.is_file()},
        python_exit_code=None,model_loaded=False,baseline_model_calls=0,variant_model_calls=0,official_source_modified=False,
        parameters=payload['parameters'],baseline_reused=payload['baseline'] is not None)
    write('runtime_started.json',runtime)
    try:
        import numpy as np
        import torch
        import biotite
        import scipy
        import torch_geometric
        import esm
        from esm.inverse_folding.util import load_structure,get_sequence_loss
        from esm.inverse_folding.multichain_util import extract_coords_from_complex,_concatenate_coords
        runtime.update(torch=torch.__version__,numpy=np.__version__,cuda=torch.version.cuda,biotite=biotite.__version__,
            scipy=scipy.__version__,torch_geometric=torch_geometric.__version__,gpu_available=torch.cuda.is_available())
        assert torch.cuda.is_available(),'Registered GPU unavailable; no CPU fallback'
        runtime.update(gpu_name=torch.cuda.get_device_name(0),gpu_capability=list(torch.cuda.get_device_capability(0)))
        torch.cuda.reset_peak_memory_stats();torch.manual_seed(17);np.random.seed(17);random.seed(17)
        torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
        if (OUT/'result').is_dir():raise RuntimeError('Controlled ESM-IF1 tool failure')
        if (OUT/'slow_worker').is_dir():time.sleep(60)
        coords,seqs=extract_coords_from_complex(load_structure('/native/wt.pdb'))
        conversion=json.loads(Path('/native/conversion.json').read_bytes());target=payload['target_chain']
        assert seqs==conversion['chain_sequences'] and seqs[target]==payload['protein_sequence']
        assert all(c.shape==(len(seqs[k]),3,3) and np.isfinite(c).all() for k,c in coords.items())
        write('parsed-coordinates.json',dict(chain_order=list(coords),sequences=seqs,
            coordinates={k:c.tolist() for k,c in coords.items()},target_chain=target,atom_order=['N','CA','C']))
        all_coords=_concatenate_coords(coords,target,padding_length=10)
        records=[];baseline=None;baseline_status='not_needed_empty_input'
        if payload['records']:
            # Only allow the checkpoint's explicit argparse Namespace in PyTorch's restricted loader.
            with torch.serialization.safe_globals([argparse.Namespace]):
                model,alphabet=esm.pretrained.load_model_and_alphabet_local('/app/weights/esm_if1_gvp4_t16_142M_UR50.pt')
            model=model.eval().cuda();runtime['model_loaded']=True
            runtime['model_parameter_count']=sum(p.numel() for p in model.parameters())
            runtime['model_training']=model.training
            def score(seq):
                with torch.no_grad():loss,padding=get_sequence_loss(model,alphabet,all_coords,seq)
                assert loss.shape==(len(seq),) and padding.shape==(len(seq),) and not padding.any()
                assert np.isfinite(loss).all() and (loss>=0).all()
                # This is the original score_sequence_in_complex full-target reduction.
                full=-np.sum(loss*~padding)/np.sum(~padding)
                return dict(score=float(full),per_residue_nll=loss.tolist(),target_padding_mask=padding.tolist(),
                    residue_count=len(seq),sequence_sha256=digest(seq.encode()))
            if payload['baseline'] is None:
                runtime['baseline_model_calls']+=1
                baseline=dict(score(payload['protein_sequence']),signature=payload['signature'],origin_job_id=os.environ['T01_JOB_ID'])
                baseline_status='computed_once'
                assert baseline['score']<0,'Zero or invalid WT denominator'
            else:baseline=payload['baseline'];baseline_status='verified_reuse'
            for record in payload['records']:
                row=dict(sample_number=record['sample_number'],sequence=record['sequence'],mutations=record['mutations'],
                    score=None,error_code=None,diagnostic=None,measurement=None)
                try:
                    if (OUT/'all_variants_failure').is_dir() or ((OUT/'first_variant_failure').is_dir() and not records):
                        raise RuntimeError('Controlled variant failure before native model call')
                    runtime['variant_model_calls']+=1
                    row['measurement']=score(record['sequence']);row['score']=row['measurement']['score']
                except Exception as exc:
                    row.update(error_code='VARIANT_SCORE_FAILED',diagnostic=str(exc));torch.cuda.empty_cache()
                records.append(row)
        write('observation.json',dict(signature=payload['signature'],baseline=baseline,baseline_status=baseline_status,records=records,
            native_api='esm.inverse_folding.util.get_sequence_loss',score_mean_scope='all_target_chain_residues',
            backbone_context='all_protein_chains_target_first_padding10',structure_prediction_executed=False))
        torch.cuda.synchronize()
        runtime.update(gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated(),gpu_peak_reserved_bytes=torch.cuda.max_memory_reserved(),python_exit_code=0)
    except BaseException as exc:
        runtime.update(python_exit_code=1,error=str(exc),error_type=type(exc).__name__)
        (OUT/'exception.txt').write_text(traceback.format_exc());raise
    finally:
        runtime['elapsed_seconds']=time.monotonic()-started
        runtime['native_output_sha256']={p.relative_to(OUT).as_posix():filehash(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
        write('runtime.json',runtime)


if __name__=='__main__':main()
