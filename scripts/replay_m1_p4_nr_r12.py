"""Read-only replay of r12's archived native BLAST bytes against the current N03 parser."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from t01_phase1_real.development.blast.result import _runtime, parse_hsps


def main():
    folder = ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/r12'
    record = json.loads((folder / 'blast.json').read_bytes())
    receipt = record['execution']['resident_receipt']
    refs = record['job']['artifacts']
    with zipfile.ZipFile(folder / 'native-evidence.zip') as archive:
        assert archive.testzip() is None
        by_hash = {ref['sha256']: archive.read('artifacts/' + ref['artifact_id']) for ref in refs}
    assert all(hashlib.sha256(raw).hexdigest() == digest for digest, raw in by_hash.items())
    runtime = json.loads(by_hash[receipt['outputs']['output/native/runtime.json']['sha256']])
    files = {
        'input.json': by_hash[runtime['input_json_sha256']],
        'input.fasta': by_hash[runtime['input_fasta_sha256']],
        'output/runtime.json': by_hash[receipt['outputs']['output/native/runtime.json']['sha256']],
        'resident/request.json': by_hash[receipt['request_sha256']],
    }
    for digest, raw in by_hash.items():
        if len(raw) > 1000 and raw.startswith(b'{'):
            try:
                candidate = json.loads(raw)
            except ValueError:
                continue
            if isinstance(candidate, dict) and candidate.get('resident_receipt', {}).get('execution_id') == receipt['execution_id']:
                files['resident/execution.json'] = raw
                break
    assert 'resident/execution.json' in files
    for name, info in receipt['outputs'].items():
        mapped = name.replace('output/native/', 'output/', 1) if name.startswith('output/native/') else 'resident/' + name[7:]
        files[mapped] = by_hash[info['sha256']]
    for name, digest in runtime['native_output_sha256'].items():
        files['output/' + name] = by_hash[digest]
    _runtime(files, record['request'])
    hsps = parse_hsps(files['output/blast.txt'], record['request'])
    print(json.dumps({'status': 'P4_R12_NATIVE_REPLAY_PASS', 'raw_hsps': len(hsps),
                      'qualified_hsps': sum(x['passes_registered_thresholds'] for x in hsps),
                      'direct_binary': runtime['commands']['blastp']['argv'][0],
                      'native_blast_sha256': hashlib.sha256(files['output/blast.txt']).hexdigest()}))


if __name__ == '__main__':
    main()
