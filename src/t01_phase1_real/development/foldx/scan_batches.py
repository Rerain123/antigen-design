"""Bounded execution/storage batches; never alter the allowed scientific scope."""
import hashlib
import io
from pathlib import Path, PurePosixPath
import shutil
import zipfile

POSITIONS_PER_BATCH = 16
MAX_ARCHIVE = 32 * 1024**2
MAX_EXPANDED = 256 * 1024**2


def plan(payload):
    tokens=payload['scan_tokens']; mapping=payload['position_mapping']
    if not tokens or len(tokens)!=len(mapping) or len(set(tokens))!=len(tokens):
        raise ValueError('Scan batch token/mapping coverage differs')
    return [dict(index=i//POSITIONS_PER_BATCH,scan_tokens=tokens[i:i+POSITIONS_PER_BATCH],
                 position_mapping=mapping[i:i+POSITIONS_PER_BATCH])
            for i in range(0,len(tokens),POSITIONS_PER_BATCH)]


def unpack(raw):
    try:return _unpack(raw)
    except (zipfile.BadZipFile,RuntimeError,NotImplementedError) as exc:
        raise ValueError('Invalid FoldX batch archive') from exc


def _unpack(raw):
    if len(raw)>MAX_ARCHIVE:raise ValueError('FoldX batch archive exceeds bound')
    out={};total=0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for item in archive.infolist():
            path=PurePosixPath(item.filename)
            if (item.orig_filename!=item.filename or item.is_dir() or path.is_absolute() or '..' in path.parts or '\\' in item.filename
                or ':' in item.filename or path.as_posix()!=item.filename or item.filename in out
                or item.external_attr>>16 & 0o170000 == 0o120000):
                raise ValueError('Unsafe or duplicate FoldX batch member')
            total+=item.file_size
            if total>MAX_EXPANDED or len(out)>=2048:raise ValueError('Expanded FoldX batch exceeds bound')
            out[item.filename]=archive.read(item)
    return out


def seal(folder, archive_path):
    if Path(folder).is_symlink() or Path(archive_path).is_symlink():raise ValueError('Batch archive symlink')
    folder=Path(folder).resolve();archive_path=Path(archive_path).resolve()
    if (folder.parent.name!='batches' or len(folder.name)!=4 or not folder.name.isdigit()
        or archive_path!=folder.with_suffix('.zip')):raise ValueError('Batch archive path differs')
    paths=sorted(folder.rglob('*'));total=0;hashes={}
    for p in paths:
        if p.is_symlink():raise ValueError('Batch output symlink')
        if p.is_file():
            total+=p.stat().st_size
            if total>MAX_EXPANDED or len(hashes)>=2048:raise ValueError('Batch output exceeds bound')
            hashes[p.relative_to(folder).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in hashes:archive.write(folder/name,name)
    raw=archive_path.read_bytes()
    restored=unpack(raw)
    if {n:hashlib.sha256(v).hexdigest() for n,v in restored.items()}!=hashes:
        raise ValueError('Batch archive roundtrip differs')
    # Delete only this newly produced directory after byte-for-byte archive QA.
    shutil.rmtree(folder)
    return dict(sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw),members=len(hashes),expanded_bytes=total)


def model_names(index):
    return [f'{prefix}target_Repair_{index}_{run}.pdb'
            for run in range(5) for prefix in ('','WT_')]


def seal_models(folder, count):
    """Lossless per-variant storage after the unchanged five-run BuildModel."""
    folder=Path(folder)
    if folder.is_symlink():raise ValueError('BuildModel output symlink')
    records=[]
    for index in range(1,count+1):
        names=model_names(index)
        hashes={}
        for name in names:
            path=folder/name
            if path.is_symlink() or not path.is_file():raise ValueError('Missing or unsafe BuildModel PDB')
            hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        batch=folder/'batches'/f'{index:04d}';batch.mkdir(parents=True)
        for name in names:(folder/name).rename(batch/name)
        receipt=seal(batch,batch.with_suffix('.zip'))
        records.append(dict(index=index,archive=f'buildmodel/batches/{index:04d}.zip',
                            member_sha256=hashes,**receipt))
    return records
