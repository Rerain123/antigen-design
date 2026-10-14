"""Inspect published data byte-for-byte; no model inference or production topology adapter."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import re

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
AA20 = frozenset('ACDEFGHIKLMNPQRSTVWY')
LABELS = frozenset('SOMIPB')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def records(text, width):
    """Width must be explicitly specified: annotation 3-line and crossval 4-line differ."""
    if width not in (3, 4):
        raise ValueError('Unsupported record width')
    lines = text.splitlines()
    if not lines or len(lines) % width or any(not line for line in lines):
        raise ValueError('Empty, blank or truncated record')
    result = []
    seen = set()
    for offset in range(0, len(lines), width):
        block = lines[offset:offset+width]
        if not block[0].startswith('>') or not block[0][1:].strip():
            raise ValueError(f'Missing record header at line {offset+1}')
        identifier = block[0][1:].split('|')[0]
        if identifier in seen:
            raise ValueError('Duplicate sequence ID: '+identifier)
        seen.add(identifier)
        sequence = block[1]
        if not re.fullmatch('[A-Z]+', sequence):
            raise ValueError('Invalid source sequence syntax: '+identifier)
        for labels in block[2:]:
            inspect_labels(sequence, labels)
        result.append({'id':identifier, 'header':block[0], 'sequence':sequence,
                       'label_rows':block[2:], 'line':offset+1})
    return result


def inspect_labels(sequence, labels):
    if not sequence or len(sequence) != len(labels):
        raise ValueError('Sequence/label length mismatch or empty input')
    unknown = sorted(set(labels)-LABELS)
    if unknown:
        raise ValueError('Unknown raw labels: '+''.join(unknown))
    segments = []
    for pos, label in enumerate(labels, 1):
        if segments and segments[-1]['raw_label'] == label:
            segments[-1]['end'] = pos
        else:
            segments.append({'raw_label':label, 'start':pos, 'end':pos})
    return {'length':len(sequence), 'counts':dict(sorted(Counter(labels).items())),
            'segments':segments, 'tm_segment_count':sum(s['raw_label']=='M' for s in segments),
            'outside_length':labels.count('O'), 'has_signal':'S' in labels,
            'outside_delivery_domain':bool(set(labels)&set('PB')),
            'raw_labels_sha256':sha(labels.encode()),
            'input_outside_current_web_alphabet':sorted(set(sequence)-AA20)}


def official_fasta(text):
    blocks = re.findall(r'<pre[^>]*>(.*?)</pre>', text, re.S|re.I)
    candidates = [html.unescape(block).strip() for block in blocks if html.unescape(block).strip().startswith('>')]
    if len(candidates) != 1:
        raise ValueError('Cannot uniquely locate official FASTA example block')
    result = []
    for line in candidates[0].splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('>'):
            result.append({'header':line, 'sequence':''})
        elif not result or set(line)-AA20:
            raise ValueError('Unsupported official example sequence')
        else:
            result[-1]['sequence'] += line
    if not result or any(not row['sequence'] for row in result):
        raise ValueError('Empty example')
    return result


def corpus_summary(rows):
    return {'record_count':len(rows), 'residue_count':sum(len(r['sequence']) for r in rows),
            'label_histograms':[dict(sorted(Counter(''.join(r['label_rows'][i] for r in rows)).items()))
                                for i in range(len(rows[0]['label_rows']))],
            'non_aa20_records':[r['id'] for r in rows if set(r['sequence'])-AA20],
            'lengths_and_six_label_domain':'PASS'}


def build(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        raise ValueError('Use a new output directory within the project')
    sources = BATCH/'public_sources'
    annotated = records((sources/'DeepTMHMM.3line').read_text(), 3)
    crossval = records((sources/'DeepTMHMM.crossval.top').read_text(), 4)
    official = official_fasta((sources/'dtu-fasta-example.html').read_text())
    truth = {r['id']:r for r in annotated}
    output.mkdir(parents=True)
    inputs = output/'inputs'
    inputs.mkdir()
    inputs.joinpath('dtu-official-examples.fasta').write_text(
        ''.join(r['header']+'\n'+r['sequence']+'\n' for r in official), encoding='utf-8')
    input_rows = [{'source':'DTU_OFFICIAL_EXAMPLE_NO_EXPECTED_LABELS', 'id':r['header'][1:].split()[0],
                   'length':len(r['sequence']), 'sequence_sha256':sha(r['sequence'].encode())} for r in official]
    # Select short, published annotation examples for coverage, not as model accuracy acceptance.
    predicates = {
        'inside':lambda a:set(a['counts'])=={'I'},
        'signal':lambda a:a['has_signal'] and not a['outside_delivery_domain'],
        'single_tm_large_outside':lambda a:a['tm_segment_count']==1 and a['outside_length']>50 and not a['outside_delivery_domain'],
        'beta_periplasm':lambda a:'P' in a['counts'] and 'B' in a['counts'],
    }
    selected = []
    eligible = sorted((r for r in annotated if not set(r['sequence'])-AA20), key=lambda r:(len(r['sequence']),r['id']))
    for case, predicate in predicates.items():
        row = next(r for r in eligible if predicate(inspect_labels(r['sequence'],r['label_rows'][0])))
        source_bytes = (sources/'DeepTMHMM.3line').read_bytes().splitlines(keepends=True)
        raw = b''.join(source_bytes[row['line']-1:row['line']+2])
        (inputs/(case+'.3line')).write_bytes(raw)
        (inputs/(case+'.fasta')).write_text(row['header']+'\n'+row['sequence']+'\n')
        selected.append({'case':case, 'id':row['id'], 'source_line':row['line'],
                         'evidence_kind':'PUBLISHED_ANNOTATION_NOT_LOCAL_PREDICTION',
                         'raw_block_sha256':sha(raw),
                         'inspection':inspect_labels(row['sequence'],row['label_rows'][0])})
    # The two label rows are intentionally kept distinct until their column semantics are verified.
    cross_comparison = {
        'sequence_mismatch_ids':[r['id'] for r in crossval if truth[r['id']]['sequence']!=r['sequence']],
        'label_row_1_differs_from_3line_ids':[r['id'] for r in crossval if truth[r['id']]['label_rows'][0]!=r['label_rows'][0]],
        'label_row_2_equal_3line_count':sum(truth[r['id']]['label_rows'][0]==r['label_rows'][1] for r in crossval),
        'missing_from_crossval_ids':sorted(set(truth)-{r['id'] for r in crossval}),
        'interpretation':'ROW_ROLES_NOT_INDEPENDENTLY_CONFIRMED; not a 1.0.57 execution or accuracy reference',
    }
    result = {'scope':'PUBLIC_SOURCE_FORMAT_AUDIT', 'model_execution':'NOT_RUN', 'production_status':'NOT_DEPLOYED',
              'annotation':corpus_summary(annotated), 'crossval':corpus_summary(crossval),
              'cross_source_comparison':cross_comparison, 'official_inputs':input_rows,
              'selected_annotation_cases':selected,
              'limitations':['Published data are not held-out acceptance data for a newly installed model.',
                             'X occurs in historical data; current official web alphabet lists AA20. Offline support is untested.',
                             'No local prediction, 1.0.57 region table, score CSV, default-parameter or resource validation.']}
    (output/'audit.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'annotation_records':len(annotated),'crossval_records':len(crossval),
                      'official_examples':len(official),'selected_cases':len(selected),'model_execution':'NOT_RUN'}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    build(parser.parse_args().output_dir)
