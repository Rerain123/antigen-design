"""Read registered results and summarize target provenance; never run science."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import prepare_m1_p1_deploy as common

REMOTE = r'''
import json,sqlite3,hashlib,datetime
from pathlib import Path
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
root=Path('/var/lib/t01/runtime')
jid='t01p1r-job-c4081362c5294a8bac8f1d0fe26d96a1'
def job(j):return json.loads(db.execute('SELECT data FROM jobs WHERE id=?',(j,)).fetchone()[0])
verified=[]
def artifact(a):
 path=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(a['artifact_id'],)).fetchone()[0]
 raw=(root/path).read_bytes()
 assert hashlib.sha256(raw).hexdigest()==a['sha256']
 verified.append(dict(artifact_id=a['artifact_id'],sha256=a['sha256']))
 return json.loads(raw)
def result(j):return artifact(next(a for a in job(j)['artifacts'] if a['role']=='result'))
ex=json.loads(db.execute('SELECT data FROM executions WHERE job_id=?',(jid,)).fetchone()[0])
nodes=ex['nodes'];res=result(jid);s=res['workflow']['expert_revision']
r=next(r for r in s['formal_records'] if r['disposition']=='FORMAL_POOL')
f=ex['revision_v2_frozen'];w=f.get('wt_side',{})
ep=result(nodes['epitope_map']['job_id']);bl=result(nodes['blast']['job_id'])
prior=ep['blast_similarity']['iedb_evidence']
def find_prior(x):
 if isinstance(x,dict):
  if 'e4_status' in x and 'contact_residues' in x:return x
  for v in x.values():
   found=find_prior(v)
   if found is not None:return found
 return None
bp=find_prior(bl);wp=find_prior(w)
def short(x):return {k:v for k,v in x.items() if not isinstance(v,(dict,list)) or k=='reason_codes'}
p=r['protection']
hot=ep['epitopes']['b_cell_antigenic_hotspot_map']['hotspots']
out=dict(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),job_id=jid,
 job_state=job(jid)['state'],frozen_keys=list(f),wt_side_keys=list(w),
 hotspots=hot,known_positions=len(p['target_positions']),
 iedb=dict(database_id=prior['database_id'],e3_regions=len(prior['epitope_regions']),
  e4_status=prior['e4_status'],contact_residues=prior['contact_residues'],
  structure_references=prior['structure_references'],warnings=prior['warnings']),
 transport=dict(blast_to_map_equal=bp==prior,map_to_frozen_equal=wp==prior),
 comparison=p['structure_comparison'],protection=short(p),
 checks={k:short(p[k]) for k in ('l1','l2','l3','auxiliary_geometry_status')},
 rsa_observation=short(p['l2']['observation']),
 hotspot_geometry=[dict(kind=o['kind'],check_status=o['check_status'],rmsd=o['observation'].get('value')) for o in p['l3']['objects']],
 epitope_review=short(r['l4']),final_acceptance=r['acceptance_status'],
 result_top_keys=list(res),verified_artifacts=verified,new_scientific_jobs=0)
print(json.dumps(out,ensure_ascii=False))
'''

if __name__ == '__main__':
    value=common.remote(REMOTE)
    path=Path(__file__).with_name('current-target-diagnosis.json')
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value,ensure_ascii=False,indent=2))
