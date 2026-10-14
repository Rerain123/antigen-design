"""Offline native N08 execution; only registered data and fixed commands are used."""
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import time
import traceback

from compute import ANCHOR, fasta, format_fasta, require

OUT = Path('/out')
DB = Path('/database')
digest = lambda raw: hashlib.sha256(raw).hexdigest()


def write(name, value):
    with (OUT/name).open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,sort_keys=True,allow_nan=False)


def main():
    started = time.monotonic()
    body = json.loads(Path('/input.json').read_text())
    runtime = dict(machine=platform.machine(),network_interfaces=socket.if_nameindex(),
                   cpu_affinity=sorted(os.sched_getaffinity(0)),commands={},versions={},python_exit_code=None,
                   input_json_sha256=digest(Path('/input.json').read_bytes()),
                   input_fasta_sha256=digest(Path('/input.fasta').read_bytes()),
                   database_manifest_sha256=digest((DB/'manifest.json').read_bytes()))
    write('runtime_started.json',runtime)
    def invoke(name, argv, stdout_name=None):
        process = subprocess.run(argv,capture_output=True,env=dict(os.environ,TMPDIR='/tmp',LC_ALL='C'))
        (OUT/(stdout_name or name+'.txt')).write_bytes(process.stdout)
        (OUT/(name+'.stderr.txt')).write_bytes(process.stderr)
        runtime['commands'][name] = dict(argv=argv,exit_code=process.returncode,
            stdout_sha256=digest(process.stdout),stderr_sha256=digest(process.stderr))
        require(process.returncode==0, 'Native command failed: '+name)
        return process.stdout
    try:
        if (OUT/'result').is_dir(): raise RuntimeError('Controlled tool failure')
        if (OUT/'slow_worker').is_dir(): time.sleep(30)
        for name, argv in [('mmseqs',['mmseqs','version']),('mafft',['mafft','--version']),('blastp',['blastp','-version'])]:
            p = subprocess.run(argv,capture_output=True,check=True)
            runtime['versions'][name] = (p.stdout+p.stderr).decode().strip().splitlines()[0]
        manifest = json.loads((DB/'manifest.json').read_text())
        require(runtime['database_manifest_sha256']==body['database_manifest_sha256'],'Manifest changed before native execution')
        for row in manifest['files']:
            raw = (DB/row['path']).read_bytes()
            require(len(raw)==row['bytes'] and digest(raw)==row['sha256'],'Database changed before native execution')
            (OUT/('database-'+row['path'])).write_bytes(raw)
        (OUT/'database-manifest.json').write_bytes((DB/'manifest.json').read_bytes())
        seqs = fasta((DB/'sequences.fasta').read_text())
        annotations = json.loads((DB/'annotations.json').read_text())
        collected = [dict(row,sequence=seqs[row['id']]) for row in annotations
                     if row['organism_name']==body['organism_name'] and row['protein_name']==body['protein_name']]
        vaccines = [r for r in collected if r['source_label']=='vaccine']
        selected = [r for r in collected if r['source_label']=='wild']
        observation = dict(collection_mode='exact_local_organism_and_protein_annotation',
            collected_ids=[r['id'] for r in collected],vaccine_sequences=vaccines,
            excluded_source_ids=[r['id'] for r in collected if r['source_label'] not in ('wild','vaccine')],
            pre_dedup_ids=[r['id'] for r in selected],representatives=[],clusters={},
            supplementation=dict(status='not_needed' if len(selected)>=20 else 'review_required',
                reason=None if len(selected)>=20 else 'LOCAL_SUPPLEMENT_HIT_ADMISSION_UNRESOLVED',
                automatic_admission=False,source_is_ncbi_nr=False))
        if len(selected)<20:
            # Native supplemental similarity facts from the same registered local
            # package are exposed separately. No unapproved nr/network fallback or
            # unprovided scientific selection threshold is invented.
            invoke('makeblastdb',['makeblastdb','-in','/database/sequences.fasta','-dbtype','prot',
                '-parse_seqids','-out','/tmp/supplement','-blastdb_version','5'])
            invoke('supplement',['blastp','-query','/input.fasta','-db','/tmp/supplement','-num_threads','2',
                '-max_target_seqs','500','-max_hsps','10','-outfmt','6 qseqid sseqid pident qstart qend sstart send evalue bitscore'])
            observation['supplementation']['raw_hits_path']='output/supplement.txt'
            write('supplement-index.json',{p.name:digest(p.read_bytes()) for p in Path('/tmp').glob('supplement.*')})
        if not selected:
            observation['collection_status']='no_sequences'
        else:
            Path('/tmp/selected.fasta').write_text(format_fasta({r['id']:r['sequence'] for r in selected}))
            invoke('mmseqs',['mmseqs','easy-cluster','/tmp/selected.fasta','/tmp/dedup','/tmp/mmseqs-tmp',
                '--min-seq-id','0.99','--alignment-mode','3','--threads','2'])
            raw = Path('/tmp/dedup_cluster.tsv').read_bytes()
            (OUT/'clusters.tsv').write_bytes(raw)
            representatives = fasta(Path('/tmp/dedup_rep_seq.fasta').read_text())
            (OUT/'representatives.fasta').write_text(format_fasta(representatives))
            clusters = {}
            for line in raw.decode().splitlines():
                rep,member = line.split('\t')
                clusters.setdefault(rep,[]).append(member)
            observation.update(collection_status='collected',clusters=clusters,
                representatives=[r for r in selected if r['id'] in representatives])
            align_input = {ANCHOR:body['protein_sequence'],**representatives}
            (OUT/'alignment-input.fasta').write_text(format_fasta(align_input))
            invoke('mafft',['mafft','--amino','--auto','--thread','2','--inputorder','/out/alignment-input.fasta'],
                   'global.msa.fasta')
        write('observation.json',observation)
        runtime['python_exit_code']=0
    except BaseException as exc:
        runtime.update(python_exit_code=1,error=str(exc),error_type=type(exc).__name__)
        (OUT/'exception.txt').write_text(traceback.format_exc())
        raise
    finally:
        runtime['elapsed_seconds']=time.monotonic()-started
        runtime['native_output_sha256']={p.name:digest(p.read_bytes()) for p in sorted(OUT.iterdir()) if p.is_file()}
        write('runtime.json',runtime)


if __name__=='__main__': main()
