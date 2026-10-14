"""Validate Academic 1.0 raw records; this is evidence analysis, not a production adapter."""
import json
import math
from pathlib import Path
import re

BATCH = Path(__file__).resolve().parent
LABELS = {'I': 'inside', 'O': 'outside', 'M': 'TMhelix', 'S': 'signal', 'P': 'periplasm', 'B': 'Beta sheet'}
AA20 = set('ACDEFGHIKLMNPQRSTVWY')


def require(value, message):
    if not value:
        raise ValueError(message)


def fasta(text):
    result = {}
    identifier = None
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith('>'):
            require(bool(line[1:].strip()), 'Missing FASTA identifier')
            identifier = line[1:].split()[0]
            require(identifier not in result, 'Duplicate FASTA identifier')
            result[identifier] = ''
        else:
            require(identifier is not None, 'Sequence before FASTA header')
            require(line == line.strip() and not any(c.isspace() for c in line), 'Whitespace in sequence')
            result[identifier] += line
    require(result and all(result.values()), 'Empty FASTA sequence')
    return result


def segments(labels):
    require(labels and set(labels) <= set(LABELS), 'Unknown or empty labels')
    result = []
    for position, label in enumerate(labels, 1):
        if not result or label != result[-1]['label']:
            result.append(dict(label=label, type=LABELS[label], start=position, end=position))
        else:
            result[-1]['end'] = position
    return result


def three_line(text, inputs):
    lines = text.splitlines()
    require(lines and len(lines) % 3 == 0, 'Truncated or empty three-line output')
    result = {}
    for index in range(0, len(lines), 3):
        header, sequence, labels = lines[index:index+3]
        match = re.fullmatch(r'>(\S+) \| (TM|SP\+TM|SP|GLOB|BETA)', header)
        require(match, 'Malformed output header/type')
        identifier, kind = match.groups()
        require(identifier not in result, 'Duplicate output identifier')
        require(identifier in inputs and sequence == inputs[identifier], 'Input/output sequence or ID mismatch')
        require(len(sequence) == len(labels), 'Label length mismatch')
        result[identifier] = dict(sequence=sequence, labels=labels, type=kind, segments=segments(labels))
    require(set(result) == set(inputs), 'Missing input record in output')
    return result


def region_table(text, predictions):
    lines = text.splitlines()
    require(lines and lines[0] == '##gff-version 3', 'Missing region table header')
    rows = {identifier: [] for identifier in predictions}
    lengths, counts = {}, {}
    for line in lines[1:]:
        if line == '//':
            continue
        if line.startswith('# '):
            match = re.fullmatch(r'# (\S+) (Length|Number of predicted TMRs): (\d+)', line)
            require(match, 'Unknown region metadata')
            identifier, field, number = match.groups()
            require(identifier in predictions, 'Unknown metadata ID')
            target = lengths if field == 'Length' else counts
            require(identifier not in target, 'Duplicate region metadata')
            target[identifier] = int(number)
            continue
        # The package emits four meaningful columns plus four empty trailing cells.
        fields = line.split('\t')
        require(len(fields) == 8 and fields[4:] == ['', '', '', ''], 'Unexpected Academic 1.0 region columns')
        identifier, kind, start, end = fields[:4]
        require(identifier in predictions and kind in LABELS.values(), 'Unknown region ID/type')
        require(start.isdigit() and end.isdigit(), 'Noninteger region coordinates')
        rows[identifier].append(dict(type=kind, start=int(start), end=int(end)))
    require(set(lengths) == set(predictions) == set(counts), 'Missing region metadata')
    for identifier, prediction in predictions.items():
        expected = [{k: s[k] for k in ('type', 'start', 'end')} for s in prediction['segments']]
        require(rows[identifier] == expected, 'Region/label disagreement: '+identifier)
        require(lengths[identifier] == len(prediction['sequence']), 'Region length mismatch')
        require(counts[identifier] == sum(s['label'] in 'MB' for s in prediction['segments']), 'Raw TMR count mismatch')
    return counts


def probability_table(text, identifier, sequence):
    lines = text.splitlines()
    require(len(lines) == len(sequence)+2, 'Probability row count mismatch')
    require(lines[:2] == ['# '+identifier, '#AA,Beta,Periplasm,Membrane,Inside,Outside,Signal'], 'Probability header mismatch')
    mass_deviations = []
    for index, (aa, line) in enumerate(zip(sequence, lines[2:])):
        fields = line.split(',')
        require(len(fields) == 7 and fields[0] == f'{index} {aa}', 'Probability position/AA mismatch')
        values = [float(value) for value in fields[1:]]
        require(all(math.isfinite(value) and 0 <= value <= 1 for value in values), 'Invalid probability value')
        mass_deviations.append(abs(sum(values)-1))
    return dict(rows=len(sequence), position_base=0, max_probability_mass_deviation=max(mass_deviations),
                mass_tolerance='NOT_A_SCIENTIFIC_ACCEPTANCE_THRESHOLD')


def audit_case(case):
    folder = BATCH/'runs'/case
    execution = json.loads((folder/'execution.json').read_text())
    runtime = json.loads((folder/'output/runtime.json').read_text())
    inspect = json.loads((folder/'container_inspect.json').read_text())[0]
    require(execution['container_exit_code'] == 0 and not execution['oom_killed'] and not execution.get('timed_out'), 'Execution failed')
    require(runtime['python_exit_code'] == 0 and not runtime['cuda_available'], 'Not a successful CPU run')
    require(runtime['network_interfaces'] == [[1, 'lo']] and inspect['HostConfig']['NetworkMode'] == 'none', 'Offline evidence missing')
    inputs = fasta((BATCH/'inputs'/f'{case}.fasta').read_text())
    output = folder/'output/result'
    records = three_line((output/'predicted_topologies.3line').read_text(), inputs)
    tmrs = region_table((output/'TMRs.gff3').read_text(), records)
    for identifier, record in records.items():
        record['raw_tmr_count'] = tmrs[identifier]
        record['alpha_tm_segment_count'] = sum(s['label'] == 'M' for s in record['segments'])
        record['outside_length'] = record['labels'].count('O')
        record['has_signal'] = 'S' in record['labels']
        record['input_outside_aa20'] = sorted(set(record['sequence'])-AA20)
        record['requires_pb_guard'] = bool(set(record['labels']) & set('PB'))
        if record['requires_pb_guard']:
            record['required_project_guard'] = dict(topology=None, status='unreliable', failure_level='WARNING', automatic_handoff=False)
    csvs = sorted((output/'probabilities').glob('*.csv'))
    probability = None
    if len(inputs) == 1:
        require(len(csvs) == 1 and (output/'plot.png').is_file(), 'Missing single-sequence outputs')
        identifier, sequence = next(iter(inputs.items()))
        probability = probability_table(csvs[0].read_text(), identifier, sequence)
        probability['host_filename'] = csvs[0].name
    else:
        require(not csvs and not (output/'plot.png').exists(), 'Unexpected batch probability outputs')
    return dict(case=case, record_count=len(records), records=records, probability=probability,
                execution_seconds=execution['elapsed_seconds'], peak_rss_kib=runtime['peak_rss_kib'])


def audit():
    cases = [audit_case(case) for case in ('short', 'coverage', 'x-residue')]
    empty = BATCH/'runs/empty'
    execution = json.loads((empty/'execution.json').read_text())
    require(execution['container_exit_code'] == 1 and not execution['oom_killed'], 'Wrong empty-input failure')
    stdout = (empty/'stdout.txt').read_text()
    require('No sequences found in FASTA input' in stdout and 'Step 1/4' not in stdout, 'Empty input was not rejected before model loading')
    require(not (empty/'output/result/predicted_topologies.3line').exists(), 'Invalid input produced topology')
    short = cases[0]['records']
    repeated = {key: cases[1]['records'][key] for key in short}
    require(short == repeated, 'Single/batch topology changed for repeated input')
    return dict(status='PASS', model_execution='EXECUTED_OFFLINE_CPU', production_status='NOT_DEPLOYED',
                scientific_accuracy='NOT_EVALUATED', cases=cases, repeated_short_topology_equal=True,
                empty_input='REJECTED_BEFORE_MODEL_LOADING', guard_scope='EVIDENCE_PROJECTION_ONLY; production/downstream not implemented')


if __name__ == '__main__':
    target = BATCH/'raw_audit.json'
    require(not target.exists(), 'Preserve existing audit')
    result = audit()
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))
