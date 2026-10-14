"""Observe the unchanged upstream CLI in a fixed, offline CPU container."""
from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import runpy
import socket
import sys
import time
import traceback

OUT=Path('/out')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)


def main():
    started=time.monotonic()
    runtime=dict(packages={k:version(k) for k in ['bp3','fair-esm','torch','numpy','pandas','plotly']},python=platform.python_version(),
        network_interfaces=socket.if_nameindex(),cpu_affinity=sorted(os.sched_getaffinity(0)),python_exit_code=None,
        tool_version='BepiPred-3.0',source_modules_modified=False)
    write(OUT/'runtime_started.json',runtime)
    try:
        assert not (OUT/'result').exists(),'Output must be fresh'
        import torch
        torch.set_num_threads(8)
        assert not torch.cuda.is_available(),'CPU profile only'
        runtime['input_fasta_sha256']=sha(Path('/input.fasta').read_bytes())
        sys.argv=['/app/bepipred3_CLI.py','-i','/input.fasta','-o','/out/result','-pred','vt_pred','-esm_dir','/out/encodings',
            '-t','0.1512','-top','0.2','-rolling_window_size','9']
        runtime['argv']=sys.argv
        # The upstream loader finds both read-only weight files under TORCH_HOME.
        # network=none prevents any online fallback; upstream code is not patched.
        namespace=runpy.run_path(sys.argv[0],run_name='__main__')
        antigens=namespace['MyAntigens'];predictor=namespace['MyBP3EnsemblePredict']
        observations=[]
        for ident,seq,path,folds in zip(antigens.accs,antigens.seqs,antigens.esm_encoding_paths,antigens.ensemble_probs):
            embedding=torch.load(path,map_location='cpu',weights_only=True)
            avg=torch.mean(torch.stack(folds,axis=1),axis=1)
            observations.append(dict(internal_sequence_id=ident,sequence=seq,sequence_sha256=sha(seq.encode()),
                embedding_shape=list(embedding.shape),embedding_sha256=sha(path.read_bytes()),embedding_file=path.relative_to(OUT).as_posix(),
                fold_probabilities=[f.cpu().tolist() for f in folds],average_probabilities=avg.cpu().tolist(),
                rolling_mean=predictor.compute_rolling_mean_on_bp3_prob_outputs(avg).tolist()))
        write(OUT/'observations.json',dict(records=observations,folds=[dict(name=p.name,sha256=sha(p.read_bytes())) for p in predictor.model_states],
            model_variant='BP3C50IDFFNN',add_seq_len=antigens.add_seq_len,threshold=0.1512,top_fraction=0.2,rolling_window=9,
            upstream_cli_sha256=sha(Path('/app/bepipred3_CLI.py').read_bytes()),bp3_source_sha256=sha(Path(namespace['bepipred3'].__file__).read_bytes())))
        runtime['python_exit_code']=0
    except BaseException as exc:
        runtime.update(python_exit_code=1,error_type=type(exc).__name__,error=str(exc))
        (OUT/'exception.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
    finally:
        runtime.update(elapsed_seconds=time.monotonic()-started,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            native_output_sha256={p.relative_to(OUT).as_posix():sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='runtime.json'})
        write(OUT/'runtime.json',runtime)


if __name__=='__main__':main()
