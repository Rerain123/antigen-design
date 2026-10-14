"""Import a traceable N03 projection from the preserved official MySQL dump.

No SQL from the dump is executed. Names/columns are allowlisted and values are
bound parameters. Binary fields outside the N03 projection remain in the source.
"""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import time

TABLES = {
    'source': 'source_id accession database name chemical_type source_date sequence organism_id organism_name',
    'epitope': 'epitope_id description linear_peptide_seq linear_peptide_modified_seq disc_source_id disc_region mc_region mc_mol1_source_id mc_mol2_source_id',
    'epitope_object': 'epitope_id object_id source_antigen_accession',
    'curated_epitope': 'curated_epitope_id reference_id e_object_id related_object_id related_object_type e_ref_start e_ref_end e_ref_region',
    'object': 'object_id reference_id object_type object_sub_type object_description region starting_position ending_position mol1_seq mol1_modified_seq mol1_source_id mol2_source_id',
    'bcell': 'bcell_id reference_id curated_epitope_id as_char_value h_organism_id complex_id ant_object_id',
    'tcell': 'tcell_id reference_id curated_epitope_id as_char_value h_organism_id complex_id ant_object_id',
    'mhc_bind': 'mhc_bind_id reference_id curated_epitope_id as_char_value',
    'mhc_elution': 'mhc_elution_id reference_id curated_epitope_id as_char_value',
    'complex': 'complex_id reference_id pdb_id ant_pdb_chain e_pdb_chain ab_c1_pdb_chain ab_c2_pdb_chain e_residues ab_ant_residues complex_type',
    'reference': 'reference_id reference_type',
    'article': 'article_id reference_id article_title pubmed_id pmc_id',
}
SPECIAL = re.compile(br"['\\]")
ESCAPES = {ord('0'):b'\0', ord('n'):b'\n', ord('r'):b'\r', ord('t'):b'\t', ord('b'):b'\b', ord('Z'):b'\x1a'}


def rows(raw, wanted, width):
    """Strict mysqldump VALUES parser, preserving NULL versus quoted 'NULL'."""
    pos = 0
    while pos < len(raw):
        if raw[pos:pos+1] != b'(':
            raise ValueError('Expected tuple')
        pos += 1
        row = {}
        for column in range(width):
            keep = column in wanted
            if raw[pos:pos+1] == b"'":
                pos += 1; start = pos; parts = []
                while True:
                    match = SPECIAL.search(raw, pos)
                    if match is None: raise ValueError('Unterminated SQL string')
                    end = match.start()
                    if keep: parts.append(raw[start:end])
                    if raw[end] == 92:
                        if end+1 >= len(raw): raise ValueError('Truncated escape')
                        escaped = raw[end+1]
                        if keep: parts.append(ESCAPES.get(escaped, bytes([escaped])))
                        pos = start = end+2
                    elif raw[end+1:end+2] == b"'":
                        if keep: parts.append(b"'")
                        pos = start = end+2
                    else:
                        pos = end+1
                        break
                if keep: row[column] = b''.join(parts).decode('utf-8')
            else:
                end = pos
                while raw[end:end+1] not in (b',',b')',b''):
                    end += 1
                token = raw[pos:end]
                if token != b'NULL' and re.fullmatch(br'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?',token) is None:
                    raise ValueError('Unsupported SQL value')
                if keep: row[column] = None if token == b'NULL' else token.decode('ascii')
                pos = end
            delimiter = b')' if column == width-1 else b','
            if raw[pos:pos+1] != delimiter: raise ValueError('SQL tuple width differs')
            pos += 1
        yield [row[i] for i in wanted]
        if raw[pos:pos+1] == b';':
            if raw[pos+1:].strip(): raise ValueError('Trailing SQL')
            return
        if raw[pos:pos+1] != b',': raise ValueError('Expected tuple separator')
        pos += 1
    raise ValueError('Missing statement terminator')


def run(source, destination, expected_sha256):
    destination.mkdir(parents=True, exist_ok=False)
    start = time.monotonic(); counts = {}; ddl = {}; table = None
    def status(state, **fields):
        record = dict(state=state, counts=counts, elapsed_seconds=round(time.monotonic()-start,2),
                      updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), **fields)
        (destination/'status.pending').write_text(json.dumps(record,indent=2),encoding='utf-8')
        (destination/'status.pending').replace(destination/'status.json')
    try:
        status('verifying_source')
        digest=hashlib.sha256()
        with source.open('rb') as stream:
            for block in iter(lambda:stream.read(4*1024**2),b''):digest.update(block)
        if digest.hexdigest()!=expected_sha256:raise ValueError('Source hash differs')
        db=sqlite3.connect(destination/'iedb.sqlite3')
        db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA cache_size=-32768')
        mappings={};last=time.monotonic()
        with gzip.open(source,'rb') as stream:
            for line in stream:
                if line.startswith(b'CREATE TABLE `'):
                    table=line.split(b'`')[1].decode('ascii');ddl[table]=[]
                elif table and line.startswith(b'  `'):
                    ddl[table].append(line.split(b'`')[1].decode('ascii'))
                elif line.startswith(b') ENGINE') and table in TABLES:
                    names=TABLES[table].split()
                    mappings[table]=[ddl[table].index(n) for n in names]
                    db.execute('CREATE TABLE "'+table+'" ('+','.join('"'+n+'" TEXT' for n in names)+')')
                    counts[table]=0
                elif line.startswith(b'INSERT INTO `'):
                    name=line.split(b'`')[1].decode('ascii')
                    if name not in TABLES:continue
                    prefix=b'INSERT INTO `'+name.encode()+b'` VALUES '
                    if not line.startswith(prefix):raise ValueError('Unexpected INSERT syntax')
                    data=rows(line[len(prefix):],mappings[name],len(ddl[name]))
                    sql='INSERT INTO "'+name+'" VALUES ('+','.join('?' for _ in mappings[name])+')'
                    before=db.total_changes;db.executemany(sql,data);counts[name]+=db.total_changes-before
                    if time.monotonic()-last>3:
                        db.commit();status('importing',current_table=name)
                        if shutil.disk_usage(destination).free < 2*1024**3:raise RuntimeError('Storage reserve reached')
                        last=time.monotonic()
        if set(counts)!=set(TABLES) or not all(counts.values()):raise ValueError('Missing N03 table')
        db.commit();status('indexing')
        for name,names in TABLES.items():
            for col in names.split():
                if col.endswith('_id') and col not in ('pubmed_id','pmc_id','pdb_id'):
                    db.execute('CREATE INDEX "ix_'+name+'_'+col+'" ON "'+name+'" ("'+col+'")')
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity check failed')
        db.close()
        (destination/'projection.json').write_text(json.dumps(dict(source=str(source),source_sha256=expected_sha256,
            projection=TABLES,source_columns=ddl,counts=counts,original_dump_preserved=True),indent=2),encoding='utf-8')
        status('imported_verified',database_bytes=(destination/'iedb.sqlite3').stat().st_size)
    except BaseException as exc:
        status('failed',error_type=type(exc).__name__,error=str(exc));raise


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True);ap.add_argument('--destination',type=Path,required=True)
    ap.add_argument('--sha256',required=True)
    args=ap.parse_args();run(args.source,args.destination,args.sha256)
