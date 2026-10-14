"""Read-only size/hash and independent DNA validation of an N16 sealed batch."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from Bio.Data import CodonTable

def audit(root):
    index=json.loads((root/'index.json').read_bytes());verified=0;published=0;optimized=0;fallback=0
    for row in index['files']:
        path=(root/row['path']).resolve();assert path.is_relative_to(root.resolve())
        raw=path.read_bytes();assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'];verified+=1
    assert set(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())==set(r['path'] for r in index['files'])|{'index.json'}
    code=CodonTable.unambiguous_dna_by_id[1].forward_table
    def check(dna,protein):
        assert len(dna)==3*len(protein) and ''.join(code[dna[i:i+3]] for i in range(0,len(dna),3))==protein
        assert 40*len(dna)<=100*sum(c in 'GC' for c in dna)<=60*len(dna)
        assert not any(site in dna for site in ('GGTCTC','GAGACC','GAAGAC','GTCTTC'))
    for case in index['cases']:
        files={}
        for row in case['artifacts']:
            raw=(root/row['path']).read_bytes();ref=row['artifact']
            assert len(raw)==ref['size_bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'];published+=1
            files[ref['artifact_id']]=raw
        request=json.loads((root/'cases'/case['name']/'request.json').read_bytes())
        rp=root/'cases'/case['name']/'result.json'
        if not rp.exists():assert case['state']=='cancelled';continue
        v=json.loads(rp.read_bytes());job=json.loads((rp.parent/'job.json').read_bytes())
        ref=next(r for r in job['artifacts'] if r['role'] in ('result','diagnostic'))
        assert json.loads(files[ref['artifact_id']])==v
        assert not v['usable_for_pipeline'] and not v['automatic_handoff'] and v['production_status']=='NOT_DEPLOYED'
        assert v['binding']['job_id']==case['job_id'] and v['binding']['input_sha256']==hashlib.sha256((rp.parent/'request.json').read_bytes()).hexdigest()
        d=v['dna']
        if d is None:continue
        raw_by_path={r['path']:files[r['artifact']['artifact_id']] for r in v['raw_artifacts']}
        usage={}
        for r in csv.DictReader(io.StringIO(raw_by_path['input/codon-table.csv'].decode())):
            usage.setdefault(r['amino_acid'],{})[r['codon'].replace('U','T')]=float(r['relative_frequency'])
        expected=''.join(min(usage[a],key=lambda c:(-usage[a][c],c)) for a in request['protein_sequence'])
        assert expected==d['initial_dna'] and d['cai_score'] is None and d['scientific_pass'] is None
        obs=json.loads(raw_by_path['output/observation.json'])
        assert obs['input_hashes']=={k.removeprefix('input/'):hashlib.sha256(raw).hexdigest() for k,raw in raw_by_path.items() if k.startswith('input/')}
        if d['optimized_dna'] is not None:
            check(d['optimized_dna'],request['protein_sequence']);optimized+=1
        else:
            assert d['status']=='OPTIMIZATION_INCOMPLETE' and d['returned_dna']==expected and d['optimizer_failure']['code']=='NO_SOLUTION'
            assert ''.join(code[expected[i:i+3]] for i in range(0,len(expected),3))==request['protein_sequence'];fallback+=1
    assert all(g['passed'] for g in index['guards']) and index['original_24_processed'] is False
    return dict(passed=True,verified_files=verified,published_artifacts=published,cases=len(index['cases']),guards=len(index['guards']),
        independently_verified_optimized=optimized,real_no_solution_fallback=fallback,index_sha256=hashlib.sha256((root/'index.json').read_bytes()).hexdigest())

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('archive',type=Path);args=ap.parse_args()
    print(json.dumps(audit(args.archive),ensure_ascii=False,indent=2))
