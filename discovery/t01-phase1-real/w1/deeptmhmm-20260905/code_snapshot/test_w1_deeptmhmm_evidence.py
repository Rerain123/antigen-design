"""Raw-format/evidence regressions; published annotations and faults are not model inference."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT/'discovery/t01-phase1-real/w1/deeptmhmm-20260905'


def load(filename):
    spec = importlib.util.spec_from_file_location('deeptmhmm_'+filename.stem, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def audit():
    return load(BATCH/'audit_sources.py')


def test_batch_integrity_and_no_fabricated_model_execution():
    result = load(BATCH/'verify_evidence.py').verify()
    assert result['status']=='PASS'
    assert result['expert_sources_unchanged']==22
    assert result['model_execution']=='NOT_RUN'


def test_segment_count_not_residue_count_and_one_based_closed_intervals(audit):
    labels = 'SSOOMMMIIMMO'
    result = audit.inspect_labels('A'*len(labels), labels)
    assert result['tm_segment_count']==2
    assert result['outside_length']==3
    assert result['has_signal'] is True
    assert result['segments']==[
        {'raw_label':'S','start':1,'end':2}, {'raw_label':'O','start':3,'end':4},
        {'raw_label':'M','start':5,'end':7}, {'raw_label':'I','start':8,'end':9},
        {'raw_label':'M','start':10,'end':11}, {'raw_label':'O','start':12,'end':12}]


@pytest.mark.parametrize('labels', ['IPPPO','IBBBO','SPBOI'])
def test_pb_are_preserved_and_marked_outside_delivery_domain(audit, labels):
    result = audit.inspect_labels('A'*len(labels), labels)
    assert result['outside_delivery_domain'] is True
    assert sum(result['counts'].values())==len(labels)
    assert ''.join(s['raw_label']*(s['end']-s['start']+1) for s in result['segments'])==labels


@pytest.mark.parametrize('sequence,labels', [('', ''),('AAA','II'),('AAA','IIIII'),('AAA','IIX'),('AAA','I I')])
def test_malformed_labels_are_rejected(audit, sequence, labels):
    with pytest.raises(ValueError):
        audit.inspect_labels(sequence, labels)


@pytest.mark.parametrize('text,width', [('',3),('>a\nAA\n',3),('a\nAA\nII\n',3),
    ('>a\nAA\nII\n>a\nAA\nII\n',3),('>a\nAA\nII\nOO\n',3)])
def test_record_width_headers_duplicates_and_truncation(audit, text, width):
    with pytest.raises(ValueError):
        audit.records(text, width)


def test_crossval_label_rows_stay_distinct(audit):
    record = audit.records('>a\nAAA\nIII\nOMM\n',4)[0]
    assert record['label_rows']==['III','OMM']


def test_historical_x_is_observed_without_claiming_input_support(audit):
    record = audit.records('>a\nAXA\nIII\n',3)[0]
    assert audit.inspect_labels(record['sequence'],record['label_rows'][0])['input_outside_current_web_alphabet']==['X']


def test_official_inputs_have_no_invented_expected_labels(audit):
    result = audit.official_fasta((BATCH/'public_sources/dtu-fasta-example.html').read_text())
    assert [len(r['sequence']) for r in result]==[991,96,307,375]
    assert all(set(r)=={'header','sequence'} for r in result)


def test_manifest_detects_changed_bytes(tmp_path):
    verifier = load(BATCH/'verify_evidence.py')
    (tmp_path/'raw').write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash mismatch'):
        verifier.verify_files(tmp_path,[{'path':'raw','bytes':7,'sha256':'0'*64}])


def test_manifest_rejects_escape_before_file_read(tmp_path):
    verifier = load(BATCH/'verify_evidence.py')
    with pytest.raises(ValueError, match='Unsafe'):
        verifier.verify_files(tmp_path,[{'path':'../outside','bytes':0,'sha256':'0'*64}])
