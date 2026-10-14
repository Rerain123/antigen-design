"""Container-only observer of unmodified Academic code; no inference replacements."""
import hashlib
from importlib.metadata import version
import json
import linecache
import os
from pathlib import Path
import resource
import runpy
import socket
import sys
import time

import torch

from contextlib import nullcontext

if os.environ.get('T01_RESIDENT_OFFLINE') == '1':
    from torch_threads import resident_thread_budget


def main():
    started = time.monotonic()
    output = Path('/out')
    report = dict(python=sys.version, packages={n: version(n) for n in
        ('torch', 'fair-esm', 'numpy', 'biopython', 'matplotlib')},
        cuda_available=torch.cuda.is_available(), cpu_count=os.cpu_count(),
        cpu_affinity=sorted(os.sched_getaffinity(0)), network_interfaces=socket.if_nameindex(),
        scientific_source_modified=False, observation='sys.settrace on utils.generate_esm_embeddings only',
        entrypoint=['/app/predict.py', '--fasta', '/input.fasta', '--output-dir', '/out/result'])
    (output/'runtime_started.json').write_text(json.dumps(report, indent=2))
    events = (output/'token_trace.jsonl').open('x')

    def emit(kind, data):
        events.write(json.dumps(dict(event=kind, elapsed_seconds=time.monotonic()-started, **data))+'\n')
        events.flush()

    def trace(frame, event, arg):
        if frame.f_code.co_filename != '/app/utils.py' or frame.f_code.co_name != 'generate_esm_embeddings':
            return None
        if event != 'line':
            return trace
        line = linecache.getline('/app/utils.py', frame.f_lineno).strip()
        local = frame.f_locals
        if line == 'minibatch_max_length = toks.size(1)':
            ids = local['toks'][0].tolist()
            alphabet = local['esm_alphabet']
            decoded = [alphabet.get_tok(t) for t in ids]
            seq = local['seq']
            emit('tokenized', dict(sequence=seq, sequence_sha256=hashlib.sha256(seq.encode()).hexdigest(),
                amino_acids=len(seq), token_ids=ids, decoded_tokens=decoded, token_count=len(ids),
                prepend_bos=bool(alphabet.prepend_bos), append_eos=bool(alphabet.append_eos),
                input_string=local['strs'][0], source_line=frame.f_lineno))
        elif line == 'tokens_list.append(tokens)':
            tokens = local['tokens']
            emit('chunk_completed', dict(start=local['start'], requested_end=local['end'],
                token_ids=local['toks'][0, local['start']:local['end']].tolist(),
                representation_shape=list(tokens.shape), finite=bool(torch.isfinite(tokens).all()),
                source_line=frame.f_lineno))
        elif line.startswith("output_file = open(f'{esm_embeddings_dir}/"):
            embedding = local['seq_embedding']
            emit('embedding_completed', dict(shape=list(embedding.shape),
                finite=bool(torch.isfinite(embedding).all()), source_line=frame.f_lineno))
        return trace

    sys.path.insert(0, '/app')
    sys.argv = report['entrypoint']
    try:
        sys.settrace(trace)
        budget = (resident_thread_budget(torch, os.environ, report.setdefault('thread_configuration', {}))
                  if os.environ.get('T01_RESIDENT_OFFLINE') == '1' else nullcontext())
        with budget:
            runpy.run_path('/app/predict.py', run_name='__main__')
        report['python_exit_code'] = 0
    except SystemExit as exc:
        report['python_exit_code'] = exc.code
        raise
    except BaseException as exc:
        report.update(error_type=type(exc).__name__, error=str(exc), python_exit_code=1)
        raise
    finally:
        sys.settrace(None)
        events.close()
        usage = resource.getrusage(resource.RUSAGE_SELF)
        report.update(elapsed_seconds=time.monotonic()-started, peak_rss_kib=usage.ru_maxrss,
            user_cpu_seconds=usage.ru_utime, system_cpu_seconds=usage.ru_stime,
            torch_intraop_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads())
        # Observe bytes only, after the original tool has closed its outputs.
        report['native_output_sha256'] = {
            p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((output/'result').rglob('*')) if p.is_file()}
        (output/'runtime.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
