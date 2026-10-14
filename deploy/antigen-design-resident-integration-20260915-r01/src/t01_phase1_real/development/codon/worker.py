"""One owned Python process, no socket or subprocess access in optimizer execution."""
import sys
from pathlib import Path

def deny_external(event,args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system','os.spawn','os.posix_spawn'):
        raise PermissionError('N16 offline optimizer prohibits network and subprocess access')

def main():
    sys.addaudithook(deny_external)
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    from t01_phase1_real.common import decode,encode,sha
    from t01_phase1_real.development.codon.compute import optimize
    path=Path(sys.argv[1]);body=decode((path/'input.json').read_bytes())
    inputs={p.name:p.read_bytes() for p in (path/'input').iterdir() if p.is_file()}
    value=optimize(body,inputs['codon-table.csv'])
    output=dict(result=value,input_hashes={k:sha(v) for k,v in inputs.items()},request_sha256=sha((path/'input.json').read_bytes()),
        network_guard='python_audit_socket_and_subprocess_denied')
    with (path/'output/observation.json').open('xb') as f:f.write(encode(output))

if __name__=='__main__':
    try:main()
    except Exception:
        import traceback
        (Path(sys.argv[1])/'output/error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise SystemExit(1)
