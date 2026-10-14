"""Register a new additive offline database, preserving every parent byte."""
import base64
import json
import sys
from pathlib import Path
import prepare_m1_p1_deploy as common
from build_6l62_supplement import OUT,NEW_ID,sha,encode

REMOTE=r'''
import json,sys,base64,hashlib,shutil,datetime,sqlite3
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development.blast.policy import verify_database
from t01_phase1_real.development.blast.iedb import read_evidence,map_evidence
p=json.load(sys.stdin);root=Path('/var/lib/t01/m1-p1-test-data/blast')
parent=root/'iedb-20260924-r01';dest=root/p['database_id']
assert dest.parent==root and dest.name=='iedb-20261013-6l62-r01'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  while block:=f.read(8*1024**2):h.update(block)
 return h.hexdigest()
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def state():
 return {t:sha(json.dumps(db.execute('SELECT data FROM '+t+' ORDER BY data').fetchall(),separators=(',',':')).encode()) for t in ('jobs','executions')}
before=state()
oldraw=(parent/'manifest.json').read_bytes();assert sha(oldraw)==p['parent_sha256']
old=json.loads(oldraw)
verify_database(str(root),dict(database_id=parent.name,database_manifest_sha256=p['parent_sha256']))
assert not dest.exists(),'New database directory already exists; verify it without overwriting'
assert shutil.disk_usage(root).free>sum(x['bytes'] for x in old['files'])+256*1024**2
meta=sqlite3.connect('file:'+str(parent/old['iedb']['metadata_path'])+'?mode=ro',uri=True);meta.row_factory=sqlite3.Row
records={t:[dict(r) for r in meta.execute('SELECT * FROM '+t+' WHERE subject_id=?',('iedb_410863',))] for t in ('proteins','regions','structures')}
assert records==p['source_records'],'Source metadata changed'
dest.mkdir()
for entry in old['files']:
 target=dest/entry['path'];target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(parent/entry['path'],target)
 assert target.stat().st_nlink==1
m=json.loads(oldraw);m['database_id']=dest.name;m['created_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
m['purpose']+='; 6L62 biological assembly 1 antibody contacts, immutable additive supplement'
m['source']['name']='IEDB public SQL export + wwPDB 6L62'
m['source']['version']='IEDB download-20260924 + 6L62 v1.3 offline import 20261013'
m['source']['license']+='; wwPDB coordinates CC0 1.0'
m['iedb']['complex_coordinates']=[p['coordinate_entry']]
for entry in p['files']:
 rel=Path(entry['path']);assert not rel.is_absolute() and '..' not in rel.parts
 target=dest/rel;assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True)
 raw=base64.b64decode(entry['base64'],validate=True);assert sha(raw)==entry['sha256'] and len(raw)==entry['bytes']
 with target.open('xb') as f:f.write(raw)
 m['files'].append({k:entry[k] for k in ('path','role','bytes','sha256')})
m['files'].sort(key=lambda x:x['path'])
raw=json.dumps(m,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
with (dest/'manifest.json').open('xb') as f:f.write(raw)
receipt=verify_database(str(root),dict(database_id=dest.name,database_manifest_sha256=sha(raw)))
# Reuse the recorded HSP facts solely for an isolated data-package verification.
def job(jid):return json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(jid,)).fetchone()[0])
def artifact(a):
 path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(a['artifact_id'],)).fetchone()[0]
 raw=(Path('/var/lib/t01/runtime')/path).read_bytes();assert sha(raw)==a['sha256'];return json.loads(raw)
j=job('t01p1r-job-8c3fd33de0664c82908ae546c6a564ef')
res=artifact(next(a for a in j['artifacts'] if a['role']=='result'));req=artifact(j['request_artifact'])
hsps=res['search']['raw_hsps'];subjects={h['subject_id'] for h in hsps if h['passes_registered_thresholds']}
evidence=read_evidence(dest,subjects,m)
mapped=map_evidence(req['protein_sequence'],hsps,evidence)
assert mapped['e4_status']=='computed' and len(mapped['contact_residues'])==23
assert mapped['epitope_regions']==res['iedb_prior']['epitope_regions']
assert not any('CONTACT' in w['code'] or 'COMPLEX' in w['code'] for w in mapped['warnings'])
assert (parent/'manifest.json').read_bytes()==oldraw
unchanged=all(file_sha(parent/e['path'])==e['sha256'] for e in old['files'])
assert unchanged and before==state()
print(json.dumps(dict(status='REGISTERED_AND_VERIFIED',database_id=dest.name,manifest_sha256=sha(raw),manifest=m,
 parent_database_unchanged=unchanged,scientific_state_unchanged=True,new_scientific_jobs=0,
 current_himat_default_changed=False,verification_scope='Offline coordinate/HSP replay only; no historical report or target mutation',
 data_replay=dict(e4_status=mapped['e4_status'],contacts=mapped['contact_residues'],e3_unchanged=True,e3_regions=len(mapped['epitope_regions'])),
 verification_file_count=len(receipt['files'])),ensure_ascii=False))
'''

if __name__=='__main__':
    entry=json.loads((OUT/'coordinate-entry.json').read_bytes())
    files=[]
    for f in sorted((OUT/'supplement').rglob('*')):
        if not f.is_file():continue
        raw=f.read_bytes();name=f.relative_to(OUT/'supplement').as_posix()
        files.append(dict(path=name,role='complex_coordinates' if name==entry['path'] else 'provenance',bytes=len(raw),sha256=sha(raw),base64=base64.b64encode(raw).decode()))
    value=common.remote(REMOTE,dict(database_id=NEW_ID,parent_sha256='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12',
        source_records=json.loads((OUT/'source/iedb-source-records.json').read_bytes()),coordinate_entry=entry,files=files))
    (OUT/'registration.json').write_bytes(encode(value))
    (OUT/'manifest.json').write_bytes(json.dumps(value['manifest'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
    print(json.dumps({k:v for k,v in value.items() if k not in ('manifest','data_replay')},ensure_ascii=False,indent=2))
