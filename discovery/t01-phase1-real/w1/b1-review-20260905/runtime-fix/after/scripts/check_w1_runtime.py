"""Read-only validation of W1-09A recorded runtime/CLI evidence and source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from check_w1_contract import validate_job, validate_transition

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'discovery/t01-phase1-real/w1/runtime-engineering-20260905'


def require(value,message):
    if not value: raise ValueError(message)


def read(path): return json.loads(path.read_text(encoding='utf-8'))


def verify(batch=DEFAULT):
    manifest=read(batch/'manifest.json')
    source_root=ROOT
    history=ROOT/'discovery/t01-phase1-real/w1/runtime-source-history.json'
    if history.exists():
        digest=hashlib.sha256((batch/'manifest.json').read_bytes()).hexdigest()
        matches=[r for r in read(history)['archives'] if r['manifest_sha256']==digest]
        require(len(matches)<=1,'Ambiguous historical source registration')
        if matches:
            source_root=(ROOT/matches[0]['source_root']).resolve()
            require(source_root.is_relative_to((ROOT/'discovery/t01-phase1-real').resolve()),'Unsafe historical source root')
    for base,entries in [(source_root,manifest['sources']),(batch,manifest['outputs'])]:
        for row in entries:
            path=(base/row['path']).resolve()
            require(path.is_relative_to(base.resolve()),'Manifest path escape')
            raw=path.read_bytes()
            require(len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'Evidence hash mismatch: '+row['path'])
    result=read(batch/'acceptance.json')
    require(result['status']=='PASS_ENGINEERING_ONLY' and result['scientific_execution']=='NOT_RUN'
            and result['production_status']=='NOT_DEPLOYED','Evidence scope mismatch')
    tests=ET.parse(batch/'runtime-tests.xml').findall('.//testcase')
    require(len(tests)==result['runtime_tests'] and not any(list(t) for t in tests),'Failed or skipped runtime case')
    require(set(result['runtime_cases'])=={f'RT{i:02d}' for i in range(1,16)},'Incomplete RT case coverage')
    for key,names in result['runtime_cases'].items():
        actual=sorted(t.attrib['name'] for t in tests if t.attrib['name'].startswith('test_'+key.lower()+'_'))
        require(names==actual and names,'RT coverage does not match executed tests')
    require(read(batch/'runtime-tests-command.json')['exit_code']==0,'Test process failed')
    for case in result['cli_cases']:
        folder=batch/'jobs'/case['name']
        value=validate_job(read(folder/'job.json'))
        require(value['state']==case['expected_state']==case['actual_state'],'CLI state mismatch')
        require(value['job_id']==case['job_id'] and not value['usable_for_pipeline'],'Job identity/consumption mismatch')
        events=read(folder/'events.json')
        for event in events: validate_job(event['snapshot'])
        for a,b in zip(events,events[1:]): validate_transition(a['snapshot'],b['snapshot'])
        require(events[-1]['snapshot']==value,'Final event mismatch')
        for ref in [value['request_artifact'],*value['artifacts']]:
            raw=(folder/(ref['artifact_id']+'.json')).read_bytes()
            require(len(raw)==ref['size_bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'Artifact mismatch')
        execution=read(folder/'execution.json')
        require(execution['tree_stopped'] is True,'Process termination not recorded')
        require(execution['observed_job_limits']['active_limit']==4,'Resource policy mismatch')
    commands=list((batch/'commands').glob('*.json'))
    require(len(commands)==result['cli_command_count'],'CLI command count mismatch')
    rejections=[read(p) for p in commands if read(p)['exit_code']==20]
    require(len(rejections)==2 and all(json.loads(p['stdout'])['error']['code']=='PROFILE_NOT_APPROVED' for p in rejections),'Model rejection evidence missing')
    return dict(status='PASS_ENGINEERING_ONLY',runtime_tests=len(tests),runtime_cases=15,cli_cases=len(result['cli_cases']),
                source_verification='CURRENT_REPOSITORY' if source_root==ROOT else 'ARCHIVED_EXECUTED_SOURCES',
                source_files=len(manifest['sources']),output_files=len(manifest['outputs']),production_status='NOT_DEPLOYED')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--batch',type=Path,default=DEFAULT)
    print(json.dumps(verify(parser.parse_args().batch),ensure_ascii=False))
