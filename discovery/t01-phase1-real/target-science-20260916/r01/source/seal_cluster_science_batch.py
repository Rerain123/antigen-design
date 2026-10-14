"""Verify collected target evidence without rerunning or changing scientific jobs."""
import json,hashlib,io,zipfile,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'discovery/t01-phase1-real/target-science-20260916/r01'
def read(p):return json.loads(p.read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def result(n):return read(OUT/n/'result.json')
expected={n:'succeeded' for n in ['structure-design','structure-n10','proteinmpnn','esm-if1','n10','foldx-scan-r02','foldx-build-r02','proteinmpnn-recover','wt-reference','scan-report']}
expected.update({n:'failed' for n in ['thermompnn','n16','foldx-scan','foldx-build']})
expected.update({n:'cancelled' for n in ['proteinmpnn-cancel','foldx-build-cancel']})
rows=[];count=0;gpu=[]
for name,state in expected.items():
    folder=OUT/name;j=read(folder/'job.json');ex=read(folder/'execution.json');v=result(name)
    assert j['state']==state,(name,j['state'])
    assert not j['usable_for_pipeline'] and not v['usable_for_pipeline'] and not v['automatic_handoff']
    assert ex['tree_stopped'] is True
    for ref in j['artifacts']:
        raw=(folder/'artifacts'/ref['artifact_id']).read_bytes()
        assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
        count+=1
    if ex.get('resident_receipt'):
        receipt=ex['resident_receipt'];assert receipt['stopped_confirmed']
        assert receipt['binding']=={k:j[k] for k in ('job_id','attempt_id','execution_identity')}
    if j['tool_id'] in ('t01.real.proteinmpnn','t01.real.esm_if1','t01.real.thermompnn'):gpu.append(j)
    rows.append(dict(case=name,job_id=j['job_id'],attempt_id=j['attempt_id'],tool_id=j['tool_id'],state=state,error_code=j['error_code'],artifacts_verified=len(j['artifacts']),result=f'{name}/result.json',execution=f'{name}/execution.json'))
gpu.sort(key=lambda j:j['started_at'])
assert all(a['finished_at']<=b['started_at'] for a,b in zip(gpu,gpu[1:])), 'GPU tasks overlap'
assert result('proteinmpnn')['generation']['generated_count']==1
esm=result('esm-if1')['scoring'];assert len(esm['records'])==1 and esm['baseline_status']=='computed_once'
scan=result('foldx-scan-r02');assert scan['repair'] and scan['native_completeness']['complete_native_output'] and len(scan['ddg_results'])==40
build=result('foldx-build-r02');assert build['repair'] and build['native_completeness']['complete_native_output']
assert len(build['variant_ddg'])==3 and all(x['runs']==5 and len(x['native_ddg_runs'])==5 for x in build['variant_ddg'])
n10=result('n10');assert n10['steps']['aggregation']['execution']['status']=='executed'
assert n10['steps']['aggregation']['execution']['command']['runtime']=='resident-process'
assert n10['steps']['ph_stability']['execution']['status']=='executed' and n10['developability']['overall_score'] is None
cancel=read(OUT/'foldx-build-cancel/execution.json');assert cancel['resident_receipt']['state']=='cancelled'
before=read(OUT/'foldx-build-cancel/lifecycle_before.json');assert before['native_started'] and not (before['resident_receipt'] or {}).get('stopped_confirmed')
recovery=read(OUT/'proteinmpnn-recover/job.json');before=read(OUT/'proteinmpnn-recover/lifecycle_before.json')
assert all(recovery[k]==before['job'][k] for k in ('job_id','attempt_id','execution_identity'))
assert read(OUT/'proteinmpnn-recover/execution.json')['resident_target']==before['execution']['resident_target']
assert any(e['event']=='controller_recovery' for e in read(OUT/'proteinmpnn-recover/events.json'))
assert result('thermompnn')['execution']['exit_code']==0 and 'gpu_name' in result('thermompnn')['execution']['diagnostic']
assert result('n16')['execution']['worker_started'] is False
report=result('scan-report');engines=report['delivery']['wt_reference']['engines']
assert engines['thermompnn']['state']=='failed'
exports=[]
for item in report['raw_artifacts']:
    if item['path'] in ('output/package.zip','output/report.md','output/package-manifest.json'):
        raw=(OUT/'scan-report/artifacts'/item['artifact']['artifact_id']).read_bytes()
        name='backend-'+Path(item['path']).name;(OUT/name).write_bytes(raw)
        if name.endswith('.zip'):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:assert z.testzip() is None
        exports.append(dict(path=name,size_bytes=len(raw),sha256=sha(raw)))
site=read(OUT/'site-final.json');assert site['generation']==site['observed']==11
assert all(c['ready'] and c['restartCount']==0 for p in site['pods'] for c in p['containers'])
summary=dict(status='EXECUTED_WITH_OPEN_DEPLOYMENT_BLOCKERS',boundary='TARGET_RESIDENT_ENGINEERING_UNREVIEWED',runtime_root='/var/lib/t01/target-science-20260916-r01',cases=rows,
    job_counts={s:sum(r['state']==s for r in rows) for s in ('succeeded','failed','cancelled')},artifacts_verified=count,
    gpu_serial_execution_verified=True,foldx=dict(asset_registry_supplemented=True,asset_files_verified=17,scan_records=40,build_variants=3,runs_per_variant=5),
    n10=dict(a3d_global_score=n10['steps']['aggregation']['global_score'],propka_curve_points=len(n10['steps']['ph_stability']['dg_curve']),n10_complete=False),
    lifecycle=dict(inflight_foldx_cancellation=True,controller_recovery_same_attempt=True,worker_restart_tested=False,short_gpu_cancel_raced_with_native_completion=True),
    exports=exports,open_blockers=[dict(tool='ThermoMPNN',cause='Native output succeeded, parser pins original RTX 5070 Ti gpu_name/gpu_capability and rejects A100',closure='Publish target GPU observation adaptation with preserved runtime/hash/numeric checks; new target task must parse 180 raw SSM rows'),dict(tool='N16',cause='Windows dependency manifest applied to Linux wheel installation; .pyd/.dll and installer metadata differ, colorama absent',closure='Create independent pinned Linux dependency profile from approved wheels and required packages, preserve Windows manifest, publish and run fresh independent E.coli fixture')],
    scientific_gate='CLOSED',production_status='NOT_DEPLOYED',original_24_rerun=False,himat_tested=False,rustfs_report_published=False)
save(OUT/'summary.json',summary)
src=OUT/'source';src.mkdir(exist_ok=True)
for name in ('run_cluster_science_batch.py','seal_cluster_science_batch.py'):shutil.copyfile(ROOT/'.tmp'/name,src/name)
entries=[dict(path=p.relative_to(OUT).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(OUT.rglob('*')) if p.is_file() and p!=OUT/'index.json']
save(OUT/'index.json',dict(status=summary['status'],files=entries,artifacts_verified=count))
assert all((OUT/r['path']).stat().st_size==r['bytes'] and sha((OUT/r['path']).read_bytes())==r['sha256'] for r in entries)
print(json.dumps(dict(jobs=len(rows),counts=summary['job_counts'],artifacts_verified=count,index_files=len(entries),exports=exports,n10=summary['n10']),ensure_ascii=False))
