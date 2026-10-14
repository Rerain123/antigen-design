"""Stream verified originals into a compact, exact-sequence SQLite index."""
import datetime,gzip,hashlib,json,os,shutil,sqlite3,sys,zlib
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(4*1024**2):h.update(b)
    return h.hexdigest()

def run(source,dest):
    source=Path(source);dest=Path(dest);dest.mkdir(parents=True,exist_ok=False)
    state=dict(state='verifying_source',records=0)
    def status(**kw):
        state.update(kw,updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        p=dest/'status.pending';p.write_text(json.dumps(state));p.replace(dest/'status.json')
    status()
    try:
        receipt=json.loads((source/'status.json').read_bytes());assert receipt['state']=='downloaded_verified'
        refs={r['name']:r for r in receipt['files']}
        for name in ('uniprot_sprot.dat.gz','uniprot_sprot.fasta.gz'):
            assert digest(source/name)==refs[name]['sha256']
        assert shutil.disk_usage(dest).free>3*1024**3
        db=sqlite3.connect(dest/'annotations.sqlite3');db.execute('PRAGMA journal_mode=DELETE')
        db.execute('CREATE TABLE entries (accession TEXT PRIMARY KEY,sequence_sha256 TEXT NOT NULL,raw_sha256 TEXT NOT NULL,record BLOB NOT NULL)')
        block=[];seq=[];inseq=False;accession=None;count=0
        status(state='importing')
        with gzip.open(source/'uniprot_sprot.dat.gz','rb') as f:
            for line in f:
                block.append(line)
                if line.startswith(b'AC   ') and accession is None:accession=line[5:].split(b';')[0].decode()
                if line.startswith(b'SQ   '):inseq=True
                elif line.startswith(b'//'):
                    raw=b''.join(block);sequence=b''.join(seq);assert accession and sequence
                    db.execute('INSERT INTO entries VALUES (?,?,?,?)',(accession,hashlib.sha256(sequence).hexdigest(),hashlib.sha256(raw).hexdigest(),zlib.compress(raw)))
                    count+=1;block=[];seq=[];inseq=False;accession=None
                    if count%5000==0:
                        db.commit();status(records=count)
                        assert shutil.disk_usage(dest).free>1024**3
                elif inseq:seq.append(b''.join(line.split()))
        assert not block and count==receipt['record_count'];db.commit()
        db.execute('CREATE INDEX by_sequence ON entries(sequence_sha256)');db.commit()
        # Independently bind every canonical FASTA record to the DAT record index.
        seen=0;acc=None;sequence=[]
        def verify():
            row=db.execute('SELECT sequence_sha256 FROM entries WHERE accession=?',(acc,)).fetchone()
            assert row and row[0]==hashlib.sha256(b''.join(sequence)).hexdigest(),acc
        with gzip.open(source/'uniprot_sprot.fasta.gz','rb') as f:
            for line in f:
                if line.startswith(b'>'):
                    if acc is not None:verify();seen+=1
                    acc=line.split(b'|')[1].decode();sequence=[]
                else:sequence.append(line.strip())
            if acc is not None:verify();seen+=1
        assert seen==count
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
        file=dest/'annotations.sqlite3'
        manifest=dict(schema_version='0.2.0',database_id=dest.name,qualification='TARGET_DATABASE_UNREVIEWED',
            purpose='N09_LOCAL_ANNOTATIONS',source=dict(name='UniProtKB Swiss-Prot',version=receipt['release'],
            release_date='2026-09-02',license='CC BY 4.0',reference=refs['uniprot_sprot.dat.gz']['url']),
            files=[dict(path=file.name,bytes=file.stat().st_size,sha256=digest(file))],
            records=count,source_sha256={n:refs[n]['sha256'] for n in ('uniprot_sprot.dat.gz','uniprot_sprot.fasta.gz')},
            format='SQLITE_ZLIB_SWISSPROT_DAT_V1',lookup='exact_sequence',fasta_all_records_verified=True)
        (dest/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,separators=(',',':')))
        status(state='imported_verified',records=count,database_bytes=file.stat().st_size,
            manifest_sha256=digest(dest/'manifest.json'),source_directory=str(source),destination=str(dest))
    except BaseException as e:status(state='failed',error=repr(e));raise

if __name__=='__main__':run(*sys.argv[1:])
