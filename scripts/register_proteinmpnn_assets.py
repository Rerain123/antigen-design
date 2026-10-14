"""One-time asset registration from verified official Git blobs and a successful GPU image probe."""
from pathlib import Path
import hashlib
import sys

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development.proteinmpnn import policy


def main():
    evidence=REPO/'discovery/t01-phase1-real/w5/proteinmpnn-assets-20260908'
    image=decode((evidence/'image-inspect.json').read_bytes())[0]
    environment=decode((evidence/'environment.json').read_bytes())
    assert image['Id']==policy.IMAGE and image['Architecture']=='amd64' and image['Os']=='linux'
    assert environment['torch']=='2.7.1+cu128' and environment['gpu_matmul_sum']==32768.0 and environment['network_interfaces']==[[1,'lo']]
    tree_raw=(policy.PACKAGE/'upstream-tree.json').read_bytes();tree=decode(tree_raw)
    assert tree['sha']==policy.COMMIT and tree['truncated'] is False
    indexed={r['path']:r for r in tree['tree']};files=[]
    for path in sorted(policy.PACKAGE.rglob('*')):
        if not path.is_file():continue
        package_path=path.relative_to(policy.PACKAGE).as_posix();raw=path.read_bytes()
        upstream_path='helper_scripts/other_tools/make_omit_AA.py' if package_path=='helper_scripts/make_omit_AA.py' else package_path
        blob=None
        if package_path!='upstream-tree.json':
            blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
            assert blob==indexed[upstream_path]['sha'] and len(raw)==indexed[upstream_path]['size']
        files.append(dict(path=path.relative_to(REPO).as_posix(),package_path=package_path,upstream_path=upstream_path,
            bytes=len(raw),sha256=sha(raw),git_blob_sha1=blob))
    for name in ('5L33','6MRR'):
        raw=(evidence/(name+'.pdb')).read_bytes();key='inputs/PDB_monomers/pdbs/'+name+'.pdb'
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==indexed[key]['sha']
    registry=dict(schema_version='0.1.0',engine='ProteinMPNN',commit=policy.COMMIT,model=policy.MODEL,
        image=policy.IMAGE,image_reference=policy.IMAGE,license='MIT',
        source='https://github.com/dauparas/ProteinMPNN/tree/'+policy.COMMIT,
        files=files,source_manifest_sha256=sha(encode(files)),archive_sha256=sha(encode(files)),
        archive_sha256_semantics='compatibility field: SHA256 of canonical file manifest; assets fetched as original Git blobs, not archive',
        environment={k:environment[k] for k in ('python','torch','numpy','cuda','gpu_name','gpu_capability')},
        environment_receipt=dict(path=(evidence/'environment.json').relative_to(REPO).as_posix(),sha256=sha((evidence/'environment.json').read_bytes())),
        scientific_signoff=None,production_status='NOT_DEPLOYED')
    with (policy.HERE/'assets.json').open('xb') as stream:stream.write(encode(registry))
    with (evidence/'source-verification.json').open('xb') as stream:stream.write(encode(registry))
    print(len(files),'official files registered with immutable image',policy.IMAGE)


if __name__=='__main__':main()
