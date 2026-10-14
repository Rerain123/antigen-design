"""Register verified original ESM Git blobs, official checkpoint and real GPU environment."""
import hashlib
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode,encode,sha
from t01_phase1_real.development.esm_if1 import policy


def main():
    folder=REPO/'discovery/t01-phase1-real/w5/esm-if1-assets-20260908'
    tree=decode((folder/'upstream-tree.json').read_bytes());indexed={r['path']:r for r in tree['tree']}
    image=decode((folder/'image-inspect.json').read_bytes())[0];env=decode((folder/'environment-r01.json').read_bytes())
    assert tree['sha']==policy.COMMIT and not tree['truncated'] and image['Id']==policy.IMAGE
    assert abs(env['official_scores'][0]-env['loss_mean'])<1e-6 and env['network_interfaces']==[[1,'lo']]
    files=[]
    for path in sorted(policy.PACKAGE.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(policy.PACKAGE).as_posix();raw=path.read_bytes();blob=None
        if not relative.startswith('weights/'):
            blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert blob==indexed[relative]['sha'] and len(raw)==indexed[relative]['size']
        files.append(dict(path=path.relative_to(REPO).as_posix(),package_path=relative,bytes=len(raw),sha256=sha(raw),git_blob_sha1=blob,
            source=('https://dl.fbaipublicfiles.com/fair-esm/models/'+path.name) if relative.startswith('weights/') else
                'https://raw.githubusercontent.com/facebookresearch/esm/'+policy.COMMIT+'/'+relative))
    value=dict(schema_version='0.1.0',engine='ESM-IF1',model=policy.MODEL,commit=policy.COMMIT,image=policy.IMAGE,
        license='MIT; original source license retained',files=files,archive_sha256=sha(encode(files)),
        archive_sha256_semantics='compatibility field: SHA256 of canonical source/weight manifest; no archive claimed',
        environment={k:env[k] for k in ('python','torch','numpy','cuda','biotite','scipy','torch_geometric','gpu_name','gpu_capability')},
        evidence_receipts={n:dict(path=(folder/n).relative_to(REPO).as_posix(),sha256=sha((folder/n).read_bytes()))
            for n in ('environment-r01.json','upstream-tree.json','upstream-commit.json','image-inspect.json')},
        scientific_signoff=None,production_status='NOT_DEPLOYED')
    for path in (policy.HERE/'assets.json',folder/'source-verification.json'):
        with path.open('xb') as stream:stream.write(encode(value))
    print(len(files),'fixed files',policy.IMAGE,env['official_scores'])


if __name__=='__main__':main()
