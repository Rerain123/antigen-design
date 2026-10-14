"""One-time edit adding evidence-preserving continuation to the acceptance CLI."""
from pathlib import Path
p=Path('scripts/run_bepipred_acceptance.py')
s=p.read_text(encoding='utf-8')
s=s.replace('from run_deeptmhmm_acceptance import write, until','''from run_deeptmhmm_acceptance import write as original_write, until


def write(path,value):
    raw=value if isinstance(value,bytes) else encode(value)
    if path.exists():
        assert path.read_bytes()==raw,'Cannot rewrite existing evidence: '+str(path)
        return
    original_write(path,raw)''')
s=s.replace("p.add_argument('--root',required=True);p.add_argument('--batch',required=True)","p.add_argument('--root',required=True);p.add_argument('--batch',required=True)\n    p.add_argument('--resume-tail',action='store_true',help='Resume interrupted acceptance after the recorded crash-after-start case')")
s=s.replace("assert root.is_absolute() and not root.exists(),'Use a fresh absolute runtime root'","assert root.is_absolute() and (a.resume_tail or not root.exists()),'Use a fresh absolute runtime root'")
s=s.replace("assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and not batch.exists(),'Use a fresh W2 batch'","assert batch.is_relative_to(REPO/'discovery/t01-phase1-real/w2') and (a.resume_tail or not batch.exists()),'Use a fresh W2 batch'\n    assert not (batch/'index.json').exists(),'Completed evidence is immutable'")
s=s.replace('batch.mkdir(parents=True);rt=Runtime(root);profile=registered_profile();entries=[]','batch.mkdir(parents=True,exist_ok=a.resume_tail);rt=Runtime(root);profile=registered_profile();entries=[]')
s=s.replace("write(batch/'source'/path.relative_to(REPO),path.read_bytes())","write(batch/('resume-source' if a.resume_tail else 'source')/path.relative_to(REPO),path.read_bytes())")
s=s.replace('        run=subprocess.run(argv,capture_output=True,timeout=220,creationflags=subprocess.CREATE_NO_WINDOW)',"""        saved=batch/'cli'/(name+'.json')
        if a.resume_tail and saved.exists():
            record=decode(saved.read_bytes());assert record['argv']==argv and record['exit_code']==expected
            return decode(record['stdout'])
        run=subprocess.run(argv,capture_output=True,timeout=220,creationflags=subprocess.CREATE_NO_WINDOW)""")
start=s.index("    first_args=['bepipred'");end=s.index("    retried=cli('explicit-retry'",start)
block=s[start:end]
replacement='    if not a.resume_tail:\n'+''.join('    '+line if line.strip() else line for line in block.splitlines(True))
replacement+='''    else:
        assert decode((batch/'profile.json').read_bytes())==profile
        for folder in sorted((batch/'cases').iterdir()):
            job=decode((folder/'job.json').read_bytes());seq=decode(rt._request_bytes(job))['protein_sequence']
            kind='UPSTREAM_PACKAGE_ASSOCIATED_SAMPLE' if folder.name=='native-example' else 'CONTROLLED_ENGINEERING_INPUT' if folder.name in ('short9','local-upper1022') else 'CONTROLLED_LIFECYCLE_VALIDATION'
            finish(folder.name,job,job['state'],job['error_code'],seq,kind)
        assert decode(decode((batch/'cli/same-key-conflict.json').read_bytes())['stdout'])['error']['code']=='IDEMPOTENCY_CONFLICT'
        assert all(decode(decode((batch/'cli'/('invalid-'+str(i)+'.json')).read_bytes())['stdout'])['error']['code']=='INVALID_REQUEST' for i in range(6))
        entries += [dict(case='duplicate-and-conflict',state='PASS',same_attempt=True),dict(case='invalid-inputs',state='PASS',rejected_before_admission=6)]
        crashed=decode((batch/'cases/crash-after-start/job.json').read_bytes())
'''
s=s[:start]+replacement+s[end:]
s=s.replace("    rt.dispatch(retried['job_id']);finish('explicit-retry',retried)","""    if a.resume_tail and rt.get(retried['job_id'])['state']=='running' and alive(rt.execution(retried['job_id']).get('supervisor')) is False:
        cli('interrupted-client-recover',['recover','--job-id',retried['job_id']])
        interrupted,_=finish('interrupted-client-retry',retried,'failed','INTERRUPTED')
        retried=cli('resume-explicit-retry',['retry','--job-id',interrupted['job_id'],'--key','resume-retry'])
        assert retried['retry_of_job_id']==interrupted['job_id']
    rt.dispatch(retried['job_id']);finish('explicit-retry',retried)""")
p.write_text(s,encoding='utf-8')
