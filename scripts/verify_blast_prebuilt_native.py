"""Build a bounded offline multi-volume fixture and exercise real N03 execution."""
import json
import random
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import encode,decode,sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.blast import policy


def main():
    out=ROOT/'discovery/t01-phase1-real/m1-p4-20260922/prebuilt-native-r02'
    out.mkdir(parents=True,exist_ok=False)
    folder=out/'databases/engineering-multivol';folder.mkdir(parents=True)
    rng=random.Random(20260922);seqs=[''.join(rng.choices('ACDEFGHIKLMNPQRSTVWY',k=300)) for _ in range(240)]
    fasta=''.join(f'>fixture_{i}\n{s}\n' for i,s in enumerate(seqs)).encode();(out/'source.fasta').write_bytes(fasta)
    cmd=['docker','run','--rm','--network','none','--mount',f'type=bind,source={out},target=/work',policy.IMAGE,
        'makeblastdb','-in','/work/source.fasta','-dbtype','prot','-parse_seqids','-title','engineering-multivol',
        '-out','/work/databases/engineering-multivol/part','-blastdb_version','5','-max_file_sz','20KB']
    p=subprocess.run(cmd,capture_output=True);(out/'build.stdout').write_bytes(p.stdout);(out/'build.stderr').write_bytes(p.stderr);p.check_returncode()
    meta_path=folder/'part.pjs';meta=decode(meta_path.read_bytes())
    volumes=sorted(p.stem for p in folder.glob('*.psq'));assert len(volumes)>=2
    m=dict(schema_version='0.2.0',database_id=folder.name,qualification='ENGINEERING_FIXTURE',
        purpose='N03 native offline prebuilt multi-volume engineering test',created_at='2026-09-22',
        source=dict(name='generated random engineering sequences',version='20260922-seed',release_date=meta['last-updated'].split('T')[0],
            license='project engineering fixture',reference='local-engineering-fixture'),
        blast=dict(db_prefix='part',dbtype='prot',blastdb_version=5,title='engineering-multivol',sequence_count=len(seqs),
            makeblastdb_version='makeblastdb: 2.17.0+',builder_identity=policy.IMAGE),
        prebuilt=dict(metadata_path=meta_path.name,alias_path='part.pal',volume_prefixes=volumes,integrity='LOCAL_SHA256_NO_UPSTREAM_CHECKSUM'),files=[])
    for path in sorted(folder.iterdir()):
        raw=path.read_bytes();m['files'].append(dict(path=path.name,role='metadata' if path==meta_path else 'alias' if path.suffix=='.pal' else 'index',bytes=len(raw),sha256=sha(raw)))
    (folder/'manifest.json').write_bytes(encode(m))
    body=dict(protein_sequence=seqs[0],user_sequence_id='engineering-multivol-native',database_id=folder.name,
        database_manifest_sha256=sha(encode(m)),thresholds=dict(identity_percent_min=70,query_coverage_percent_min=80),timeout_seconds=120)
    start=time.perf_counter();receipt=policy.verify_database(folder.parent,body);elapsed=time.perf_counter()-start
    rt=Runtime(ROOT/'var/t01-phase1-real/m1-p4-prebuilt-native',blast_database_root=folder.parent)
    job=rt.submit_sequence(encode(body),'m1-p4-prebuilt-native',policy.TOOL);rt.dispatch(job['job_id']);job=rt.wait(job['job_id'])
    result=rt.result(job['job_id'])
    for name,value in [('job',job),('result',result),('request',body),('database-receipt',receipt)]:
        (out/(name+'.json')).write_bytes(encode(value))
    assert job['state']=='succeeded',result['execution']
    total=sum(e['bytes'] for e in m['files'])
    (out/'verification.json').write_bytes(encode(dict(status='ENGINEERING_NATIVE_MULTIVOLUME_PASS',volumes=len(volumes),
        build_argv=cmd,input_sha256=sha(fasta),full_hash_bytes=total,full_hash_elapsed_seconds=elapsed,
        integrity_policy='FULL_SHA256_EVERY_VERIFICATION_NO_CACHE',
        nr_cost=dict(bytes=613736552406,seconds_at_100_MiB_per_second=613736552406/(100*1024**2),
            seconds_at_500_MiB_per_second=613736552406/(500*1024**2),
            measured_nr_throughput=None,acceptance='TARGET_MOUNT_THROUGHPUT_AND_DEADLINE_REMAIN_UNVERIFIED'),
        target_nr_accepted=False,scientific_release_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
    print('ENGINEERING_NATIVE_MULTIVOLUME_PASS',len(volumes))


if __name__=='__main__':main()
