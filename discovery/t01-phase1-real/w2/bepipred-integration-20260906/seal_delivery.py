"""Read-only verify all completed execution evidence and create the W2 delivery index."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import subprocess

BASE=Path(__file__).parent;REPO=BASE.parents[3]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode, encode, sha
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.bepipred.policy import registered_profile, verify_assets


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(8*1024**2):h.update(block)
    return h.hexdigest()


def put(path,raw):
    if not isinstance(raw,bytes):raw=encode(raw)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw)


def main():
    assert not (BASE/'index.json').exists(),'Final index is immutable'
    subindices=[BASE/'acceptance-r01/index.json',REPO/'discovery/t01-phase1-real/w1/bepipred-shared-regression-20260906/structure/index.json',
        REPO/'discovery/t01-phase1-real/w1/bepipred-shared-regression-20260906/deeptmhmm/index.json']
    summaries=[];verified=0
    for path in subindices:
        value=decode(path.read_bytes());assert value['status']=='PASS'
        for name,ref in value['files'].items():
            target=path.parent/name
            assert digest(target)==ref['sha256'] and target.stat().st_size==ref['size_bytes'],str(target)
            verified+=1
        summaries.append(dict(path=path.relative_to(REPO).as_posix(),sha256=digest(path),cases=len(value['cases']),
            containers=sum(bool(c.get('artifacts_verified')) for c in value['cases']),published_artifacts=sum(c.get('artifacts_verified',0) for c in value['cases']),
            execution_profile=value['profile']))
    assert registered_profile()==summaries[0]['execution_profile']
    pinned=verify_assets()
    protected=decode((BASE/'protected-before.json').read_bytes())['files']
    assert all(digest(REPO/r['path'])==r['sha256'] and (REPO/r['path']).stat().st_size==r['size_bytes'] for r in protected)
    # Export the documented one-command result and every published artifact too.
    command=decode((BASE/'documented-command.json').read_bytes());output=decode(command['stdout']);job=output['job']
    rt=Runtime(REPO/'var/t01-phase1-real/bepipred-demo')
    assert rt.get(job['job_id'])==job and job['state']=='succeeded'
    put(BASE/'demo/job.json',job);put(BASE/'demo/result.json',output['result']);put(BASE/'demo/events.json',rt.events(job['job_id']))
    for ref in job['artifacts']:
        raw=rt.artifact_bytes(job['job_id'],ref['artifact_id']);assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes']
        put(BASE/'demo/artifacts'/ref['artifact_id'],raw)
    sources=[p for p in (REPO/'src/t01_phase1_real/development').rglob('*') if p.suffix in ('.py','.json')]
    sources += [REPO/p for p in ['scripts/t01_runtime.py','scripts/t01_development_supervisor.py','scripts/run_bepipred_acceptance.py',
        'tests/test_bepipred_development.py','docs/project/STATUS.md','docs/project/PHASE1_DELIVERY_PLAN.md','docs/project/OPEN_ITEMS.md',
        'docs/project/ARCHITECTURE.md','docs/development/RUNBOOK.md']]
    source_receipt=[]
    for path in sources:
        dest=BASE/'final-source'/path.relative_to(REPO)
        # Raw document snapshots are byte evidence, not a second navigation tree.
        if path.suffix=='.md':dest=dest.with_suffix('.md.snapshot')
        put(dest,path.read_bytes())
        source_receipt.append(dict(path=path.relative_to(REPO).as_posix(),snapshot=dest.relative_to(BASE).as_posix(),sha256=digest(path)))
    inventory={p.relative_to(BASE).as_posix():dict(sha256=digest(p),size_bytes=p.stat().st_size) for p in sorted(BASE.rglob('*')) if p.is_file()}
    value=dict(status='PASS',completed_at=datetime.now(timezone.utc).isoformat(),qualification='LOCAL_DEVELOPMENT_ONLY',
        scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,production_status='NOT_DEPLOYED',
        sub_batches=summaries,sub_batch_files_verified=verified,pinned_assets_verified=len(pinned['files']),protected_files_verified=len(protected),
        root_tests=dict(passed=1094,skipped=1,log='root-tests.txt'),targeted_tests=dict(passed=236,log='targeted-tests.txt'),
        raw_probes=[dict(path='raw-runs/'+n+'/index.json',sha256=digest(BASE/'raw-runs'/n/'index.json')) for n in ['safe51','invalid-star','short8']],
        documented_command=dict(path='documented-command.json',exported_artifacts=len(job['artifacts']),job_id=job['job_id']),
        postprocessing='OI-026; project linear_scores/peaks/map null; raw dual columns retained',files=inventory,final_sources=source_receipt,
        notes=[
            'BepiPred upstream package examples are not an independent scientific holdout; repeated-A boundary input is an engineering fixture.',
            'The initial raw run used native Windows CRLF FASTA; unified task FASTA uses LF. Both retain exact input hash and safe sequence identity.',
            'Initial unified smoke rejected native Plotly fragment because the parser expected a full HTML document. Corrected after inspecting original output; original failed result retained.',
            'The acceptance client/supervisor was interrupted during explicit retry. Existing completed evidence was reverified without rewriting; the stopped model had no receipt, so recovery correctly marked INTERRUPTED, followed by a new explicit retry.',
            'Raw short8 exits zero but exposes 8 probabilities and 9 smoothed values; project admission and postvalidation reject it. Raw star exits one.',
            'Native HTML references Plotly CDN and remains an unrendered original artifact; numeric CLI query and model execution require no network.',
            'W1 regressions are stored under W1 by the existing campaign entrypoints and linked here as W2 change validation. Previous W1 evidence remains unchanged.',
            'Full W1, N04 scientific acceptance, full W2 and target deployment remain incomplete. Legacy full Mock and S07 were unchanged and were not rerun.'
        ])
    put(BASE/'index.json',value)
    checked=subprocess.run([sys.executable,'-X','utf8',str(REPO/'scripts/check_docs.py')],capture_output=True)
    put(BASE/'docs-check.txt',checked.stdout+checked.stderr)
    assert checked.returncode==0,checked.stdout.decode(errors='replace')
    value['documentation_check']=dict(status='PASS',log='docs-check.txt',sha256=digest(BASE/'docs-check.txt'))
    value['files']['docs-check.txt']=dict(sha256=digest(BASE/'docs-check.txt'),size_bytes=(BASE/'docs-check.txt').stat().st_size)
    # Finish this newly created index only after its links and snapshot layout pass.
    (BASE/'index.json').write_bytes(encode(value))
    print(json.dumps(dict(status='PASS',sub_batches=summaries,files=len(inventory),index=str(BASE/'index.json')),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
