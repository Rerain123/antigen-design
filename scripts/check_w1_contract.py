"""Offline design checks only. Does not schedule jobs or calculate scientific values."""
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = ROOT/'工作流设计/02-数据契约/phase1-real-v0.1'


def require(value, message):
    if not value:
        raise ValueError(message)


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite JSON number: '+value)
    def finite_float(value):
        parsed = float(value)
        require(math.isfinite(parsed), 'Nonfinite JSON exponent')
        return parsed
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite_float)


def read(path):
    return strict_json(path.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def contract():
    return read(CONTRACT_ROOT/'contract.json')


def schema_check(value, name):
    schema = read(CONTRACT_ROOT/(name+'.schema.json'))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value), key=lambda e:str(list(e.path)))
    require(not errors, 'Schema error: '+('; '.join(e.message for e in errors[:3])))


def tool_check(value):
    row = next((r for r in contract()['tools'] if r['tool_id']==value['tool_id']), None)
    require(row is not None and row['node_id']==value['node_id'], 'Tool/node registration mismatch')
    if row['module']=='A':
        require(value['run_mode']=='engineering_example', 'Engineering worker cannot use scientific mode')


def identity_check(value):
    prefixes = contract()['names']['id_prefixes']
    for field, kind in [('run_id','run'),('job_id','job'),('attempt_id','attempt'),('artifact_id','artifact'),('retry_of_job_id','job')]:
        if value.get(field) is not None:
            require(value[field].startswith(prefixes[kind]), 'Foreign identity namespace: '+field)


def validate_submit(value):
    schema_check(value, 'submit')
    tool_check(value)
    identity_check(value)
    ref = value['request_artifact']
    identity_check(ref)
    require(ref['run_id']==value['run_id'] and ref['role']=='request', 'Request artifact binding mismatch')
    require(ref['job_id'] is None and ref['attempt_id'] is None, 'Request must be staged as a run input')
    if value['run_mode']=='pipeline':
        require(value['rule_profile'] is not None, 'Pipeline needs a rule profile')
        require(ref['evidence_kind']!='ENGINEERING_FIXTURE', 'Fixture cannot become pipeline input')
    return value


def validate_job(value):
    schema_check(value, 'job')
    tool_check(value)
    identity_check(value)
    state, terminal = value['state'], value['state'] in contract()['terminal_states']
    times = {k:timestamp(value[k]) for k in ['created_at','updated_at','started_at','finished_at'] if value[k] is not None}
    require(times['updated_at']>=times['created_at'], 'Timestamp order invalid')
    for name in ['started_at','finished_at']:
        if name in times:
            require(times['created_at']<=times[name]<=times['updated_at'], 'Timestamp order invalid')
    if 'started_at' in times and 'finished_at' in times:
        require(times['finished_at']>=times['started_at'], 'Timestamp order invalid')
    require(terminal == (value['finished_at'] is not None), 'Terminal timestamp mismatch')
    if terminal:
        require(value['scientific_disposition']!='pending', 'Terminal disposition still pending')
    has_attempt = value['attempt_id'] is not None
    require(has_attempt == (value['execution_identity'] is not None), 'Attempt/execution identity mismatch')
    require(has_attempt == (value['started_at'] is not None), 'Attempt/start time mismatch')
    require((value['lease_epoch']>0) == has_attempt, 'Lease/attempt mismatch')
    if state=='queued':
        require(not has_attempt and value['stop_reason'] is None, 'Queued job has execution or stop intent')
    if state in ['running','stop_requested','reconciling','succeeded','timed_out']:
        require(has_attempt, 'State needs an execution attempt')
    if not terminal:
        require(value['exit_code'] is None and not value['stop_confirmed'], 'Active job claims completion')
        require(value['scientific_disposition']=='pending' and not value['usable_for_pipeline'], 'Active job claims scientific result')
    if state=='running': require(value['stop_reason'] is None, 'Running job has stop intent')
    if state=='stop_requested': require(value['stop_reason'] is not None, 'Missing stop intent')
    if state in ['cancelled','timed_out']:
        reason, code = ('cancel','CANCELLED') if state=='cancelled' else ('timeout','TIMEOUT')
        require(value['stop_reason']==reason and value['stop_confirmed'] and value['error_code']==code, 'Unconfirmed or inconsistent stop')
    else:
        require(not value['stop_confirmed'], 'Unexpected stop confirmation')
    if state in ['succeeded','failed']:
        require(value['stop_reason'] is None, 'Stop intent cannot be replaced by result')
    if state=='succeeded':
        require(value['exit_code']==0 and value['error_code'] is None, 'Success/exit mismatch')
        require(any(a['role']=='result' for a in value['artifacts']), 'Success requires committed result artifact')
    if state=='failed': require(value['error_code'] is not None, 'Failure needs an error code')
    if state!='succeeded':
        require(not value['usable_for_pipeline'], 'Only success can be consumable')
        require(value['scientific_disposition'] not in ['accepted','skipped'], 'Non-success scientific disposition')
    require(value['scientific_disposition']!='review_required' or value['review_required'], 'Review flag missing')
    if value['usable_for_pipeline']:
        require(value['run_mode']=='pipeline' and value['evidence_kind']=='PIPELINE_REAL_OUTPUT'
                and value['scientific_disposition']=='accepted' and not value['review_required']
                and value['rule_profile'] is not None, 'Illegal pipeline consumption claim')
    if value['evidence_kind']=='ENGINEERING_FIXTURE' or value['run_mode']!='pipeline':
        require(not value['usable_for_pipeline'], 'Development evidence promoted to pipeline')
    if value['tool_id']=='t01.real.engineering_probe':
        require(value['evidence_kind']=='ENGINEERING_FIXTURE' and value['scientific_disposition'] in ['pending','not_evaluated'], 'Engineering worker claims science')
    require(value['retry_of_job_id']!=value['job_id'], 'Self retry lineage')
    request = value['request_artifact']
    identity_check(request)
    require(request['run_id']==value['run_id'] and request['role']=='request'
            and request['job_id'] is None and request['attempt_id'] is None, 'Request artifact binding mismatch')
    if value['run_mode']=='pipeline':
        require(request['evidence_kind']!='ENGINEERING_FIXTURE' and value['rule_profile'] is not None, 'Unqualified pipeline request')
    expected_kind = {'engineering_example':'ENGINEERING_FIXTURE','g0_probe':'G0_REAL_OUTPUT','pipeline':'PIPELINE_REAL_OUTPUT'}
    require(value['evidence_kind']==expected_kind[value['run_mode']], 'Run mode/evidence identity mismatch')
    seen = {request['artifact_id']}
    for ref in value['artifacts']:
        identity_check(ref)
        require(ref['artifact_id'] not in seen, 'Duplicate artifact identity')
        seen.add(ref['artifact_id'])
        require((ref['run_id'],ref['job_id'],ref['attempt_id']) == (value['run_id'],value['job_id'],value['attempt_id']), 'Cross-job/attempt artifact')
        require(ref['evidence_kind']==value['evidence_kind'], 'Mixed evidence identity')
    return value


def validate_transition(before, after):
    """Check recorded example snapshots; this is not an execution state machine."""
    validate_job(before)
    validate_job(after)
    require(after['state'] in contract()['transitions'][before['state']], 'Illegal transition')
    fixed = ['run_id','job_id','request_id','tool_id','node_id','run_mode','submission_sha256','request_artifact',
             'execution_profile','rule_profile','retry_of_job_id','created_at','evidence_kind']
    require(all(before[k]==after[k] for k in fixed), 'Immutable job field changed')
    require(after['revision']==before['revision']+1, 'Revision must increase once')
    require(timestamp(after['updated_at'])>=timestamp(before['updated_at']), 'Event time went backwards')
    require(after['lease_epoch']>=before['lease_epoch'], 'Lease epoch went backwards')
    if before['attempt_id'] is not None:
        require(all(before[k]==after[k] for k in ['attempt_id','execution_identity','started_at']), 'Recovery started another attempt')
    elif before['state']=='queued' and after['state'] in ['cancelled','failed']:
        require(after['attempt_id'] is None, 'Queued terminal transition invented execution')
    if before['stop_reason'] is not None:
        require(before['stop_reason']==after['stop_reason'], 'Stop intent lost')


def check_consumption(value):
    """Use only checked-in review registry, never client claims as authorization."""
    validate_job(value)
    row = next(r for r in contract()['tools'] if r['tool_id']==value['tool_id'])
    require(value['usable_for_pipeline'] and row['production_enabled'], 'Production not approved in registry')
    # No scientific profile/qualification catalog has been signed off in this design.
    raise ValueError('No signed scientific tool/rule/environment/input-support approval catalog')


def verify_source_files(root, entries, size_key='bytes'):
    root = root.resolve()
    seen = set()
    for row in entries:
        rel = row['path']
        require(isinstance(rel,str) and ':' not in rel and '\\' not in rel and not rel.startswith('/')
                and '..' not in rel.split('/'), 'Unsafe source path')
        path = (root/rel).resolve()
        require(path.is_relative_to(root) and path not in seen and path!=root, 'Unsafe/duplicate source path')
        seen.add(path)
        raw = path.read_bytes()
        require(len(raw)==row[size_key] and digest(raw)==row['sha256'], 'Source hash mismatch: '+rel)


def verify():
    spec = contract()
    for operation in ['create_run','get','cancel','retry']:
        value = dict(contract_version='0.1.0',operation=operation)
        if operation!='create_run': value['job_id']='t01p1r-job-example'
        if operation!='get': value['idempotency_key']='control-example'
        schema_check(value,'control')
    require(len({r['tool_id'] for r in spec['tools']})==len(spec['tools']), 'Duplicate tool registration')
    for name in ['job','submit']:
        require({r['tool_id'] for r in spec['tools']}==set(read(CONTRACT_ROOT/(name+'.schema.json'))['properties']['tool_id']['enum']), 'Tool schema/registry drift')
    require(not any(r['production_enabled'] for r in spec['tools']), 'Unexpected production qualification')
    transitions = spec['transitions']
    require(set(transitions)==set(read(CONTRACT_ROOT/'job.schema.json')['properties']['state']['enum']), 'State registry drift')
    for state, targets in transitions.items():
        require(len(set(targets))==len(targets) and set(targets)<=set(transitions), 'Invalid transition targets')
        if state in spec['terminal_states']: require(not targets, 'Terminal transition allowed')
    sources = read(CONTRACT_ROOT/'source_manifest.json')['sources']
    verify_source_files(ROOT,sources)
    acceptance = read(CONTRACT_ROOT/'acceptance.json')
    cases = acceptance['runtime_cases']+acceptance['scientific_cases']
    require(len({c['id'] for c in cases})==len(cases), 'Duplicate acceptance case')
    require(all(c['execution_status']=='DECLARED_NOT_RUN' for c in cases), 'Design cases mistaken for execution')
    submission_path = CONTRACT_ROOT/acceptance['submit_example']
    submission = validate_submit(read(submission_path))
    for name in acceptance['job_examples']:
        value = validate_job(read(CONTRACT_ROOT/name))
        require(value['submission_sha256']==digest(submission_path.read_bytes()), 'Submission hash drift')
        require(all(value[k]==submission[k] for k in ['run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile']), 'Example request/job mismatch')
    verify_source_files(CONTRACT_ROOT,acceptance['local_example_files'],'size_bytes')
    return dict(status='PASS',scope='STATIC_CONTRACT_ONLY',expert_sources=sum(r['kind']=='EXPERT_ORIGINAL' for r in sources),
        source_files=len(sources),job_examples=len(acceptance['job_examples']),submit_examples=1,control_examples=4,
        runtime_cases_declared=len(acceptance['runtime_cases']),scientific_cases_declared=len(acceptance['scientific_cases']),
        runtime_execution='NOT_RUN',scientific_execution='NOT_RUN',production_status='NOT_DEPLOYED')


if __name__=='__main__':
    print(json.dumps(verify(),ensure_ascii=False))
