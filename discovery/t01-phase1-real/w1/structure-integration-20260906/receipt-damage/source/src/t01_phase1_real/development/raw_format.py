"""Academic raw format validation derived from audit_raw.py; A5 v10.5 sections 2/3/7."""
import math
import re

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

