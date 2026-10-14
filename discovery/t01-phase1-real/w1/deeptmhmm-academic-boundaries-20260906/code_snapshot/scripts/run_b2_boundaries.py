"""Predeclare and run bounded, offline Academic experiments; no production worker."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from b2_boundary_evidence import (BATCH, IMAGE, OLD, REVIEW, ROOT, digest, fingerprint,
    inventory, load_old, read, require, safe_id, verify_files, write_new)

DOCKER = ['docker', '--config', str(ROOT/'.tmp/b2-boundaries-docker-client'),
          '--host', 'npipe:////./pipe/dockerDesktopLinuxEngine']


def prepare(batch):
    require(batch.resolve().is_relative_to(ROOT) and not batch.exists(), 'Use a new project batch')
    load_old('verify_evidence').verify(assets=True)
    protected = {p['path']:p for p in read(REVIEW/'protected_before.json')['files']}
    for entry in read(REVIEW/'manifest.json')['sources']:
        protected[entry['path']] = entry
    for folder in [REVIEW, ROOT/'discovery/t01-phase1-real/w1/b2-review-maintenance-20260906']:
        for p in folder.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                protected[p.relative_to(ROOT).as_posix()] = fingerprint(p)
    for path in ['scripts/check_docs.py','tests/test_docs.py']:
        protected[path] = fingerprint(ROOT/path)
    verify_files(ROOT, list(protected.values()))
    batch.mkdir(parents=True)
    write_new(batch/'protected_before.json', dict(files=list(protected.values())))
    short = load_old('audit_raw').fasta((OLD/'inputs/short.fasta').read_text())
    old_id, sequence = next(iter(short.items()))
    rows = [dict(id='safe-id', sequence=sequence, kind='EXISTING_G0_REFERENCE', source=fingerprint(OLD/'inputs/short.fasta'),
                 original_user_id='../输入 | safe-id\nmetadata-only', outcome='EXPECT_COMPLETE_RAW', purpose='Safe-ID full-artifact link and original-ID comparison')]
    for length in [1,8,9,29,30,1020,1021,1022,1023]:
        rows.append(dict(id='length-'+str(length),sequence=(sequence*((length//len(sequence))+1))[:length],
            kind='SYNTHETIC_LENGTH_FIXTURE', original_user_id='synthetic_'+str(length),
            source=fingerprint(OLD/'inputs/short.fasta'), outcome='OBSERVE_COMPLETE_OR_DIAGNOSED_FAILURE',
            purpose='Real tokenizer/chunk and process boundary; not biological accuracy'))
    rows.extend([
        dict(id='empty',sequence='',kind='INVALID_INPUT_FAULT',original_user_id='empty', outcome='EXPECT_EXECUTION_FAILURE',purpose='Empty FASTA record rejection'),
        dict(id='invalid-symbol',sequence='ACDEFGHIK*',kind='INVALID_INPUT_FAULT',original_user_id='star',outcome='EXPECT_EXECUTION_FAILURE',purpose='Original tokenizer invalid-symbol failure'),
        dict(id='existing-output',sequence=sequence,kind='EXISTING_OUTPUT_FAULT',original_user_id=old_id,outcome='EXPECT_EXECUTION_FAILURE',purpose='Actual original-package failure with retained stale successful artifacts',seed_from='safe-id')])
    for row in rows:
        row['internal_id'] = safe_id(row['sequence'])
        p = batch/'inputs'/(row['id']+'.fasta')
        p.parent.mkdir(exist_ok=True)
        with p.open('x',encoding='utf-8',newline='\n') as f:
            f.write('>'+row['internal_id']+'\n'+row['sequence']+'\n')
        row['input'] = fingerprint(p)
        row['sequence_sha256'] = hashlib.sha256(row['sequence'].encode()).hexdigest()
    plan = dict(stage='W1-08B2_SUPPLEMENTAL_DEVELOPMENT_EVIDENCE', production_enabled=False,
        scientific_signoff=None, original_entrypoint=True, image_id=IMAGE,
        limits=dict(cpu_quota=8,cpu_affinity='0-7',memory_bytes=10*1024**3,timeout_seconds=900,parallel_models=1),
        cases=rows, fault_cases=['missing-prediction','missing-regions','missing-probability','missing-plot','missing-report',
            'truncated-labels','wrong-sequence','wrong-id','wrong-region','nan-probability','wrong-probability-position',
            'hash-tamper','unexpected-artifact','invalid-plot','wrong-report-id','missing-token-trace','wrong-token'],
        acceptance='Success: exact ID/sequence/labels/regions/probability/hash/token coverage; failure: concrete diagnostics, topology null, no consumption. No prediction or numeric accuracy thresholds invented.')
    write_new(batch/'plan.json', plan)
    write_new(batch/'method_summary.json', dict(base_method=fingerprint(OLD/'method_summary.json'),
        tool_version='1.0 - Academic Version', image_id=IMAGE, runtime_packages=read(OLD/'method_summary.json')['runtime_packages'],
        parameters=read(OLD/'method_summary.json')['parameters'], observation='Read-only Python line tracing of original tokenization/chunk return and embedding completion',
        applicability_note='Prior long-chunk not-exercised statement belongs to prior batch; actual new observations recorded per case.',
        model_execution='PENDING_EXECUTION', scientific_accuracy='NOT_EVALUATED', production_status='NOT_DEPLOYED'))
    print(json.dumps(dict(status='PREDECLARED',cases=len(rows),fault_cases=len(plan['fault_cases']),protected_files=len(protected))))


def run_case(batch, case):
    plan = read(batch/'plan.json')
    row = next(r for r in plan['cases'] if r['id']==case)
    verify_files(ROOT,[row['input']])
    target = batch/'runs'/case
    require(not target.exists(), 'Preserve existing attempt; use a new batch')
    assets, asset_count = load_old('run_offline').check_assets()
    image_inspect = subprocess.run(DOCKER+['image','inspect','--format','{{json .Id}} {{json .Os}} {{json .Architecture}}',IMAGE],capture_output=True,timeout=20,check=True)
    require(image_inspect.stdout.decode().strip()==f'"{IMAGE}" "linux" "amd64"','Wrong existing image')
    target.mkdir(parents=True)
    output = target/'output'; output.mkdir()
    (target/'input.fasta').write_bytes((ROOT/row['input']['path']).read_bytes())
    if row.get('seed_from'):
        seed=batch/'runs'/row['seed_from']
        require(read(seed/'execution.json')['container_exit_code']==0,'Seed source must be an actual success')
        shutil.copytree(seed/'output/result',output/'result')
        write_new(target/'seed.json',dict(source_case=row['seed_from'],files=inventory(output)))
    name = 't01-b2-boundary-'+uuid.uuid4().hex[:12]
    command = DOCKER+['create','--pull','never','--name',name,'--network','none','--read-only',
        '--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','512',
        '--memory','10g','--memory-swap','10g','--cpus','8','--cpuset-cpus','0-7',
        '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','--env','CUDA_VISIBLE_DEVICES=-1','--env','PYTHONUNBUFFERED=1',
        '--mount',f'type=bind,source={assets},target=/app,readonly',
        '--mount',f'type=bind,source={target/"input.fasta"},target=/input.fasta,readonly',
        '--mount',f'type=bind,source={ROOT/"scripts/b2_boundary_probe.py"},target=/probe.py,readonly',
        '--mount',f'type=bind,source={output},target=/out','--workdir','/app','--entrypoint','python',IMAGE,'-B','/probe.py']
    sources=[fingerprint(ROOT/p) for p in ['scripts/b2_boundary_probe.py','scripts/b2_boundary_evidence.py','scripts/run_b2_boundaries.py']]
    record=dict(case=case,started_at=datetime.now(timezone.utc).isoformat(),command=command,image_id=IMAGE,
        plan_sha256=digest(batch/'plan.json'),sources=sources,assets_verified_before=asset_count,
        input_sha256=digest(target/'input.fasta'),timed_out=False,stopped_confirmed=False,production_status='NOT_DEPLOYED')
    write_new(target/'command.json',record)
    created=subprocess.run(command,capture_output=True,timeout=30)
    (target/'create.stdout').write_bytes(created.stdout); (target/'create.stderr').write_bytes(created.stderr)
    require(created.returncode==0,'Container creation failed; diagnostics retained')
    container_id=created.stdout.decode().strip()
    require(len(container_id)==64 and all(c in '0123456789abcdef' for c in container_id),'Invalid created container ID')
    record['container_id']=container_id
    started=time.monotonic()
    try:
        with (target/'stdout.txt').open('wb') as stdout, (target/'stderr.txt').open('wb') as stderr:
            try:
                completed=subprocess.run(DOCKER+['start','--attach',container_id],stdout=stdout,stderr=stderr,timeout=900)
                record['attach_exit_code']=completed.returncode
            except subprocess.TimeoutExpired:
                record['timed_out']=True
                killed=subprocess.run(DOCKER+['kill',container_id],capture_output=True,timeout=30)
                (target/'kill.stdout').write_bytes(killed.stdout); (target/'kill.stderr').write_bytes(killed.stderr)
        inspected=subprocess.run(DOCKER+['inspect',container_id],capture_output=True,timeout=30,check=True)
        (target/'container_inspect.json').write_bytes(inspected.stdout)
        state=json.loads(inspected.stdout)[0]['State']
        record.update(container_exit_code=state['ExitCode'],oom_killed=state['OOMKilled'],
            stopped_confirmed=not state['Running'] and state['Status']=='exited')
    finally:
        removed=subprocess.run(DOCKER+['rm','-f',container_id],capture_output=True,timeout=30)
        (target/'remove.stdout').write_bytes(removed.stdout); (target/'remove.stderr').write_bytes(removed.stderr)
        record['remove_exit_code']=removed.returncode
        record['elapsed_seconds']=time.monotonic()-started
        _,record['assets_verified_after']=load_old('run_offline').check_assets()
        record['artifacts']=inventory(output)
        write_new(target/'execution.json',record)
    print(json.dumps({k:record[k] for k in ['case','container_exit_code','oom_killed','timed_out','stopped_confirmed','elapsed_seconds']}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','run'])
    parser.add_argument('--batch',type=Path,default=BATCH)
    parser.add_argument('--case')
    args=parser.parse_args()
    batch=args.batch.resolve()
    require(batch.is_relative_to(ROOT),'Batch outside project')
    if args.mode=='prepare':
        prepare(batch)
    else:
        for row in read(batch/'plan.json')['cases']:
            if args.case is None or row['id']==args.case:
                run_case(batch,row['id'])
