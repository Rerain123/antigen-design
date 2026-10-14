"""Read-only indexed originals with bounded per-query evidence snapshots."""
import sqlite3
import zlib
from functools import lru_cache
from ...common import decode,encode,ensure,sha
from ...files import no_links
from ..blast.policy import _hash_file
from .swissprot import project

@lru_cache(maxsize=8)
def verified(path,size,digest,identity):
    actual_size,actual_hash=_hash_file(path)
    ensure((actual_size,actual_hash)==(size,digest),'HASH_MISMATCH','N09 indexed database bytes changed')
    return True

def database(folder,body,raw,manifest):
    ensure(set(manifest)=={'schema_version','database_id','qualification','purpose','source','files','records',
        'source_sha256','format','lookup','fasta_all_records_verified'} and manifest['format']=='SQLITE_ZLIB_SWISSPROT_DAT_V1'
        and manifest['lookup']=='exact_sequence' and manifest['fasta_all_records_verified'] is True,
        'HASH_MISMATCH','Unsupported indexed N09 schema')
    ensure(len(manifest['files'])==1,'HASH_MISMATCH','One indexed database required')
    row=manifest['files'][0]
    ensure(set(row)=={'path','bytes','sha256'} and row['path']=='annotations.sqlite3'
        and type(row['bytes']) is int and 0<row['bytes']<8*1024**3,'HASH_MISMATCH','Invalid N09 index inventory')
    path=no_links(folder/row['path']);st=path.stat();identity=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
    verified(path,row['bytes'],row['sha256'],identity)
    sequence=body['parent']['sequence'] if body['parent'] else body['protein_sequence']
    files={'input/annotation-manifest.json':raw};entries=[];details=[];total=0
    with sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        total=db.execute('SELECT count(*) FROM entries WHERE sequence_sha256=?',(sha(sequence.encode()),)).fetchone()[0]
        ensure(total<=500,'OUTPUT_INVALID','Too many exact annotation matches; explicit selection required')
        matches=list(db.execute('SELECT accession,raw_sha256,record FROM entries WHERE sequence_sha256=? ORDER BY accession',(sha(sequence.encode()),)))
        if body['entry_id'] and not any(r[0]==body['entry_id'] for r in matches):
            matches+=list(db.execute('SELECT accession,raw_sha256,record FROM entries WHERE accession=?',(body['entry_id'],)))
    for accession,digest,compressed in matches:
        decoder=zlib.decompressobj();original=decoder.decompress(compressed,4*1024**2+1)
        ensure(len(original)<=4*1024**2 and decoder.eof and not decoder.unused_data,'OUTPUT_INVALID','Invalid/oversized Swiss-Prot record')
        ensure(sha(original)==digest,'HASH_MISMATCH','Swiss-Prot record changed')
        entry,audit=project(original,body)
        ensure(entry['primaryAccession']==accession,'HASH_MISMATCH','Indexed accession mismatch')
        entries.append(entry);files['input/swissprot/'+accession+'.dat']=original
        details.append(dict(accession=accession,raw_sha256=digest,projection_audit=audit))
    data=encode(entries);ensure(len(data)<=16*1024**2,'OUTPUT_INVALID','Selected annotation snapshot too large')
    files['input/annotation-entries.json']=data
    files['input/annotation-lookup.json']=encode(dict(mode='exact_sequence',query_sha256=sha(sequence.encode()),
        organism_filter=body['organism_name'],exact_sequence_matches=total,records=details,
        homology_transfer=False,database_sha256=row['sha256']))
    after=path.stat()
    ensure(identity==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'HASH_MISMATCH','N09 database changed during lookup')
    return dict(database_id=manifest['database_id'],manifest_sha256=sha(raw),qualification=manifest['qualification'],
        source=manifest['source'],files=manifest['files']),files

def replay(body,files):
    lookup=decode(files['input/annotation-lookup.json']);entries=[]
    for row in lookup['records']:
        raw=files['input/swissprot/'+row['accession']+'.dat']
        ensure(sha(raw)==row['raw_sha256'],'HASH_MISMATCH','Snapshot Swiss-Prot bytes changed')
        entry,audit=project(raw,body)
        ensure(entry['primaryAccession']==row['accession'] and audit==row['projection_audit'],
            'OUTPUT_INVALID','Swiss-Prot projection audit changed')
        entries.append(entry)
    ensure(encode(entries)==files['input/annotation-entries.json'],'OUTPUT_INVALID','Swiss-Prot annotation projection changed')
    return lookup
