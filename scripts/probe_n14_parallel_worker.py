"""Execute production worker on archived nine-aa engineering inputs, offline."""
import json,sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from test_foldx_development import recording
from t01_phase1_real.development.foldx import policy
from t01_phase1_real.development.foldx.result import _buildmodel
from t01_phase1_real.development.variant_report.structures import validate
from t01_phase1_real.common import encode,decode,sha

def main():
    out=ROOT/'reports/n14-performance-20260928'/('production-worker-'+sys.argv[1])
    out.mkdir(parents=True,exist_ok=False)
    _,body,files,_=recording('buildmodel-three-variants-five-runs')
    for n,raw in files.items():
        if n.startswith('native/') or n in ('input.json','input.fasta'):
            p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    (out/'output').mkdir()
    cmd=['docker','run','--rm','--network','none','--cpus','2','--memory','4g','--pids-limit','128']
    for source,target,readonly in [(out/'native','/native',True),(out/'input.json','/input.json',True),
        (out/'input.fasta','/input.fasta',True),(out/'output','/out',False),
        (policy.HERE,'/worker',True),(policy.PACKAGE,'/app',True)]:
        cmd+=['--mount',f'type=bind,source={source},target={target}'+(',readonly' if readonly else '')]
    cmd+=['--entrypoint','python',policy.IMAGE,'-B','/worker/worker.py']
    done=subprocess.run(cmd,capture_output=True,timeout=300)
    (out/'stdout.txt').write_bytes(done.stdout);(out/'stderr.txt').write_bytes(done.stderr)
    (out/'launch.json').write_bytes(encode(dict(argv=cmd,exit_code=done.returncode)))
    if done.returncode:raise RuntimeError(done.stderr.decode(errors='replace')[-2000:])
    native={n:v for n,v in files.items() if not n.startswith('output/')}
    native.update({'output/'+p.relative_to(out/'output').as_posix():p.read_bytes() for p in (out/'output').rglob('*') if p.is_file()})
    runtime=decode(native['output/runtime.json']);payload=decode(native['native/payload.json'])
    rows,complete=_buildmodel(payload,runtime,native)
    checked=validate(body,native)
    assert len(rows)==3 and len(checked)==31 and all(r['runs']==5 for r in rows)
    receipt=dict(status='PASS',rows=rows,completeness=complete,validated_pdb_count=len(checked),
        native_inventory_match=runtime['native_output_sha256']=={n[7:]:sha(v) for n,v in native.items() if n.startswith('output/') and n!='output/runtime.json'},
        scope='9-aa native engineering fixture, not PCV2 acceptance or throughput')
    assert receipt['native_inventory_match']
    (out/'verification.json').write_bytes(encode(receipt));print(json.dumps(receipt))

if __name__=='__main__':main()
