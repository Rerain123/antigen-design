"""N03 prebuilt protein volumes: explicit metadata, alias and byte inventory.

This verifier never registers a staging directory or infers an upstream checksum.
"""
from pathlib import PurePosixPath
import re
from urllib.parse import urlsplit
from ...common import decode, ensure
from ...files import read_locked


def relative(name):
    return isinstance(name,str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,255}',name)) \
        and all(p not in ('','.', '..') for p in name.split('/'))


def validate(folder,manifest):
    p=manifest['prebuilt'];blast=manifest['blast'];entries=manifest['files']
    ensure(isinstance(p,dict) and set(p)=={'metadata_path','alias_path','volume_prefixes','integrity'}
        and relative(p['metadata_path']) and relative(p['alias_path'])
        and p['integrity']=='LOCAL_SHA256_NO_UPSTREAM_CHECKSUM',
        'HASH_MISMATCH','Prebuilt metadata/alias/integrity declaration differs')
    prefix=blast['db_prefix'];volumes=p['volume_prefixes']
    ensure(isinstance(volumes,list) and 2<=len(volumes)<=10000 and len(volumes)==len(set(volumes))
        and all(relative(v) and re.fullmatch(re.escape(prefix)+r'\.[0-9]{2,4}',v) for v in volumes)
        and [int(v.rsplit('.',1)[1]) for v in volumes]==list(range(len(volumes)))
        and p['alias_path']==prefix+'.pal',
        'HASH_MISMATCH','Prebuilt volume identities must be complete and ordered')
    paths={e['path']:e['role'] for e in entries}
    ensure(paths.get(p['metadata_path'])=='metadata' and paths.get(p['alias_path'])=='alias'
        and list(paths.values()).count('metadata')==1 and list(paths.values()).count('alias')==1
        and 'source_fasta' not in paths.values(), 'HASH_MISMATCH','Prebuilt source inventory differs')
    alias=read_locked(folder/p['alias_path'],1024*1024).decode('utf-8')
    lines=[line.strip().split() for line in alias.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    # Restrict to ordinary whole-database aliases; no hidden OID/GI subset or path indirection.
    ensure(all(line[0] in ('TITLE','DBLIST','NSEQ','LENGTH') for line in lines)
        and sum(line[0]=='DBLIST' for line in lines)==1,'HASH_MISMATCH','Unsupported or ambiguous BLAST alias')
    listed=next(line[1:] for line in lines if line[0]=='DBLIST')
    parent=PurePosixPath(prefix).parent
    ensure(all(relative(v) and '/' not in v for v in listed)
        and [str(parent/v) for v in listed]==volumes,'HASH_MISMATCH','Alias and volume inventory differ')
    for volume in volumes:
        ensure(all(paths.get(volume+suffix)=='index' for suffix in ('.phr','.pin','.psq')),
            'HASH_MISMATCH','Prebuilt protein volume core set is incomplete: '+volume)
    meta=decode(read_locked(folder/p['metadata_path'],2*1024*1024))
    ensure(isinstance(meta,dict) and meta.get('dbname')==PurePosixPath(prefix).name
        and meta.get('dbtype')=='Protein' and meta.get('number-of-volumes')==len(volumes)
        and meta.get('number-of-sequences')==blast['sequence_count']
        and meta.get('last-updated','').split('T')[0]==manifest['source']['release_date']
        and type(meta.get('bytes-total')) is int and meta['bytes-total']>0,
        'HASH_MISMATCH','Prebuilt source metadata and registered identity differ')
    names=meta.get('files');ensure(isinstance(names,list) and names,'HASH_MISMATCH','Metadata inventory required')
    reference=manifest['source']['reference'].rstrip('/')+'/'
    declared=[]
    for item in names:
        ensure(isinstance(item,str),'HASH_MISMATCH','Metadata file entry must be a string')
        url=urlsplit(item)
        if url.scheme:
            ensure(item.startswith(reference) and item[len(reference):]==PurePosixPath(url.path).name,
                'HASH_MISMATCH','Metadata references a different snapshot')
            item=PurePosixPath(url.path).name
        ensure(relative(item) and '/' not in item,'HASH_MISMATCH','Metadata filename is unsafe')
        declared.append(str(parent/item))
    ensure(len(declared)==len(set(declared)) and set(declared)|{p['alias_path']}==
        {e['path'] for e in entries if e['role'] in ('index','alias')},
        'HASH_MISMATCH','Metadata and manifest inventories differ')
    by_path={e['path']:e for e in entries}
    declared_total=sum(by_path[path]['bytes'] for path in declared)
    # NCBI's nr metadata for the pinned 2025-06-24 snapshot counts the
    # per-volume database files but excludes taxonomy side files and .pxm.
    # All listed bytes are still independently declared and SHA-256 checked.
    auxiliary_suffixes={'.pal','.pdb','.pos','.pot','.ptf','.pto','.pxm'}
    core_total=sum(by_path[path]['bytes'] for path in declared
                   if PurePosixPath(path).suffix not in auxiliary_suffixes)
    ensure(meta['bytes-total'] in (declared_total,core_total),
        'HASH_MISMATCH','Metadata byte total differs from both complete and core file inventories')
    provenance={path for path,role in paths.items() if role=='provenance'}
    if provenance or manifest['qualification']=='TARGET_DATABASE_UNREVIEWED':
        expected={path+'.source.json' for path in declared}
        expected.add(p['alias_path']+'.source.json')
        ensure(provenance==expected,'HASH_MISMATCH','Prebuilt mirror source records are incomplete')
        urls=[]
        for path in sorted(set(declared)|{p['alias_path']}):
            sidecar=decode(read_locked(folder/(path+'.source.json'),8192))
            ensure(isinstance(sidecar,dict) and set(sidecar)=={'url','bytes','validator'}
                and type(sidecar['bytes']) is int and sidecar['bytes']==by_path[path]['bytes']
                and isinstance(sidecar['url'],str) and isinstance(sidecar['validator'],(str,type(None)))
                and urlsplit(sidecar['url']).scheme in ('http','https')
                and PurePosixPath(urlsplit(sidecar['url']).path).name==PurePosixPath(path).name,
                'HASH_MISMATCH','Prebuilt mirror source record differs from declared file')
            urls.append(sidecar['url'].rsplit('/',1)[0])
        ensure(len(set(urls))==1,'HASH_MISMATCH','Prebuilt mirror source records mix directories')
    for e in entries:
        if e['role']=='index':
            ensure(re.fullmatch(re.escape(prefix)+r'(?:\.[0-9]{2,4})?\.[a-z]+',e['path']),
                'HASH_MISMATCH','Mixed database index identity')
    return dict(volume_count=len(volumes),metadata_path=p['metadata_path'],alias_path=p['alias_path'],
        integrity=p['integrity'],upstream_checksum_verified=False)
