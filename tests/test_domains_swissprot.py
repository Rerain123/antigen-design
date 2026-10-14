"""Indexed N09 selection, source fidelity and missing-data behavior."""
import copy,json,sqlite3,zlib
import pytest
from t01_phase1_real.common import encode,sha,RuntimeFault,decode
from t01_phase1_real.development.domains import policy,service
from t01_phase1_real.development.domains.swissprot import project

SEQ='ACDEFGHIKLMNPQRSTVWY'
def record(acc='P00001',organism='Example virus'):
    return f'''ID   TEST_TEST               Reviewed;          19 AA.
AC   {acc};
DT   01-JAN-2000, integrated into UniProtKB/Swiss-Prot.
DT   01-JAN-2000, sequence version 1.
DT   01-JAN-2000, entry version 1.
DE   RecName: Full=Test protein;
OS   {organism}.
OC   Viruses.
OX   NCBI_TaxID=1;
FT   DOMAIN          2..8
FT                   /note="Verified source domain"
FT   ACT_SITE        <10
FT   REGION          P00001-2:2..4
SQ   SEQUENCE   19 AA;  2000 MW;  0000000000000000 CRC64;
     {SEQ}
//
'''.encode()

def package(tmp_path,records=None):
    folder=tmp_path/'swissprot-test';folder.mkdir()
    records=records or [record()]
    path=folder/'annotations.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE entries(accession TEXT PRIMARY KEY,sequence_sha256 TEXT,raw_sha256 TEXT,record BLOB)')
        for raw in records:
            accession=raw.split(b'AC   ')[1].split(b';')[0].decode()
            db.execute('INSERT INTO entries VALUES(?,?,?,?)',(accession,sha(SEQ.encode()),sha(raw),zlib.compress(raw)))
        db.execute('CREATE INDEX by_sequence ON entries(sequence_sha256)')
    manifest=dict(schema_version='0.2.0',database_id=folder.name,qualification='TARGET_DATABASE_UNREVIEWED',purpose='N09_LOCAL_ANNOTATIONS',
        source=dict(name='Swiss-Prot',version='test',release_date='2026-09-02',license='CC BY 4.0',reference='fixture'),
        files=[dict(path=path.name,bytes=path.stat().st_size,sha256=sha(path.read_bytes()))],records=len(records),source_sha256={},
        format='SQLITE_ZLIB_SWISSPROT_DAT_V1',lookup='exact_sequence',fasta_all_records_verified=True)
    raw=encode(manifest);(folder/'manifest.json').write_bytes(raw)
    b=dict(protein_sequence=SEQ,user_sequence_id='n09-test',organism_name=None,database_id=folder.name,database_manifest_sha256=sha(raw),
        entry_id=None,parent=None,user_annotations=[],timeout_seconds=60,
        topology_input=dict(state='not_provided',artifact=None,reason_code=None),structure_input=dict(state='not_provided',artifact=None,reason_code=None))
    return b,path

def test_indexed_lookup_projects_real_coordinates_and_replays(tmp_path):
    b,path=package(tmp_path);policy.request(encode(b))
    receipt,files=policy.database(tmp_path,b);v=service.evaluate(b,files)
    assert v['lookup']['selected_entry']=='P00001' and v['lookup']['mode']=='exact_sequence'
    assert any(r['type']=='domain' and r['start']==2 and r['end']==8 for r in v['functional_domains'])
    assert 'UNCERTAIN_FEATURE_COORDINATES' in v['review_reasons']
    assert v['annotation_provenance']['records'][0]['projection_audit'][0]['reason']=='ISOFORM_COORDINATES_NOT_CANONICAL'
    changed=dict(files);entries=decode(files['input/annotation-entries.json']);entries[0]['features'][0]['location']['start']['value']=3
    changed['input/annotation-entries.json']=encode(entries)
    with pytest.raises(RuntimeFault):service.evaluate(b,changed)

def test_missing_ambiguous_and_explicit_organism(tmp_path):
    b,_=package(tmp_path,[record(),record('P00002','Other virus')])
    _,f=policy.database(tmp_path,b);assert service.evaluate(b,f)['lookup']['status']=='ambiguous'
    b['organism_name']='Example virus';_,f=policy.database(tmp_path,b)
    assert service.evaluate(b,f)['lookup']['selected_entry']=='P00001'
    b['organism_name']='Sus scrofa';_,f=policy.database(tmp_path,b)
    assert service.evaluate(b,f)['lookup']['status']=='no_exact_match'
    b.update(organism_name=None,protein_sequence='A'*19);_,f=policy.database(tmp_path,b)
    assert service.evaluate(b,f)['lookup']['status']=='no_exact_match'

def test_cached_database_rejects_mutation(tmp_path):
    b,path=package(tmp_path);policy.database(tmp_path,b)
    with path.open('ab') as f:f.write(b'damage')
    with pytest.raises(RuntimeFault,match='bytes changed'):policy.database(tmp_path,b)

def test_parent_chain_coordinates_not_double_shifted():
    raw=record().replace(b'FT   DOMAIN          2..8',b'FT   CHAIN           2..8')
    b=dict(parent=dict(sequence=SEQ,offset=2,id='P00001'),protein_sequence=SEQ[1:8])
    e,a=project(raw,b)
    assert e['features'][0]['location']==dict(start=dict(value=1,modifier='EXACT'),end=dict(value=7,modifier='EXACT'))
    assert e['coordinate_spaces'][0]=='mature'
