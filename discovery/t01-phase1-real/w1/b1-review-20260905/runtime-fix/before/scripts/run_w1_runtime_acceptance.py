"""Create a new local engineering CLI campaign and actual RT01-RT15 pytest evidence."""
import argparse
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.common import TOOL, decode, encode, new_id, now, profile, sha
from t01_phase1_real.files import read_locked, within
from t01_phase1_real.runtime import Runtime


def run(output):
    output=output.resolve()
    if not output.is_relative_to(ROOT/'discovery/t01-phase1-real/w1') or output.exists():
        raise ValueError('Use a new directory under discovery/t01-phase1-real/w1')
    output.mkdir(parents=True)
    runtime=Runtime(ROOT/'.tmp'/('w1-runtime-'+new_id('run')))
    commands=[]
    def save(name,value):
        path=output/name; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(encode(value))
    def call(*args, expected=0):
        argv=[sys.executable,'-X','utf8',str(ROOT/'scripts/w1_runtime.py'),'--root',str(runtime.root),*args]
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        record=dict(argv=argv,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,observed_at=now())
        commands.append(record); save(f'commands/{len(commands):02d}.json',record)
        assert result.returncode==expected,record
        return decode(result.stdout)
    cases=[]
    def case(name,job,expected):
        assert job['state']==expected,job
        assert not job['usable_for_pipeline'] and job['evidence_kind']=='ENGINEERING_FIXTURE'
        cases.append(dict(name=name,job_id=job['job_id'],expected_state=expected,actual_state=job['state']))
        save(f'jobs/{name}/job.json',job)
        save(f'jobs/{name}/events.json',runtime.events(job['job_id']))
        save(f'jobs/{name}/execution.json',runtime.execution(job['job_id']))
        for ref in [job['request_artifact'],*job['artifacts']]:
            with runtime._db() as db:
                relative=db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
            raw=read_locked(within(runtime.root,relative))
            assert len(raw)==ref['size_bytes'] and sha(raw)==ref['sha256']
            (output/f'jobs/{name}'/(ref['artifact_id']+'.json')).write_bytes(raw)
        if job['attempt_id']:
            for filename in ['input.json','worker-started.json','child.json','output.json','receipt.json']:
                path=within(runtime.root,runtime.attempt_path(job)+'/'+filename)
                if path.exists(): (output/f'jobs/{name}'/filename).write_bytes(read_locked(path))
    success=call('demo'); case('success',success,'succeeded')
    assert call('get','--job-id',success['job_id'])==success
    failed=call('demo','--mode','fail'); case('failure',failed,'failed')
    timed=call('demo','--mode','tree','--delay','10'); case('timeout',timed,'timed_out')
    run_id=call('create-run','--key','cancel-run')['run_id']
    save('cancel-input.json',dict(mode='tree',payload='cancel engineering fixture',delay_seconds=10))
    ref=call('stage','--run-id',run_id,'--input',str(output/'cancel-input.json'))
    body=dict(contract_version='0.1.0',run_id=run_id,request_id='cancel-request',idempotency_key='cancel-submit',
              tool_id=TOOL,node_id=None,run_mode='engineering_example',request_artifact=ref,execution_profile=profile(),rule_profile=None)
    save('cancel-submit.json',body)
    queued=call('submit','--input',str(output/'cancel-submit.json'))
    assert call('submit','--input',str(output/'cancel-submit.json'))['job_id']==queued['job_id']
    active=call('dispatch','--job-id',queued['job_id'])
    deadline=time.monotonic()+5
    while not within(runtime.root,runtime.attempt_path(active)+'/child.json').exists():
        assert time.monotonic()<deadline
        time.sleep(.025)
    call('cancel','--job-id',active['job_id'],'--key','cancel-1')
    cancelled=call('wait','--job-id',active['job_id']); case('cancel',cancelled,'cancelled')
    retry=call('retry','--job-id',failed['job_id'],'--key','retry-1')
    call('dispatch','--job-id',retry['job_id'])
    retried=call('wait','--job-id',retry['job_id']); case('retry',retried,'failed')
    assert retried['retry_of_job_id']==failed['job_id'] and retried['attempt_id']!=failed['attempt_id']
    with runtime._db() as db: jobs_before=db.execute('SELECT count(*) FROM jobs').fetchone()[0]
    for tool in ['t01.real.af3','t01.real.esmfold2']:
        candidate=dict(body,tool_id=tool,node_id='N01',run_mode='g0_probe',idempotency_key=tool)
        save('rejected-submit.json',candidate)
        rejection=call('submit','--input',str(output/'rejected-submit.json'),expected=20)
        assert rejection['error']['code']=='PROFILE_NOT_APPROVED'
    with runtime._db() as db: assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==jobs_before
    argv=[sys.executable,'-X','utf8','-m','pytest','-o','addopts=','-q','tests/test_w1_runtime.py',
          '--junitxml='+str(output/'runtime-tests.xml')]
    result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=120,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    save('runtime-tests-command.json',dict(argv=argv,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0,result.stdout
    tests=ET.parse(output/'runtime-tests.xml').findall('.//testcase')
    covered={f'RT{i:02d}':sorted(t.attrib['name'] for t in tests if t.attrib['name'].startswith(f'test_rt{i:02d}_')) for i in range(1,16)}
    assert all(covered.values())
    save('acceptance.json',dict(status='PASS_ENGINEERING_ONLY',date=now(),runtime_root=str(runtime.root),
        evidence_kind='ENGINEERING_FIXTURE',scientific_execution='NOT_RUN',production_status='NOT_DEPLOYED',
        execution_profile=profile(),cli_cases=cases,cli_command_count=len(commands),runtime_cases=covered,
        runtime_tests=len(tests),server_execution='NOT_RUN',no_scientific_fallback=True))
    save('environment.json',dict(os=platform.platform(),python=sys.version,python_executable=sys.executable,
        sqlite=sqlite3.sqlite_version,jsonschema=version('jsonschema'),execution_backend='Windows Job Objects',
        host_role='LOCAL_DEVELOPMENT',observed_at=now()))
    sources=[*sorted((ROOT/'src/t01_phase1_real').glob('*.py')),*sorted((ROOT/'scripts').glob('w1_runtime*.py')),
             Path(__file__),ROOT/'scripts/check_w1_runtime.py',ROOT/'tests/test_w1_runtime.py',
             ROOT/'tests/test_w1_runtime_evidence.py',ROOT/'docs/project/sources/PHASE1_W1_SERVER_CAPACITY_20260905.json']
    entries=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size) for p in sources]
    outputs=[dict(path=p.relative_to(output).as_posix(),sha256=sha(p.read_bytes()),size_bytes=p.stat().st_size)
             for p in sorted(output.rglob('*')) if p.is_file()]
    save('manifest.json',dict(source_root='REPOSITORY',sources=entries,outputs=outputs))
    return dict(status='PASS_ENGINEERING_ONLY',runtime_tests=len(tests),runtime_cases=len(covered),cli_cases=len(cases),output=str(output))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().output_dir),ensure_ascii=False))
