"""Development evidence validation only; never publishes consumable scientific results."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT/'discovery/t01-phase1-real/w1/deeptmhmm-academic-boundaries-20260906'
OLD = ROOT/'discovery/t01-phase1-real/w1/deeptmhmm-academic-20260905'
REVIEW = ROOT/'discovery/t01-phase1-real/w1/b2-review-20260906'
IMAGE = 'sha256:7f85781fadf8c89ddbafced691d05006caf6881b06aa5b9bae4bd531393bcd72'
SOURCES = ['scripts/b2_boundary_probe.py', 'scripts/b2_boundary_evidence.py',
           'scripts/run_b2_boundaries.py', 'scripts/check_b2_boundaries.py', 'tests/test_b2_boundaries.py']


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def fingerprint(path, base=ROOT):
    return dict(path=path.relative_to(base).as_posix(), sha256=digest(path), size_bytes=path.stat().st_size)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def load_old(name):
    spec = importlib.util.spec_from_file_location('b2_boundaries_old_'+name, OLD/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(folder):
    return [fingerprint(p, folder) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]


def verify_files(folder, entries, exact=False):
    seen = set()
    for entry in entries:
        name = entry['path']
        require(':' not in name and '\\' not in name and all(x not in ('', '.', '..') for x in name.split('/')), 'UNSAFE_ARTIFACT_PATH')
        p = (folder/name).resolve()
        require(p.is_relative_to(folder.resolve()) and name not in seen, 'UNSAFE_OR_DUPLICATE_ARTIFACT')
        seen.add(name)
        require(p.is_file() and fingerprint(p, folder.resolve()) == entry, 'ARTIFACT_HASH_OR_PRESENCE_MISMATCH: '+name)
    if exact:
        require({p['path'] for p in inventory(folder)} == seen, 'UNDECLARED_ARTIFACT')


def safe_id(sequence):
    return 't01seq_'+hashlib.sha256(sequence.encode()).hexdigest()


def validate_trace(events, sequence):
    tokenized = [e for e in events if e['event']=='tokenized']
    chunks = [e for e in events if e['event']=='chunk_completed']
    embeddings = [e for e in events if e['event']=='embedding_completed']
    require(len(tokenized)==len(embeddings)==1 and chunks, 'MISSING_TOKEN_OR_EMBEDDING_OBSERVATION')
    token = tokenized[0]
    require(token['sequence']==token['input_string']==sequence and token['sequence_sha256']==hashlib.sha256(sequence.encode()).hexdigest(), 'TOKEN_INPUT_MISMATCH')
    require(token['token_count']==len(token['token_ids'])==len(token['decoded_tokens']), 'TOKEN_COUNT_MISMATCH')
    left, right = int(token['prepend_bos']), len(token['decoded_tokens'])-int(token['append_eos'])
    require(''.join(token['decoded_tokens'][left:right])==sequence, 'TOKEN_RECONSTRUCTION_MISMATCH')
    require(token['decoded_tokens'][0]=='<cls>' and token['decoded_tokens'][-1]=='<eos>'
            and token['prepend_bos'] and token['append_eos'], 'UNEXPECTED_PINNED_ALPHABET_SPECIAL_TOKENS')
    reconstructed = []
    cursor = 0
    for chunk in chunks:
        require(chunk['start']==cursor, 'CHUNK_POSITION_GAP_OR_OVERLAP')
        ids = chunk['token_ids']
        require(ids and ids==token['token_ids'][cursor:chunk['requested_end']], 'CHUNK_TOKEN_MISMATCH')
        require(chunk['representation_shape']==[1,len(ids),1280] and chunk['finite'], 'INVALID_CHUNK_REPRESENTATION')
        reconstructed.extend(ids)
        cursor += len(ids)
    require(reconstructed==token['token_ids'], 'INCOMPLETE_TOKEN_COVERAGE')
    require(embeddings[0]['shape']==[len(sequence),1280] and embeddings[0]['finite'], 'INVALID_EMBEDDING_SHAPE_OR_VALUES')
    return dict(amino_acids=len(sequence), token_count=token['token_count'],
        chunk_token_counts=[len(c['token_ids']) for c in chunks],
        chunk_ranges_0based_half_open=[[c['start'],c['start']+len(c['token_ids'])] for c in chunks],
        exact_token_reconstruction=True, embedding_shape=embeddings[0]['shape'])


def check_complete_output(output, sequence, identifier):
    audit = load_old('audit_raw')
    require(identifier==safe_id(sequence), 'UNSAFE_OR_NONBINDING_ID')
    result = output/'result'
    required = ['predicted_topologies.3line', 'TMRs.gff3', 'deeptmhmm_results.md', 'plot.png',
                'probabilities/'+identifier+'_probs.csv', 'embeddings/'+hashlib.md5(sequence.encode()).hexdigest()]
    for relative in required:
        require((result/relative).is_file() and (result/relative).stat().st_size>0, 'MISSING_REQUIRED_OUTPUT: '+relative)
    require(sorted(p.name for p in (result/'probabilities').iterdir())==[identifier+'_probs.csv'], 'PROBABILITY_FILENAME_MISMATCH')
    records = audit.three_line((result/'predicted_topologies.3line').read_text(), {identifier:sequence})
    audit.region_table((result/'TMRs.gff3').read_text(), records)
    record = records[identifier]
    labels = record['labels']
    expected_type = 'BETA' if 'B' in labels else 'SP+TM' if 'S' in labels and 'M' in labels else 'TM' if 'M' in labels else 'SP' if 'S' in labels else 'GLOB'
    require(record['type']==expected_type, 'TYPE_LABEL_MISMATCH')
    probability = audit.probability_table((result/'probabilities'/(identifier+'_probs.csv')).read_text(), identifier, sequence)
    require((result/'plot.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n'), 'INVALID_PLOT_SIGNATURE')
    report = (result/'deeptmhmm_results.md').read_text()
    require(identifier in report, 'REPORT_ID_MISMATCH')
    return dict(raw_record=record, probability=probability, required_outputs=required)


def assess_bundle(folder, sequence, identifier):
    """A malformed bundle yields diagnostics and null, even if a stale topology exists."""
    disposition = dict(topology=None, usable_for_pipeline=False, automatic_handoff=False,
        requires_review=True, scientific_signoff=None, production_status='NOT_DEPLOYED')
    try:
        execution = read(folder/'execution.json')
        require(execution['container_exit_code']==0 and execution['stopped_confirmed']
            and not execution['timed_out'] and not execution['oom_killed'], 'EXECUTION_FAILED_OR_NOT_STOPPED')
        require(execution['input_sha256']==digest(folder/'input.fasta'), 'EXECUTION_INPUT_HASH_MISMATCH')
        require((folder/'input.fasta').read_text()=='>'+identifier+'\n'+sequence+'\n', 'INPUT_ID_OR_SEQUENCE_MISMATCH')
        output = folder/'output'
        verify_files(output, execution['artifacts'], exact=True)
        runtime = read(output/'runtime.json')
        require(runtime['python_exit_code']==0 and not runtime['cuda_available']
            and runtime['network_interfaces']==[[1,'lo']], 'RUNTIME_FAILURE_OR_OFFLINE_EVIDENCE_MISMATCH')
        require(runtime['packages']==read(OLD/'method_summary.json')['runtime_packages'], 'PACKAGE_VERSION_MISMATCH')
        raw = check_complete_output(output, sequence, identifier)
        trace = validate_trace([json.loads(line) for line in (output/'token_trace.jsonl').read_text().splitlines()], sequence)
        return dict(status='COMPLETE_RAW_ONLY', diagnostics=[], trace=trace, **raw, **disposition)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        return dict(status='REJECTED', raw_record=None, diagnostics=[dict(type=type(exc).__name__, message=str(exc))], **disposition)
