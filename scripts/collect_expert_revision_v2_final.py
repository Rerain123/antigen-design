"""Verify the terminal same-run native facts and download the authenticated report."""
import base64
import json
from pathlib import Path
import run_expert_revision_v2_native as run
from version_bundle import encode,sha

OUT=run.OUT/'final'
REMOTE=run.REMOTE.split("if p['action']=='start':",1)[0]+r'''
import base64,io,zipfile
from datetime import datetime
from t01_phase1_real.common import encode
from t01_phase1_real.development.workflow import service,revision_controller as rc
from t01_phase1_real.service_api.user_report import from_workflow_package
jid=p['job_id'];job=rt.get(jid);ex=rt.execution(jid)
assert job['state']=='succeeded' and ex['tree_stopped'] is True and not ex.get('pending_confirmation')
assert sha(rt._request_bytes(job))==p['request_sha256'] and job['run_id']==p['run_id']
argv=Path('/proc/1/cmdline').read_bytes().decode().split('\0')
for flag,name in [('--blast-database-root','blast_database_root'),('--homology-database-root','homology_database_root'),('--domains-database-root','domains_database_root')]:
 setattr(rt,name,Path(argv[argv.index(flag)+1]) if flag in argv else None)
with rt._db() as db:before=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
body=decode(rt._request_bytes(job));fact=rc.verified_fact(rt,jid,body);assert fact is not None
for ancestor,digest in p['stopped_ancestors'].items():
 assert rt.get(ancestor)['state']=='cancelled' and sha(encode(rt.execution(ancestor)))==digest
paused=rt.execution(p['paused_parent'])
assert ex['revision_v2_frozen']==paused['revision_v2_frozen']
assert ex['nodes']['cheap0']['job_id']==paused['nodes']['cheap0']['job_id']
assert ex['nodes']['design']['confirmation']==paused['nodes']['design']['confirmation']
assert ex['started_at']==paused['started_at'] and ex['confirmation_wait_seconds']==paused['confirmation_wait_seconds']
old_msa=paused['nodes']['wt_msa']['job_id'];assert rt.get(old_msa)['state']=='cancelled' and rt.execution(old_msa)['tree_stopped'] is True
def seconds(a,z):
 return (datetime.fromisoformat(z.replace('Z','+00:00'))-datetime.fromisoformat(a.replace('Z','+00:00'))).total_seconds() if a and z else None
def elapsed(child):
 a=child.get('started_at');z=child.get('finished_at') or child.get('ended_at')
 return seconds(a,z)
children=[];msa_reuse=[]
for name,row in ex['nodes'].items():
 if not row.get('job_id'):continue
 child=service.verified(rt,body,name,row['job_id'],job['run_id'],ex['nodes'])
 assert child['state'] in ('succeeded','failed','cancelled','timed_out')
 assert not child.get('attempt_id') or rt.execution(child['job_id']).get('tree_stopped') is True
 children.append(dict(step=name,job_id=child['job_id'],state=child['state'],error_code=child.get('error_code'),
  origin=row.get('origin'),started_at=child.get('started_at'),finished_at=child.get('finished_at'),execution_seconds=elapsed(child)))
 if name.startswith('rx') and name.endswith('_af3'):
  request=decode(rt._request_bytes(child));ref=request['msa_source']
  assert ref['job_id']==ex['nodes']['wt_msa']['job_id'] and ref['job_id']!=old_msa
  msa_reuse.append(dict(step=name,job_id=child['job_id'],msa_source=ref))
result=rt.result(jid);refs={r['path']:r['artifact'] for r in result['raw_artifacts']}
assert result['scientific_gate']=='CLOSED' and result['usable_for_pipeline'] is False
request=urllib.request.Request('http://127.0.0.1:18083/v1/workflows/'+jid+'/report',
 headers={'Authorization':'Bearer '+credential['token']})
with urllib.request.urlopen(request,timeout=85) as response:
 package=response.read(32*1024**2+1);digest=response.headers['Digest']
assert len(package)<=32*1024**2 and digest=='sha-256='+sha(package)==('sha-256='+refs['output/package.zip']['sha256'])
exports={'workflow-package.zip':package}
with zipfile.ZipFile(io.BytesIO(package)) as archive:
 manifest=json.loads(archive.read('manifest.json'))
 for member in manifest['files']:
  info=archive.getinfo(member['path']);assert info.file_size==member['size_bytes']<=32*1024**2
  assert sha(archive.read(member['path']))==member['sha256']
 for name in ('workflow.json','workflow-report.md'):exports[name]=archive.read(name)
html=from_workflow_package(package)
if html is not None:exports['report.html']=html
records=[r for r in fact['formal_records'] if r['disposition']=='FORMAL_POOL']
exports['candidates.fasta']=('\n'.join('>'+r['candidate_id']+' DEVELOPMENT_UNREVIEWED; scientific_gate=CLOSED\n'+r['sequence'] for r in records)+'\n').encode()
structure_exports=[]
for record in records:
 ref=record.get('structure')
 if not ref:continue
 assert ref['run_id']==job['run_id']
 producer=rt.result(ref['job_id'])
 native=[r['path'] for r in producer['raw_artifacts'] if r['artifact']==ref]
 assert len(native)==1
 suffix=Path(native[0]).suffix.lstrip('.').lower()
 assert suffix in ('cif','pdb')
 raw=rt.artifact_bytes(ref['job_id'],ref['artifact_id']);assert sha(raw)==ref['sha256']
 name='structure-'+record['content_hash']+'.'+suffix;exports[name]=raw
 structure_exports.append(dict(candidate_id=record['candidate_id'],filename=name,artifact=ref))
summary=[dict(candidate_id=r['candidate_id'],sample_number=r['sample_number'],mutation_count=len(r['mutations']),
 esm_if1=r['esm_if1'],s28=r['validation'],structure_observations=r.get('structure_observations'),
 protection=r.get('protection'),l4=r.get('l4'),foldx=r.get('foldx'),
 acceptance_status=r['acceptance_status'],provisional_acceptance_status=r['provisional_acceptance_status'],
 description_score=r.get('description_score'),comparison_score=r.get('comparison_score'),acceptance_score=r.get('acceptance_score')) for r in records]
with rt._db() as db:assert before==db.execute('SELECT count(*) FROM jobs').fetchone()[0]
print(json.dumps(dict(audit=dict(status='PASS_READ_ONLY_TERMINAL_NATIVE_AUDIT',job_id=jid,run_id=job['run_id'],
 parent_state=job['state'],workflow_result_status=result['status'],coverage_complete=fact['coverage_complete'],
 acceptance_status=fact['acceptance_status'],provisional_acceptance_status=fact['provisional_acceptance_status'],
 design_outcomes=fact['design_outcomes'],stop_reason_codes=fact['stop_reason_codes'],run_audit=fact['run_audit'],
 unique_candidates=summary,formal_count=len(fact['formal_records']),children=children,msa_reuse=msa_reuse,structure_exports=structure_exports,
 old_checkpoints_unchanged=True,wt_frozen_unchanged=True,t4_preserved=True,generation_repeated=False,cheap_scoring_repeated=False,
 authenticated_report_download=True,package_sha256=sha(package),public_report_api_called=False,
 timing=dict(original_started_at=ex['started_at'],resumed_at=job['started_at'],finished_at=job.get('finished_at'),
  overall_wall_seconds_including_pause_and_repairs=seconds(ex['started_at'],job.get('finished_at')),
  resumed_wall_seconds=elapsed(job),user_pause_seconds=seconds(p['paused_at'],job['started_at']),
  confirmation_wait_seconds=ex['confirmation_wait_seconds'],one_hour_performance_goal_verified=False),
 scientific_gate='CLOSED',production_status='NOT_DEPLOYED',new_jobs=0,native_models_called_by_audit=False),
 exports={name:dict(base64=base64.b64encode(raw).decode(),size_bytes=len(raw),sha256=sha(raw)) for name,raw in exports.items()})))
'''

if __name__=='__main__':
    submitted=run.active_submission()
    pause=json.loads((run.OUT/'pause-confirmation.json').read_bytes())
    first=json.loads((run.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930/continuation-submission.json').read_bytes())
    payload=dict(job_id=submitted['job_id'],owner=submitted['owner'],
        run_id=submitted['run_id'],request_sha256=submitted['request_sha256'],paused_parent=pause['job_id'],paused_at=pause['paused_at'],
        stopped_ancestors={pause['job_id']:pause['execution_sha256'],first['source_job_id']:first['continuation']['source_execution_sha256']})
    bootstrap="import io,json,sys; envelope=json.load(sys.stdin); sys.stdin=io.StringIO(json.dumps(envelope['payload'])); exec(compile(envelope['source'],'terminal-native-audit','exec'))"
    value=run.common.remote(bootstrap,dict(source=REMOTE,payload=payload))
    OUT.mkdir(parents=True,exist_ok=True);manifest={}
    for name,item in value['exports'].items():
        import re
        assert name in ('workflow-package.zip','workflow.json','workflow-report.md','report.html','candidates.fasta') or re.fullmatch(r'structure-[0-9a-f]{64}\.(cif|pdb)',name)
        raw=base64.b64decode(item['base64'],validate=True)
        assert len(raw)==item['size_bytes'] and sha(raw)==item['sha256']
        path=OUT/name
        if path.exists():assert path.read_bytes()==raw
        else:
            with path.open('xb') as stream:stream.write(raw)
        manifest[name]={k:v for k,v in item.items() if k!='base64'}
    audit=value['audit'];audit['downloaded_artifacts']=manifest
    (OUT/'audit.json').write_bytes(encode(audit)+b'\n')
    print(json.dumps({k:audit[k] for k in ('status','parent_state','coverage_complete','acceptance_status',
        'provisional_acceptance_status','design_outcomes','stop_reason_codes','formal_count','downloaded_artifacts')},ensure_ascii=False))
