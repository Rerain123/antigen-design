"""Build and register the downloaded offline IEDB projection with pinned BLAST."""
import base64
import json
from pathlib import Path
import subprocess
import prepare_m1_p1_deploy as c

DEST='/var/lib/t01/m1-p1-test-data/blast/iedb-20260924-r01'
EVIDENCE=c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922'


def main():
    staged=c.remote('''import json,shutil,sys
from pathlib import Path
p=Path('/var/lib/t01/runtime/datasets/iedb/20260924-r01/n03-projection-r02')
d=Path(json.load(sys.stdin)['destination'])
status=json.loads((p/'status.json').read_bytes());assert status['state']=='projection_verified'
assert shutil.disk_usage(p).free>3*1024**3
d.mkdir(exist_ok=False)
for name in ('proteins.fasta','evidence.sqlite3'):shutil.copyfile(p/name,d/name)
(d/'projection.json').write_bytes((p/'status.json').read_bytes())
print(json.dumps(status))
''',dict(destination=DEST))
    code='''import subprocess,os,json,time
from pathlib import Path
d=Path('/var/lib/t01/m1-p1-test-data/blast/iedb-20260924-r01')
e=dict(os.environ);e.pop('PYTHONHOME',None);e.pop('PYTHONPATH',None)
argv=['/blast/bin/makeblastdb','-in',str(d/'proteins.fasta'),'-dbtype','prot','-parse_seqids','-title','IEDB local source proteins 20260924','-out',str(d/'iedb'),'-blastdb_version','5']
start=time.monotonic();p=subprocess.run(argv,capture_output=True,env=e,timeout=600)
print(json.dumps(dict(argv=argv,exit_code=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode(),elapsed_seconds=time.monotonic()-start)))
'''
    result=subprocess.run(c.K+['exec','deployment/antigen-design','-c','worker-blast','--',
        '/opt/t01/supervisor/bin/python3.11','-B','-c',code],capture_output=True,timeout=700)
    result.check_returncode();build=json.loads(result.stdout)
    (EVIDENCE/'iedb-index-build-r01.json').write_text(json.dumps(build,indent=2),encoding='utf-8')
    assert build['exit_code']==0,build
    manifest=c.remote('''import json,hashlib,sys,datetime
from pathlib import Path
d=Path(json.load(sys.stdin)['destination'])
status=json.loads((d/'projection.json').read_bytes())
meta=json.loads((d/'iedb.pjs').read_bytes())
assert meta['number-of-sequences']==status['counts']['proteins']
files=[]
for p in sorted(d.iterdir()):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while b:=f.read(8*1024**2):h.update(b)
 role={'proteins.fasta':'source_fasta','evidence.sqlite3':'iedb_metadata','projection.json':'provenance'}.get(p.name,'index')
 files.append(dict(path=p.name,role=role,bytes=p.stat().st_size,sha256=h.hexdigest()))
m=dict(schema_version='0.3.0',database_id=d.name,qualification='TARGET_DATABASE_UNREVIEWED',purpose='C20 N03 offline IEDB literature prior; positive assays with full source sequences',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 source=dict(name='IEDB public SQL export',version='download-20260924',release_date='upstream release not independently verified; downloaded 2026-09-24',license='CC BY 4.0; official IEDB export terms',reference='https://www.iedb.org/database_export_v3.php'),
 blast=dict(db_prefix='iedb',dbtype='prot',blastdb_version=5,title='IEDB local source proteins 20260924',sequence_count=status['counts']['proteins'],makeblastdb_version='makeblastdb: 2.17.0+',builder_identity='sha256:47f7b258c072f1f931ca485e03e76f721dd4a621bf1bd24ece9c1c3d1107057a'),
 iedb=dict(metadata_path='evidence.sqlite3',source_sql_sha256='f788be3a2dcdc568bb40c572ae5a031762b5eb42b5ace8b1a6ebf3311cc1ddcb',source_snapshot='iedb-public-sql-download-20260924',mapping_version='iedb-n03-v1'),files=files)
raw=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
with (d/'manifest.json').open('xb') as f:f.write(raw)
print(json.dumps(dict(manifest=m,manifest_sha256=hashlib.sha256(raw).hexdigest(),bytes=sum(f['bytes'] for f in files),metadata=meta)))
''',dict(destination=DEST))
    (EVIDENCE/'iedb-database-manifest-r01.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(dict(manifest_sha256=manifest['manifest_sha256'],bytes=manifest['bytes'],proteins=staged['counts']['proteins'],build_seconds=build['elapsed_seconds'])))


if __name__=='__main__':main()
