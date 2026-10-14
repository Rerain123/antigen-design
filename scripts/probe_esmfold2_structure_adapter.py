"""Local CPU replay of archived r02 bytes; not a new GPU prediction or target acceptance."""
import base64
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import encode,sha
from t01_phase1_real.development.esmfold2.standard import normalize,NAMES


def main():
    import tempfile
    folder=Path(tempfile.mkdtemp(prefix='esmfold2-s09-replay-',dir=ROOT/'.tmp'))
    bundle=json.loads((ROOT/'discovery/t01-phase1-real/esmfold2-target-20260917/backend-r02/latest.json').read_bytes())
    row=next(r for r in bundle['evidence'] if r['job']['tool_id']=='t01.real.esmfold2')
    blobs={a['ref']['artifact_id']:base64.b64decode(a['base64']) for a in row['artifacts']}
    result=json.loads(next(blobs[a['ref']['artifact_id']] for a in row['artifacts'] if a['ref']['role']=='result'))
    files={r['path']:blobs[r['artifact']['artifact_id']] for r in result['raw_artifacts']}
    standard=normalize({n:files['output/raw/'+n] for n in NAMES|{'manifest.json'}},json.loads(files['input.json']),result['binding'])
    structure=next(r for r in bundle['evidence'] if r['job']['tool_id']=='t01.real.ingest_structure')
    diag=json.loads(next(base64.b64decode(a['base64']) for a in structure['artifacts'] if a['ref']['role']=='diagnostic'))
    raw={a['ref']['artifact_id']:base64.b64decode(a['base64']) for a in structure['artifacts']}
    inputs={a['path']:raw[a['artifact']['artifact_id']] for a in diag['raw_artifacts']}
    body=json.loads(inputs['input.json']);binding=json.loads(inputs['binding.json'])
    derived=standard['tool-structure.cif'];body['structure_artifact'].update(sha256=sha(derived),size_bytes=len(derived))
    # Explicitly local rebound fixture. These bytes are never submitted to a task store.
    binding.update(structure_sha256=sha(derived),input_sha256=sha(encode(body)))
    evidence=dict(binding=binding,structure_artifact=body['structure_artifact'],quality=json.loads(standard['prediction-quality.json']))
    for name,data in [('input.json',encode(body)),('binding.json',encode(binding)),('input.structure',derived),('prediction-evidence.json',encode(evidence))]:
        (folder/name).write_bytes(data)
    (folder/'out').mkdir()
    cmd=['docker','run','--rm','--network','none','--read-only','--cpuset-cpus','0,1','--tmpfs','/tmp:rw,size=128m',
         '--entrypoint','/usr/local/bin/python']
    for src,dst,mode in [(folder/'out','/out','rw'),(ROOT/'src/t01_phase1_real/development/structure','/worker','ro'),
                         (ROOT/'src','/code','ro'),(ROOT/'docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json','/profile.json','ro')]:
        cmd+=['-v',str(src)+':'+dst+':'+mode]
    for name in ('input.json','binding.json','input.structure','prediction-evidence.json'):
        cmd+=['-v',str(folder/name)+':/'+name+':ro']
    cmd+=['t01-freesasa-g0:2.2.1-20260905','-B','/worker/worker.py']
    subprocess.run(cmd,check=True)
    report=json.loads((folder/'out/result/analysis.json').read_bytes())
    assert report['status']!='input_rejected' and report['mapping']['target_chain_id']=='A'
    assert report['quality']['quality']==evidence['quality']['quality']
    assert report['freesasa']['status']=='executed',report['freesasa']
    print('LOCAL_ARCHIVE_STRUCTURE_REPLAY_PASS',folder)
    print(json.dumps(dict(quality=report['quality']['quality'],rsa_status=report['rsa']['status'],
                         rsa_error=report['rsa']['error_code'],scientific_gate='CLOSED')))


if __name__=='__main__': main()
