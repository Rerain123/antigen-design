"""Build a versioned C20 source-protein and evidence projection, offline."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import time


def source_interval(row, sequence):
    try:
        begin=int(row['starting_position']);end=int(row['ending_position'])
        valid=1<=begin<=end<=len(sequence) and sequence[begin-1:end]==row['mol1_seq']
        state='VALIDATED_SOURCE_INTERVAL' if valid else 'IEDB_SOURCE_INTERVAL_MISMATCH'
        if row['mol1_modified_seq']:state='IEDB_MODIFIED_EPITOPE_REQUIRES_REVIEW'
        return begin,end,state
    except (TypeError,ValueError):return None,None,'IEDB_SOURCE_INTERVAL_MISSING'


def run(source, destination):
    destination.mkdir(parents=True,exist_ok=False)
    start=time.monotonic();counts=Counter();rejects=Counter()
    def status(state,**kw):
        temp=destination/'status.pending'
        temp.write_text(json.dumps(dict(state=state,counts=counts,rejections=rejects,
            seconds=round(time.monotonic()-start,2),**kw),indent=2),encoding='utf-8')
        temp.replace(destination/'status.json')
    try:
        if json.loads((source/'status.json').read_bytes())['state']!='imported_verified':
            raise ValueError('Import not complete')
        db=sqlite3.connect((source/'iedb.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
        db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA cache_size=-32768')
        out=sqlite3.connect(destination/'evidence.sqlite3')
        out.executescript('''
CREATE TABLE proteins(subject_id TEXT PRIMARY KEY,source_id TEXT,accession TEXT,source_database TEXT,name TEXT,sequence TEXT,organism_name TEXT);
CREATE TABLE regions(subject_id TEXT,epitope_id TEXT,curated_epitope_id TEXT,reference_id TEXT,pubmed_id TEXT,start INTEGER,end INTEGER,epitope_type TEXT,mapping_status TEXT);
CREATE TABLE structures(subject_id TEXT,complex_id TEXT,pdb_id TEXT,ant_pdb_chain TEXT,e_pdb_chain TEXT,ab_c1_pdb_chain TEXT,ab_c2_pdb_chain TEXT,reference_id TEXT);
''')
        status('building_assay_types')
        db.execute('CREATE TEMP TABLE types(curated_epitope_id TEXT PRIMARY KEY,b INTEGER DEFAULT 0,t INTEGER DEFAULT 0)')
        for table,col in (('bcell','b'),('tcell','t'),('mhc_bind','t'),('mhc_elution','t')):
            db.execute('INSERT INTO types(curated_epitope_id,'+col+') SELECT DISTINCT curated_epitope_id,1 FROM "'+table+
                '" WHERE lower(as_char_value) LIKE \'positive%\' ON CONFLICT(curated_epitope_id) DO UPDATE SET '+col+'=1')
        db.commit();status('building_evidence')
        query='''SELECT c.curated_epitope_id,c.reference_id,o.object_id,o.mol1_source_id,o.mol2_source_id,
 o.starting_position,o.ending_position,o.mol1_seq,o.mol1_modified_seq,o.object_sub_type,
 e.epitope_id,t.b,t.t,a.pubmed_id
 FROM curated_epitope c JOIN "object" o ON o.object_id=c.e_object_id
 JOIN epitope_object e ON e.object_id=o.object_id
 JOIN types t ON t.curated_epitope_id=c.curated_epitope_id
 LEFT JOIN article a ON a.reference_id=c.reference_id'''
        cached={};source_cursor=db.cursor();last=time.monotonic()
        with (destination/'proteins.fasta').open('x',encoding='ascii') as fasta:
            for row in db.execute(query):
                sid=row['mol2_source_id'] or row['mol1_source_id']
                if not sid:rejects['SOURCE_ID_MISSING']+=1;continue
                if row['mol1_source_id'] and row['mol2_source_id'] and row['mol1_source_id']!=row['mol2_source_id']:
                    rejects['MULTICOMPONENT_SOURCE_AMBIGUOUS']+=1;continue
                if sid not in cached:
                    # The official dump repeats identical source rows across
                    # curated records. Collapse exact duplicates, but never
                    # choose arbitrarily between conflicting source versions.
                    sources=source_cursor.execute('SELECT DISTINCT * FROM source WHERE source_id=?',(sid,)).fetchall()
                    protein=None
                    if len(sources)==1:
                        s=sources[0];seq=s['sequence']
                        if seq and re.fullmatch('[ACDEFGHIKLMNPQRSTVWYBXZJUO]+',seq) and len(seq)>=9:
                            protein=dict(s);subject='iedb_'+sid
                            out.execute('INSERT INTO proteins VALUES (?,?,?,?,?,?,?)',
                                (subject,sid,s['accession'],s['database'],s['name'],seq,s['organism_name']))
                            fasta.write('>'+subject+'\n'+seq+'\n');counts['proteins']+=1
                    cached[sid]=protein
                protein=cached[sid]
                if protein is None:rejects['FULL_SOURCE_SEQUENCE_UNAVAILABLE']+=1;continue
                subject='iedb_'+sid;begin,end,state=source_interval(row,protein['sequence'])
                kind='mixed' if row['b'] and row['t'] else 'B' if row['b'] else 'T' if row['t'] else 'unknown'
                out.execute('INSERT INTO regions VALUES (?,?,?,?,?,?,?,?,?)',
                    (subject,row['epitope_id'],row['curated_epitope_id'],row['reference_id'],row['pubmed_id'],begin,end,kind,state))
                counts['regions']+=1;counts[state]+=1
                if time.monotonic()-last>5:out.commit();status('building_evidence');last=time.monotonic()
        out.commit();status('building_structures')
        out.execute('CREATE INDEX regions_subject ON regions(subject_id)')
        out.execute('CREATE INDEX regions_curated ON regions(curated_epitope_id)')
        for row in db.execute('''SELECT DISTINCT b.curated_epitope_id,c.* FROM bcell b JOIN "complex" c ON c.complex_id=b.complex_id WHERE c.pdb_id IS NOT NULL AND lower(b.as_char_value) LIKE 'positive%' '''):
            subjects=out.execute('SELECT DISTINCT subject_id FROM regions WHERE curated_epitope_id=?',(row['curated_epitope_id'],)).fetchall()
            for (subject,) in subjects:
                out.execute('INSERT INTO structures VALUES (?,?,?,?,?,?,?,?)',(subject,)+tuple(row[n] for n in
                    ('complex_id','pdb_id','ant_pdb_chain','e_pdb_chain','ab_c1_pdb_chain','ab_c2_pdb_chain','reference_id')))
                counts['structure_references']+=1
        out.execute('CREATE INDEX structures_subject ON structures(subject_id)');out.commit()
        if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Evidence database integrity failed')
        if not counts['proteins'] or not counts['VALIDATED_SOURCE_INTERVAL']:raise ValueError('No usable C20 source records')
        out.close();db.close()
        status('projection_verified',e4_coordinates_available=False,source_projection=str(source/'projection.json'))
    except BaseException as exc:status('failed',error=str(exc));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--destination',type=Path,required=True);a=p.parse_args();run(a.source,a.destination)
