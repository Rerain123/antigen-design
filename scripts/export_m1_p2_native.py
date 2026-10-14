"""Export registered native P2 outputs, retaining immutable ArtifactRefs in an index."""
import base64
import hashlib
import json
import run_m1_p2_probe as p

CODE=r'''
import base64,io,zipfile
from t01_phase1_real.common import sha
index=[];buffer=io.BytesIO()
with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
    for name,jid in task['jobs'].items():
        j=rt.get(jid);ensure(j['run_id']==run_id,'FORBIDDEN','Foreign export job')
        value=rt.result(jid)
        for item in value['raw_artifacts']:
            path=item['path']
            # Source snapshots are already recursively hash-verified in the audit.
            # This bundle contains actual new outputs and native run receipts.
            if not path.startswith(('output/','resident/')):continue
            if path.startswith('resident/') and not path.endswith(('execution.json','request.json','executor-observation.json','stderr.txt','stdout.txt')):continue
            ensure(not Path(path).is_absolute() and '..' not in Path(path).parts,'FORBIDDEN','Unsafe evidence path')
            raw=rt.artifact_bytes(jid,item['artifact']['artifact_id'])
            target=name+'/'+path
            archive.writestr(target,raw)
            index.append(dict(path=target,artifact=item['artifact']))
    archive.writestr('artifact-index.json',encode(dict(run_id=run_id,files=index,scientific_gate='CLOSED',usable_for_pipeline=False)))
raw=buffer.getvalue()
print(json.dumps(dict(data=base64.b64encode(raw).decode(),sha256=sha(raw),bytes=len(raw),files=len(index))))
'''


def main():
    task=p.context();audit=json.loads((p.OUT/'audit-summary.json').read_bytes())
    task['jobs']={n:r['job_id'] for n,r in audit['jobs'].items()}
    result=p.deploy.remote(p.PREAMBLE+CODE,task)
    raw=base64.b64decode(result.pop('data'),validate=True)
    assert len(raw)==result['bytes'] and hashlib.sha256(raw).hexdigest()==result['sha256']
    (p.OUT/'native-evidence.zip').write_bytes(raw)
    p.save('native-evidence-manifest.json',dict(result,run_id=task['run_id'],path='native-evidence.zip'))
    print(json.dumps(result))


if __name__=='__main__':main()
