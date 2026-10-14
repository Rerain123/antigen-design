"""Inspect/hash and safely extract the user-provided academic archive; no supplied code is executed."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]
ARCHIVE=Path('C:/Users/wing/Downloads/DeepTMHMM-Academic-License-v1.0.zip')
PREFIX='DeepTMHMM-Academic-License-v1.0'


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    target=BATCH/'package_receipt.json'
    if target.exists():raise SystemExit('Receipt exists; do not overwrite received package')
    package_hash=digest(ARCHIVE)
    asset_root=ROOT/'var/t01-phase1-real/tool-assets'/('deeptmhmm-academic-1.0-'+package_hash[:12])
    if asset_root.exists():raise SystemExit('Asset directory already exists')
    records=[];skipped=[];seen=set()
    with zipfile.ZipFile(ARCHIVE) as z:
        members=[]
        for member in z.infolist():
            name=member.filename
            parts=PurePosixPath(name).parts
            mode=member.external_attr>>16
            if '\\' in name or ':' in name or name.startswith('/') or any(p in {'..','.'} or p.rstrip(' .')!=p for p in parts):
                raise ValueError('Unsafe archive member path')
            if stat.S_ISLNK(mode) or member.flag_bits&1:
                raise ValueError('Symlink/encrypted archive member is not supported')
            if member.is_dir():continue
            if parts[0]=='__MACOSX':
                skipped.append({'path':name,'reason':'macOS metadata','bytes':member.file_size});continue
            if parts[0]!=PREFIX or len(parts)<2:raise ValueError('Unexpected archive root')
            relative=Path(*parts[1:])
            path=(asset_root/relative).resolve()
            if not path.is_relative_to(asset_root.resolve()) or str(path).casefold() in seen:
                raise ValueError('Unsafe or duplicate extraction target')
            seen.add(str(path).casefold())
            if member.file_size>3_000_000_000:raise ValueError('Unexpected individual asset size')
            members.append((member,relative,path))
        if sum(m.file_size for m,_,_ in members)>3_000_000_000:raise ValueError('Unexpected total asset size')
        asset_root.mkdir(parents=True)
        for member,relative,path in members:
            path.parent.mkdir(parents=True,exist_ok=True)
            h=hashlib.sha256();size=0
            with z.open(member) as source,path.open('xb') as out:
                for block in iter(lambda:source.read(8*1024*1024),b''):
                    h.update(block);out.write(block);size+=len(block)
            if size!=member.file_size:raise ValueError('Extracted size differs')
            records.append({'path':relative.as_posix(),'bytes':size,'sha256':h.hexdigest(),'archive_member':member.filename})
            if path.suffix not in {'.pt','.model'}:
                copy=BATCH/'package_sources'/relative
                copy.parent.mkdir(parents=True,exist_ok=True);copy.write_bytes(path.read_bytes())
            print(json.dumps({'extracted':relative.as_posix(),'bytes':size}),flush=True)
    expert=ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    receipt={'recorded_at':datetime.now(timezone.utc).isoformat(),'source':'USER_PROVIDED_LOCAL_ARCHIVE',
             'source_path':str(ARCHIVE),'archive_sha256':package_hash,'archive_bytes':ARCHIVE.stat().st_size,
             'asset_root':asset_root.relative_to(ROOT).as_posix(),'files':records,'skipped_metadata':skipped,
             'declared_product':'DeepTMHMM 1.0 - Academic Version','license_declared':'CC BY-NC-SA 4.0; see package LICENSE.txt and README.txt',
             'upstream_download_receipt':'NOT_PROVIDED; do not claim independent publisher signature verification',
             'usage_source':'docs/project/sources/PHASE1_W1_DEEPTMHMM_USAGE_20260905.json',
             'expert_sources_before':{p.relative_to(ROOT).as_posix():digest(p) for p in expert.iterdir() if p.is_file()},
             'model_execution':'NOT_RUN_AT_RECEIPT','production_status':'NOT_DEPLOYED'}
    target.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(records),'archive_sha256':package_hash,'asset_root':receipt['asset_root']}))


if __name__=='__main__':main()
