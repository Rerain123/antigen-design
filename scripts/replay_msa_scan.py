"""Replay archived AF3 MSA and N17 sources through deployed code, read-only."""
import json
import prepare_m1_p1_deploy as common
from version_bundle import encode
import replay_remaining_tools
import verify_n17_continuation

OUT=common.ROOT/'reports/msa-scan-20260928'
REMOTE=r'''
import json,sqlite3
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.af3.msa import sources,folding
from t01_phase1_real.common import decode,RuntimeFault,sha
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
count=db.execute('select count(*) from jobs').fetchone()[0];records=[]
for scope,raw in db.execute('select scope,data from jobs'):
    job=json.loads(raw)
    if job['tool_id']!='t01.real.af3' or job['state']!='succeeded':continue
    rt=Runtime('/var/lib/t01/runtime',scope=scope)
    try:
        body=decode(rt._request_bytes(job));source=dict(job_id=job['job_id'],artifact=next(a for a in job['artifacts'] if a['role']=='result'))
        with rt._db() as source_db:files,receipt=sources(rt,source_db,dict(body,msa_source=source),job['run_id'])
        p=decode(files['msa-source.json']);sequence=body['protein_sequence']
        variant=('C' if sequence[0]=='A' else 'A')+sequence[1:]
        projected=folding(variant,1,p)['sequences'][0]['protein']
        assert projected['sequence']==variant
        records.append(dict(job_id=job['job_id'],status='PASS',length=len(sequence),source=receipt,
            alignment_rows={k:sum(l.startswith('>') for l in v.splitlines()) for k,v in p['msas'].items()},
            projected_input_sha256=sha(json.dumps(projected,sort_keys=True).encode()),prediction_submitted=False))
    except (RuntimeFault,ValueError,KeyError,TypeError) as exc:
        records.append(dict(job_id=job['job_id'],status='BLOCKED',reason=str(exc),code=getattr(exc,'code',type(exc).__name__)))
assert db.execute('select count(*) from jobs').fetchone()[0]==count
print(json.dumps(dict(mode='READ_ONLY_ARCHIVED_NATIVE_MSA_REUSE_PROJECTION',records=records,job_count=count,
    new_jobs=0,model_invocations=0)))
'''

if __name__=='__main__':
    value=common.remote(REMOTE);(OUT/'af3-native-msa-replay.json').write_bytes(encode(value))
    print(json.dumps(dict(af3=[{k:r[k] for k in ('job_id','status')} for r in value['records']],new_jobs=0)))
    if not any(r['status']=='PASS' for r in value['records']):raise RuntimeError('No compatible archived WT MSA source')
    n17=common.remote(replay_remaining_tools.REMOTE);(OUT/'n17-native-replay.json').write_bytes(encode(n17))
    if len(n17['records'])<5 or any(r['status']!='PASS' for r in n17['records']):raise RuntimeError('Archived N17 replay differs')
    verify_n17_continuation.OUT=OUT;verify_n17_continuation.main()
