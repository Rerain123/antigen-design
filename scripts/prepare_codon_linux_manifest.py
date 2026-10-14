"""Derive a separate Linux N16 inventory from pinned wheel payloads, not a live installation."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile
from email.parser import BytesParser

def digest(raw):return hashlib.sha256(raw).hexdigest()

def build(windows_manifest, wheel_roots):
    original=json.loads(Path(windows_manifest).read_bytes())
    selected={}
    for root in wheel_roots:
        for path in sorted(Path(root).glob('*.whl')):
            with zipfile.ZipFile(path) as archive:
                names=archive.namelist()
                metadata=[n for n in names if n.count('/')==1 and n.endswith('.dist-info/METADATA')]
                if len(metadata)!=1:raise ValueError('One wheel metadata file required')
                meta=BytesParser().parsebytes(archive.read(metadata[0]))
                name=meta['Name'].lower().replace('_','-')
                if name not in original['packages']:continue
                version=meta['Version']
                if version!=original['packages'][name]['version']:raise ValueError('Unapproved version: '+name)
                if name in selected:raise ValueError('Duplicate wheel: '+name)
                files=[]
                for relative in sorted(names):
                    p=PurePosixPath(relative)
                    if p.is_absolute() or '..' in p.parts or '\\' in relative:raise ValueError('Unsafe wheel path')
                    if relative.endswith('/') or relative.endswith('.dist-info/RECORD'):continue
                    if '.data' in p.parts[0]:raise ValueError('Wheel relocation requires explicit handling')
                    if p.suffix in ('.pyd','.dll'):raise ValueError('Windows binary in Linux wheel')
                    raw=archive.read(relative)
                    files.append(dict(path=relative,size_bytes=len(raw),sha256=digest(raw)))
                selected[name]=dict(version=version,wheel=dict(file=path.name,sha256=digest(path.read_bytes()),size_bytes=path.stat().st_size),files=files)
    if set(selected)!=set(original['packages']):raise ValueError('Missing packages: '+str(set(original['packages'])-set(selected)))
    return dict(schema_version='0.1.0',platform='linux-x86_64',python=[3,11],
        inventory_policy='exact-wheel-payload-excluding-installer-generated-RECORD; includes native binaries',
        windows_manifest_sha256=digest(Path(windows_manifest).read_bytes()),table=original['table'],packages=selected)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--windows-manifest',type=Path,required=True);p.add_argument('--wheel-root',type=Path,action='append',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    value=build(a.windows_manifest,a.wheel_root)
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    with a.output.open('xb') as stream:stream.write(raw)
    print(json.dumps(dict(sha256=digest(raw),packages=len(value['packages']),files=sum(len(x['files']) for x in value['packages'].values()))))
