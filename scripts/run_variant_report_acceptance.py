"""New report executions over verified copies of historical real outputs; no model runs."""
import argparse
import copy
from pathlib import Path
import shutil
import subprocess
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import encode,decode,sha,RuntimeFault,now
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.variant_report import policy
from t01_phase1_real.development.variant_report.ranking import rank_fixture

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(value if isinstance(value,bytes) else encode(value))

def clone(original,root,archives,batch):
    manifests=[]
    for archive in archives:
        index=decode((archive/'index.json').read_bytes())
        for row in index['files']:
            raw=(archive/row['path']).read_bytes()
            assert len(raw)==row['bytes'] and sha(raw)==row['sha256'],row['path']
        manifests.append(dict(path=str(archive/'index.json'),sha256=sha((archive/'index.json').read_bytes()),files=len(index['files'])))
    shutil.copytree(original,root)
    rt=Runtime(root);restored=[]
    for archive in archives:
        for folder in (archive/'cases').iterdir():
            if not (folder/'job.json').exists():continue
            job=decode((folder/'job.json').read_bytes())
            for ref in job['artifacts']:
                with rt._db() as db:row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
                if row is None:continue
                assert decode(row['data'])==ref
                raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
                assert sha(raw)==ref['sha256'] and len(raw)==ref['size_bytes']
                target=root/row['relative_path'];assert target.resolve().is_relative_to(root.resolve())
                if target.read_bytes()!=raw:
                    restored.append(dict(path=row['relative_path'],before=sha(target.read_bytes()),after=sha(raw)))
                    target.write_bytes(raw)
    write(batch/(root.name+'-copy.json'),dict(original_root=str(original),copied_root=str(root),manifests=manifests,
        restored_only_new_copy=restored,semantics='Historical identities retained, no new model execution'))
    return rt

def source(rt,archive,name):
    j=rt.get(decode((archive/'cases'/name/'job.json').read_bytes())['job_id'])
    refs=[r for r in j['artifacts'] if r['role'] in ('result','diagnostic')]
    return dict(job_id=j['job_id'],artifact=refs[0] if refs else None)

def body(rt,src,mode):
    job=rt.get(src['job_id'])
    with rt._db() as db:req=decode(rt._input(db,job['request_artifact'],job['run_id']))
    return dict(protein_sequence=req['protein_sequence'],user_sequence_id='Historical real engineering report',
        upstream=dict(design_audit=src if mode=='N11_DESIGN_AUDIT' else None,foldx=src if mode!='N11_DESIGN_AUDIT' else None),
        variant_source=mode,foldx_bindings=[],timeout_seconds=60)

def markdown(report):
    lines=['# W6 逐变体工程评估报告','',f"结果：{report['outcome']}；总数 {report['summary']['total']}，淘汰 {report['summary']['excluded']}，未判定 {report['summary']['undetermined']}。",
        '', '开发未签收；N13 未执行；无正式排名、最佳候选或 Agent C 交接。','',
        '| 变体 | 序列 | 状态 | ESM-IF1 变化 % | 淘汰原因 | FoldX ΔΔG kcal/mol |',
        '|---|---|---|---|---|---|']
    for r in report['records']:
        reasons='；'.join(x['code'] for x in r['exclusion_reasons']) or '输入未齐，需复核'
        lines.append(f"| {r['id']} | {r['sequence']} | {r['disposition']} | {(r['esm_if1'] or {}).get('delta_pct')} | {reasons} | {(r['foldx'] or {}).get('ddg_foldx')} |")
    lines+=['','具体缺项、逐位权限、六维负担、突变、SHA-256、任务/尝试及原始产物来源见同目录 result.json。','']
    return '\n'.join(lines).encode('utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--batch',required=True);a=p.parse_args()
    root=Path(a.root).absolute();batch=Path(a.batch).absolute()
    assert root.is_relative_to(REPO/'var/t01-phase1-real') and batch.is_relative_to(REPO/'discovery/t01-phase1-real/w6')
    assert not root.exists() and not batch.exists();root.mkdir(parents=True);batch.mkdir(parents=True)
    design=REPO/'discovery/t01-phase1-real/w5/design-backend-integration-20260908/acceptance-r02'
    esm=REPO/'discovery/t01-phase1-real/w5/esm-if1-integration-20260908/acceptance-r01'
    fold=REPO/'discovery/t01-phase1-real/w6/foldx-integration-20260909/acceptance-r05'
    dr=clone(REPO/'var/t01-phase1-real/design-backend-acceptance-r02',root/'design',[esm,design],batch)
    fr=clone(Path(decode((fold/'index.json').read_bytes())['runtime_root']),root/'foldx',[fold],batch)
    dbody=body(dr,source(dr,design,'historical-24-burden'),'N11_DESIGN_AUDIT')
    fbody=body(fr,source(fr,fold,'buildmodel-three-variants-five-runs'),'FOLDX_EXPLICIT_ENGINEERING')
    cases=[];guards=[]
    def finish(rt,name,j,state='succeeded',code=None):
        j=rt.get(j['job_id']);assert j['state']==state and j['error_code']==code,(name,j)
        v=rt.result(j['job_id']) if j['artifacts'] else None
        write(batch/'cases'/name/'job.json',j);write(batch/'cases'/name/'events.json',rt.events(j['job_id']))
        if v:
            assert not v['usable_for_pipeline'] and not v['automatic_handoff'] and v['scientific_signoff'] is None
            write(batch/'cases'/name/'result.json',v)
            if v['report']:write(batch/'cases'/name/'report.md',markdown(v['report']))
        for ref in j['artifacts']:write(batch/'cases'/name/'artifacts'/ref['artifact_id'],rt.artifact_bytes(j['job_id'],ref['artifact_id']))
        cases.append(dict(case=name,job_id=j['job_id'],runtime_root=str(rt.root),state=state,error_code=code))
        print(name,state,code,flush=True);return j,v
    def run(rt,name,b,fault=None,state='succeeded',code=None):
        write(batch/'requests'/(name+'.json'),b);j=rt.submit_sequence(encode(b),name,policy.TOOL);rt._development_fault=fault
        try:rt.dispatch(j['job_id'])
        finally:rt._development_fault=None
        if fault=='interrupt_after_claim':rt.recover(j['job_id'])
        return finish(rt,name,j,state,code)
    dj,dv=run(dr,'real-24-all-excluded',dbody)
    report=dv['report'];assert report['summary']==dict(total=24,excluded=24,retained=0,undetermined=0)
    assert all(r['esm_if1']['passed'] is False and any(e['code']=='R35_DETERIORATION_EXCEEDED' for e in r['exclusion_reasons']) for r in report['records'])
    assert report['best_candidate'] is None and report['outcome']=='ALL_EXCLUDED'
    fj,fv=run(fr,'real-foldx-three-bound',fbody)
    assert len(fv['report']['records'])==3 and all(r['foldx']['runs']==5 and r['stability_state']=='BOUND_UNREVIEWED' for r in fv['report']['records'])
    assert all(r['disposition']=='UNDETERMINED' for r in fv['report']['records'])
    failed=copy.deepcopy(fbody);failed['upstream']['foldx']=source(fr,fold,'tool-failure')
    _,v=run(fr,'failed-foldx-source',failed)
    assert v['report']['source_receipts']['foldx']['state']=='failed' and len(v['report']['records'])==1
    assert v['report']['records'][0]['foldx'] is None
    empty=copy.deepcopy(dbody);empty['upstream']['design_audit']=None
    run(dr,'missing-sources',empty)
    def reject(rt,name,b):
        try:rt.submit_sequence(encode(b),name,policy.TOOL)
        except RuntimeFault as exc:guards.append(dict(case=name,code=exc.code,detail=str(exc)))
        else:raise AssertionError('Invalid request accepted: '+name)
    wrong=copy.deepcopy(fbody);wrong['protein_sequence']=dbody['protein_sequence'];reject(fr,'different-wt',wrong)
    wrong=copy.deepcopy(fbody);wrong['upstream']['foldx']=source(fr,fold,'positionscan-two-positions');reject(fr,'positionscan-not-buildmodel',wrong)
    wrong=copy.deepcopy(dbody);wrong['upstream']['foldx']=fbody['upstream']['foldx'];reject(dr,'cross-runtime-foldx-ref',wrong)
    wrong=copy.deepcopy(dbody);wrong['upstream']['design_audit']['artifact']['sha256']='0'*64;reject(dr,'forged-artifact',wrong)
    wrong=copy.deepcopy(dbody);wrong['foldx_bindings']=[dict(sample_number=1,variant_id='wrong-id')];reject(dr,'unavailable-variant-link',wrong)
    assert dr.submit_sequence(encode(dbody),'real-24-all-excluded',policy.TOOL)['job_id']==dj['job_id']
    wrong=copy.deepcopy(dbody);wrong['user_sequence_id']='changed';reject(dr,'real-24-all-excluded',wrong)
    for fault,code in [('compute_failure','TOOL_FAILED'),('corrupt_output','OUTPUT_INVALID'),('interrupt_after_claim','INTERRUPTED')]:
        j,_=run(dr,fault,dbody,fault,'failed',code)
        retry=dr.control(encode(dict(contract_version='0.1.0',operation='retry',job_id=j['job_id'],idempotency_key='w6-report-'+fault+'-retry')))
        dr.dispatch(retry['job_id']);finish(dr,fault+'-retry',retry)
    # CLI reads revalidate publication hashes; single-record selection retains report binding.
    for name,rt,j,vid in [('all-excluded',dr,dj,'sample-1'),('foldx',fr,fj,'single-A1G')]:
        for operation,args in [('result',[]),('variant-record',['--id',vid])]:
            proc=subprocess.run([sys.executable,'-X','utf8',str(REPO/'scripts/t01_runtime.py'),'--root',str(rt.root),operation,'--job-id',j['job_id'],*args],capture_output=True)
            assert proc.returncode==0,proc.stdout+proc.stderr
            write(batch/'queries'/(name+'-'+operation+'.json'),decode(proc.stdout))
    flags={n:False for n in ('epitope_violation','safety_excluded','constraint_override','host_similarity_high','burden_exceeded')}
    records=[dict(id=n,overall=dev,ddg=0.,count=6,epitope=1.3,epitope_state='VERIFIED',soft_penalty=False,host_medium=False,flags=flags)
        for n,dev in [('a',.8),('b',.8),('dominated',.7)]]
    numeric=rank_fixture(records,'general',evidence_kind='SYNTHETIC_CONTRACT_FIXTURE')
    assert numeric['score_groups']==[dict(score=.89,ids=['a','b'])]
    write(batch/'ranking-fixture.json',dict(inputs=records,result=numeric))
    # Mutations only on new runtime copies; restore after probes so documented queries remain valid.
    def tamper(rt,job,ref,operation,name):
        with rt._db() as db:path=rt.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
        saved=path.read_bytes()
        try:
            path.write_bytes(b'{}')
            try:operation()
            except RuntimeFault as exc:guards.append(dict(case=name,code=exc.code))
            else:raise AssertionError('Tamper accepted')
        finally:path.write_bytes(saved)
    src=fbody['upstream']['foldx'];sj=fr.get(src['job_id']);raw=next(r for r in sj['artifacts'] if r['role']=='raw')
    tamper(fr,sj,raw,lambda:fr.submit_sequence(encode(fbody),'raw-tamper',policy.TOOL),'foldx-native-hash')
    # Late source mutation after computation must fail publication too.
    from t01_phase1_real.development.variant_report import service
    with fr._db() as db:target=fr.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(raw['artifact_id'],)).fetchone()[0]
    saved=target.read_bytes();original_evaluate=service.evaluate
    def late_evaluate(*args):
        value=original_evaluate(*args);target.write_bytes(b'{}');return value
    queued=fr.submit_sequence(encode(fbody),'late-source-change',policy.TOOL)
    try:
        service.evaluate=late_evaluate;fr.dispatch(queued['job_id'])
    finally:
        service.evaluate=original_evaluate;target.write_bytes(saved)
    finish(fr,'late-source-change',queued,'failed','HASH_MISMATCH')
    ref=next(r for r in dj['artifacts'] if r['role']=='result')
    tamper(dr,dj,ref,lambda:dr.result(dj['job_id']),'published-report-hash')
    write(batch/'profile.json',policy.registered_profile());write(batch/'rules.json',policy.registered_rules())
    paths=list(policy.HERE.glob('*.py'))+[REPO/'scripts/run_variant_report_acceptance.py',REPO/'scripts/audit_variant_report_evidence.py',REPO/'tests/test_variant_report_development.py']
    paths += [policy.HERE.parent/n for n in ('runtime.py','cli.py','registry.py','contracts.py','design_backend/source.py')]
    for path in paths:write(batch/'source'/path.relative_to(REPO),path.read_bytes())
    files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()]
    write(batch/'index.json',dict(status='PASS',completed_at=now(),cases=cases,guards=guards,files=files,
        historical_models_reexecuted=False,real_excluded=24,real_foldx_bound=3,scientific_ranking=False,formal_delivery=False,
        runtime_root=str(root),production_status='NOT_DEPLOYED'))

if __name__=='__main__':main()
