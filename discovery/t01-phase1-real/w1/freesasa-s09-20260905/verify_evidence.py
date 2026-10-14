"""Read-only provenance, identity and numerical-sanity checks for this fixed batch."""
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(condition, message):
    if not condition:
        raise ValueError(message)


def verify():
    campaign = read(BATCH/'campaign_result.json')
    checked = 0
    for item in campaign['input_and_program_files'] + [a for c in campaign['cases'] for a in c['artifacts']]:
        data = (BATCH/item['path']).read_bytes()
        check(len(data) == item['size_bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], item['path'])
        checked += 1
    supplement = read(BATCH/'supplement_manifest.json')
    for item in supplement['files']:
        base = BATCH if item['scope'] == 'batch' else ROOT
        data = (base/item['path']).read_bytes()
        check(len(data) == item['size_bytes'] and hashlib.sha256(data).hexdigest() == item['sha256'], item['path'])
    for item in read(BATCH/'inputs/SOURCE_MANIFEST.json')['files']:
        if 'source_path' in item:
            check((ROOT/item['source_path']).read_bytes() == (BATCH/'inputs'/item['path']).read_bytes(), 'Source changed')
    a = read(BATCH/'runs/converted-pdb/result/raw.json')
    repeat = read(BATCH/'runs/converted-pdb-repeat/result/raw.json')
    bridge = read(BATCH/'runs/biopython-mmcif/result/raw.json')
    check(a == repeat, 'Repeated native output drift')
    check((BATCH/'runs/converted-pdb/result/raw.json').read_bytes() == (BATCH/'runs/converted-pdb-repeat/result/raw.json').read_bytes(), 'Repeated raw bytes drift')
    check(a['atom_count'] == 602 and a['residue_count'] == 76, 'Unexpected raw coverage')
    for data in (a, repeat, bridge):
        check(all(data['engineering_checks'].values()), 'Numerical sanity failure')
    mapping = read(BATCH/'inputs/mapping.json')
    expected = [(e['structure_residue']['chain_id'], str(e['structure_residue']['res_seq']) + e['structure_residue']['insertion_code'],
                 e['structure_residue']['residue_name']) for e in mapping['entries']]
    for data in (a, bridge):
        actual = [(r['chain'], r['residue_number'], r['residue_name']) for r in data['residues']]
        check(expected == actual, 'Native residue identity differs from candidate mapping')
    check(mapping['mapping_status'] == 'unverified', 'Probe must not approve the mapping')
    for case in campaign['cases']:
        check(case['command'][case['command'].index('--network') + 1] == 'none', 'Network isolation flag missing')
        env = read(BATCH/'runs'/case['case_id']/'result/environment.json')
        check(env['network_interfaces'] == ['lo'], 'Non-loopback interface')
    follow = read(BATCH/'followup/inspection.json')
    for key in ('synthetic_icode_native', 'synthetic_icode_bridge'):
        data = follow[key]
        check(['A', '42'] in data['unique_residue_addresses'] and ['A', '42A'] in data['unique_residue_addresses'], 'Insertion identity lost')
        check(len(data['unique_residue_addresses']) == 76 and not data['nonfinite_absolute_atom_indices'], 'Synthetic renumbering failure')
    for key in ('old_toy_native', 'old_toy_bridge'):
        check(follow[key]['total_sasa_a2'] == {'raw_nonfinite_token': 'nan'}, 'Nonfinite raw evidence changed')
    catalog = read(ROOT/'docs/project/phase1/PHASE1_REAL_W1_S09_CASES.json')
    for source in catalog['sources'].values():
        check(hashlib.sha256((ROOT/source['path']).read_bytes()).hexdigest() == source['sha256'], 'S-09 source drift')
    check(len({c['case_id'] for c in catalog['cases']}) == len(catalog['cases']), 'Duplicate S-09 cases')
    pending = [c for c in catalog['cases'] if c['kind'] == 'DECISION_REQUIRED']
    check(len(pending) == 6 and all(c['expected_fields']['confidence'] is None and c['expected_fields']['s11_quality_condition'] is None for c in pending), 'Pending decisions received fabricated expectations')
    check(all(c['execution_status'] == 'NOT_RUN' for c in catalog['cases']), 'S-09 draft claims execution')
    return {'status': 'PASS', 'scope': 'FIXED_BATCH_PROVENANCE_RAW_IDENTITY_AND_DRAFT_CATALOG_ONLY',
            'campaign_file_hashes_checked': checked, 'supplement_file_hashes_checked': len(supplement['files']), 'native_repeat_equal': True,
            'native_residue_identity_matches_unverified_mapping': True,
            'bridge_total_sasa_absolute_difference_a2': abs(a['total_sasa_a2'] - bridge['total_sasa_a2']),
            'bridge_comparison': 'OBSERVED_DIFFERENCE_NOT_SCIENTIFIC_TOLERANCE_PASS',
            'insertion_code_native_and_bridge_preserved': True, 'synthetic_toy_nan_preserved': True,
            's09_source_derived_cases': 27, 's09_pending_cases': 6, 's09_execution': 'NOT_RUN',
            'scientific_acceptance': 'NOT_RUN', 'production_status': 'NOT_DEPLOYED'}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
