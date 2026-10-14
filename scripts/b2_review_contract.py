"""B2 review-only request/result validation and raw replay; never an executing adapter."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator
from check_w1_contract import strict_json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / '工作流设计/02-数据契约/phase1-real-v0.1/b2-review'
ACADEMIC = ROOT / 'discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905'
BATCH = ROOT / 'discovery/t01-phase1-real/w1/b2-review-20260906'
AA20 = set('ACDEFGHIKLMNPQRSTVWY')
LABELS = {'I': 'inside', 'O': 'outside', 'M': 'TMhelix', 'S': 'signal', 'P': 'periplasm', 'B': 'Beta sheet'}
TYPES = {'TM', 'SP+TM', 'SP', 'GLOB', 'BETA'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return strict_json(path.read_bytes())


def load_original(name):
    spec = importlib.util.spec_from_file_location('b2_original_' + name, ACADEMIC / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def input_findings(sequence):
    """Literal transport/input review findings, not an approved model accuracy domain."""
    if not sequence:
        return ['EMPTY_SEQUENCE']
    if sequence != sequence.upper() or any(c.isspace() for c in sequence):
        return ['SEQUENCE_NOT_NORMALIZED']
    if re.fullmatch('[A-Z]+', sequence) is None:
        return ['INVALID_SEQUENCE_SYMBOL']
    findings = ['UPSTREAM_DEFAULT_LENGTH_GUARD'] if len(sequence) < 9 else []
    if set(sequence) - AA20:
        findings.append('NON_AA20_REQUIRES_REVIEW')
    # 991 aa is the largest recorded local input, not a tool maximum or a scientific cutoff.
    if len(sequence) > 991:
        findings.append('LENGTH_BEYOND_RECORDED_SAMPLES')
    return findings


def schema(value, name):
    Draft202012Validator(read(CONTRACT / (name + '.schema.json'))).validate(value)


def validate_request(value):
    schema(value, 'request')
    require(value['protein_sequence_sha256'] == sha(value['protein_sequence'].encode()), 'Sequence hash mismatch')
    require(value['internal_sequence_id'] == 't01seq_' + value['protein_sequence_sha256'], 'Unsafe or nonbinding internal ID')
    require(value['profile_sha256'] == sha((CONTRACT / 'profile.json').read_bytes()), 'Profile hash mismatch')
    return value


def segments(labels):
    require(bool(labels) and set(labels) <= set(LABELS), 'Unknown or empty raw labels')
    result = []
    for position, label in enumerate(labels, 1):
        if result and result[-1]['label'] == label:
            result[-1]['end'] = position
        else:
            result.append(dict(label=label, type=LABELS[label], start=position, end=position))
    return result


def raw_record(identifier, sequence, labels, kind):
    require(len(sequence) == len(labels), 'Raw label length mismatch')
    require(kind in TYPES, 'Unknown raw protein type')
    regions = segments(labels)
    # A class header is diagnostic; a contradictory header must not bypass the label guard.
    # Academic tm_util.get_predicted_type_from_labels uses B, not P, to select BETA.
    expected_type = 'BETA' if 'B' in labels else 'SP+TM' if 'S' in labels and 'M' in labels else 'TM' if 'M' in labels else 'SP' if 'S' in labels else 'GLOB'
    require(kind == expected_type, 'Protein type and labels disagree')
    return dict(record_id=identifier, sequence=sequence, labels=labels, type=kind,
                segments=regions, raw_tmr_count=sum(s['label'] in 'MB' for s in regions), coordinate_base=1)


def disposition(sequence, raw=None, failure=None):
    findings = input_findings(sequence)
    if findings:
        reason = 'INPUT_REVIEW_REQUIRED' if all(f in {'NON_AA20_REQUIRES_REVIEW', 'LENGTH_BEYOND_RECORDED_SAMPLES'} for f in findings) else 'INVALID_INPUT'
    elif failure:
        require(failure in {'TOOL_UNAVAILABLE', 'INVALID_OUTPUT', 'TOOL_FAILED', 'TIMED_OUT', 'CANCELLED'}, 'Unknown failure reason')
        reason = failure
    elif raw is None:
        raise ValueError('Successful interpretation requires complete raw evidence')
    elif set(raw['labels']) & set('PB'):
        reason = 'PB_OUT_OF_DOMAIN'
    else:
        reason = None
    topology = None
    if reason is None:
        topology = dict(labels=[LABELS[c] for c in raw['labels']],
            segments=[{k: s[k] for k in ('type', 'start', 'end')} for s in raw['segments']],
            has_signal='S' in raw['labels'], tm_count=sum(s['label'] == 'M' for s in raw['segments']),
            outside_length=raw['labels'].count('O'))
    warnings = [] if reason is None else [dict(level='failure', severity='WARNING', code=reason,
        message='拓扑预测不可用' if reason == 'TOOL_UNAVAILABLE' else '原始拓扑或输入需复核；不得自动交接')]
    return dict(topology=topology, null_reason=reason, input_findings=findings,
        interpretation_status='parsed_unverified' if reason is None else 'unreliable',
        requires_review=True, automatic_handoff=False, usable_for_pipeline=False, warnings=warnings)


def make_request(name, sequence, user_sequence_id='review input'):
    return dict(contract_version='0.1.0', contract_status='DRAFT_REVIEW_ONLY', tool_id='t01.real.deeptmhmm',
        run_id='t01p1r-run-b2-' + name, request_id='b2-' + name,
        protein_sequence=sequence, protein_sequence_sha256=sha(sequence.encode()), user_sequence_id=user_sequence_id,
        internal_sequence_id='t01seq_' + sha(sequence.encode()), profile_id='t01.deeptmhmm.academic1.cpu.review.v0.1',
        profile_sha256=sha((CONTRACT / 'profile.json').read_bytes()))


def make_result(request, request_bytes, *, raw=None, failure=None, evidence_kind='ENGINEERING_FIXTURE', raw_artifacts=None):
    validate_request(request)
    name = request['request_id']
    result = dict(contract_version='0.1.0', contract_status='DRAFT_REVIEW_ONLY', tool_id=request['tool_id'],
        identity_scope='LOCAL_REVIEW_NOT_RUNTIME_ISSUED', evidence_kind=evidence_kind,
        binding=dict(run_id=request['run_id'], request_id=name, job_id='t01p1r-job-' + name,
            attempt_id='t01p1r-attempt-' + name, request_sha256=sha(request_bytes),
            sequence_sha256=request['protein_sequence_sha256'], profile_sha256=request['profile_sha256']),
        execution_observation='completed' if raw is not None else 'not_started' if failure in (None, 'TOOL_UNAVAILABLE') else 'timed_out' if failure == 'TIMED_OUT' else 'cancelled' if failure == 'CANCELLED' else 'failed',
        failure_reason=failure, raw_record=raw, raw_artifacts=raw_artifacts or [],
        id_pairing='HISTORICAL_ORIGINAL_ID' if evidence_kind == 'G0_RAW_REPLAY' else 'SAFE_INTERNAL_ID',
        scientific_signoff=None, production_status='NOT_DEPLOYED', **disposition(request['protein_sequence'], raw, failure))
    return result


def validate_result(value, request, request_bytes):
    schema(value, 'result')
    validate_request(request)
    require(strict_json(request_bytes) == request, 'Request object differs from exact request bytes')
    binding = value['binding']
    require(binding['run_id'] == request['run_id'] and binding['request_id'] == request['request_id']
        and binding['request_sha256'] == sha(request_bytes) and binding['sequence_sha256'] == request['protein_sequence_sha256']
        and binding['profile_sha256'] == request['profile_sha256'], 'Cross-request/sequence/profile binding')
    raw = value['raw_record']
    if raw is not None:
        require(raw['sequence'] == request['protein_sequence'], 'Raw input sequence mismatch')
        require(raw == raw_record(raw['record_id'], raw['sequence'], raw['labels'], raw['type']), 'Raw topology facts disagree')
        if value['id_pairing'] == 'SAFE_INTERNAL_ID':
            require(raw['record_id'] == request['internal_sequence_id'], 'Raw record ID does not match safe input')
        else:
            require(value['evidence_kind'] == 'G0_RAW_REPLAY' and raw['record_id'] == request['user_sequence_id'], 'Invalid historical ID pairing')
        require(value['failure_reason'] is None and value['execution_observation'] == 'completed', 'Failure/cancel result contains completed topology')
    else:
        expected_execution = 'not_started' if value['failure_reason'] in (None, 'TOOL_UNAVAILABLE') else 'timed_out' if value['failure_reason'] == 'TIMED_OUT' else 'cancelled' if value['failure_reason'] == 'CANCELLED' else 'failed'
        require(value['execution_observation'] == expected_execution, 'Execution observation does not match failure evidence')
    expected = disposition(request['protein_sequence'], raw, value['failure_reason'])
    require(all(value[key] == field for key, field in expected.items()), 'Topology/null/guard/statistics disagreement')
    if value['evidence_kind'] == 'G0_RAW_REPLAY':
        require(value['id_pairing'] == 'HISTORICAL_ORIGINAL_ID' and bool(value['raw_artifacts']), 'Replay must retain original source artifacts')
    else:
        require(value['id_pairing'] == 'SAFE_INTERNAL_ID', 'Fixture cannot claim historical raw identity')
    refs = value['raw_artifacts']
    require(len({ref['path'] for ref in refs}) == len(refs) and len({ref['role'] for ref in refs}) == len(refs), 'Duplicate raw artifact path/role')
    contents = {}
    for ref in refs:
        name = ref['path']
        require(':' not in name and '\\' not in name and all(p not in ('', '.', '..') for p in name.split('/')), 'Unsafe raw artifact path')
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT), 'Raw artifact escaped repository')
        data = path.read_bytes()
        require(sha(data) == ref['sha256'] and len(data) == ref['size_bytes'], 'Raw artifact changed')
        contents[ref['role']] = data
    if value['evidence_kind'] == 'G0_RAW_REPLAY':
        require(set(contents) == {'input_fasta', 'prediction', 'regions', 'execution', 'method_summary'}, 'Incomplete replay source set')
        audit = load_original('audit_raw')
        predictions = audit.three_line(contents['prediction'].decode('utf-8'), audit.fasta(contents['input_fasta'].decode('utf-8')))
        audit.region_table(contents['regions'].decode('utf-8'), predictions)
        require(raw is not None and raw['record_id'] in predictions, 'Missing replay record')
        p = predictions[raw['record_id']]
        require(raw == raw_record(raw['record_id'], p['sequence'], p['labels'], p['type']), 'Replay raw record differs from actual source')
        execution = strict_json(contents['execution'])
        require(execution['container_exit_code'] == 0 and not execution.get('timed_out') and not execution['oom_killed']
                and execution['input_sha256'] == sha(contents['input_fasta']), 'Replayed execution failed or input differs')
        require(contents['method_summary'] == (ACADEMIC / 'method_summary.json').read_bytes(), 'Replay tool identity changed')
    return value


def replay_case(case):
    """Re-read a sealed prior model run; never execute predict.py or modify its files."""
    audit = load_original('audit_raw')
    observed = audit.audit_case(case)
    inputs = audit.fasta((ACADEMIC / 'inputs' / (case + '.fasta')).read_text(encoding='utf-8'))
    out = []
    for identifier, row in observed['records'].items():
        require(inputs[identifier] == row['sequence'], 'Replay input differs')
        out.append(raw_record(identifier, row['sequence'], row['labels'], row['type']))
    return out
