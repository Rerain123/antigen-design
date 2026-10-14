"""One owned Python process, no socket or subprocess access in optimizer execution."""
import sys
import os
from pathlib import Path

def deny_external(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.spawn','os.posix_spawn'):
        raise PermissionError('N16 offline optimizer prohibits network and subprocess access')

def main():
    # Set before NumPy/OpenBLAS import; 192 host CPUs otherwise exhaust the
    # owned Linux worker's 1 GiB address-space budget during library startup.
    threads={}
    if sys.platform=='linux':
        threads={name:'1' for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}
        os.environ.update(threads)
    sys.addaudithook(deny_external)
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    from t01_phase1_real.common import decode,encode,sha
    from t01_phase1_real.development.codon.compute import optimize
    path=Path(sys.argv[1]);body=decode((path/'input.json').read_bytes())
    inputs={p.name:p.read_bytes() for p in (path/'input').iterdir() if p.is_file()}
    value=optimize(body,inputs['codon-table.csv'])
    output=dict(result=value,input_hashes={k:sha(v) for k,v in inputs.items()},request_sha256=sha((path/'input.json').read_bytes()),
        network_guard='python_audit_socket_and_subprocess_denied',thread_environment=threads)
    with (path/'output/observation.json').open('xb') as f:f.write(encode(output))

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        (Path(sys.argv[1])/'output/error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise SystemExit(1)
