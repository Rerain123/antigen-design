import importlib.util
import json
from pathlib import Path
import sqlite3

spec=importlib.util.spec_from_file_location('iedb_projection',Path(__file__).parents[1]/'scripts/build_iedb_projection.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_verified_projection_excludes_negative_only_and_preserves_source(tmp_path):
    source=tmp_path/'source';source.mkdir()
    (source/'status.json').write_text('{"state":"imported_verified"}')
    db=sqlite3.connect(source/'iedb.sqlite3')
    db.executescript('''
CREATE TABLE source(source_id TEXT,accession TEXT,"database" TEXT,name TEXT,sequence TEXT,organism_name TEXT);
INSERT INTO source VALUES ('7','P123','UniProt','protein','ACDEFGHIKLMNPQRSTVWY','organism');
INSERT INTO source SELECT * FROM source;
CREATE TABLE curated_epitope(curated_epitope_id TEXT,reference_id TEXT,e_object_id TEXT);
INSERT INTO curated_epitope VALUES ('1','5','2'),('3','5','4');
CREATE TABLE object(object_id TEXT,mol1_source_id TEXT,mol2_source_id TEXT,starting_position TEXT,ending_position TEXT,mol1_seq TEXT,mol1_modified_seq TEXT,object_sub_type TEXT);
INSERT INTO object VALUES ('2',NULL,'7','3','7','DEFGH',NULL,'Peptide from protein'),('4',NULL,'7','8','10','IKL',NULL,'Peptide from protein');
CREATE TABLE epitope_object(object_id TEXT,epitope_id TEXT);
INSERT INTO epitope_object VALUES ('2','99'),('4','98');
CREATE TABLE article(reference_id TEXT,pubmed_id TEXT);
INSERT INTO article VALUES ('5','123');
CREATE TABLE bcell(curated_epitope_id TEXT,as_char_value TEXT,complex_id TEXT);
INSERT INTO bcell VALUES ('1','Positive',NULL),('3','Negative',NULL);
CREATE TABLE tcell(curated_epitope_id TEXT,as_char_value TEXT);
INSERT INTO tcell VALUES ('1','Positive-High');
CREATE TABLE mhc_bind(curated_epitope_id TEXT,as_char_value TEXT);
CREATE TABLE mhc_elution(curated_epitope_id TEXT,as_char_value TEXT);
CREATE TABLE complex(complex_id TEXT,pdb_id TEXT,ant_pdb_chain TEXT,e_pdb_chain TEXT,ab_c1_pdb_chain TEXT,ab_c2_pdb_chain TEXT,reference_id TEXT);
''');db.commit();db.close()
    module.run(source,tmp_path/'out')
    out=sqlite3.connect(tmp_path/'out/evidence.sqlite3')
    assert out.execute('SELECT epitope_id,start,end,epitope_type,mapping_status FROM regions').fetchall()==[
        ('99',3,7,'mixed','VALIDATED_SOURCE_INTERVAL')]
    assert (tmp_path/'out/proteins.fasta').read_text()=='>iedb_7\nACDEFGHIKLMNPQRSTVWY\n'
    assert json.loads((tmp_path/'out/status.json').read_text())['state']=='projection_verified'


def test_wrong_or_modified_interval_is_not_invented():
    row=dict(starting_position='3',ending_position='5',mol1_seq='DEF',mol1_modified_seq=None)
    assert module.source_interval(row,'ACDEFGH')[2]=='VALIDATED_SOURCE_INTERVAL'
    assert module.source_interval(dict(row,mol1_seq='YYY'),'ACDEFGH')[2]=='IEDB_SOURCE_INTERVAL_MISMATCH'
    assert module.source_interval(dict(row,mol1_modified_seq='D*EF'),'ACDEFGH')[2]=='IEDB_MODIFIED_EPITOPE_REQUIRES_REVIEW'
