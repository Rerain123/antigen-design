"""Audit a terminal AF3-first workflow directly from retained runtime evidence.

This read-only audit does not call ``workflow.report`` and therefore does not
publish or download a public report.  It verifies AF3 native/standard evidence,
the conservative N01/S-09 structure outcome, same-run bindings and the N18
engineering branch result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
K = [
    'C:/Program Files/Docker/Docker/resources/bin/kubectl.exe',
    '--kubeconfig', str(ROOT / '.tmp/himat.kubeconfig'),
    '--request-timeout=90s', '-n', 'him-ws',
]
SUCCEEDED = {
    'prediction', 'structure', 'topology', 'bepipred', 'netmhc',
    'epitope_map', 'glycosylation', 'developability', 'wt_draft',
    'variant_report', 'wt_reference', 'local_delivery',
}
SKIPPED = {
    'blast': 'DATABASE_NOT_PROVIDED',
    'homology': 'DATABASE_NOT_PROVIDED',
    'domains': 'DATABASE_NOT_PROVIDED',
    'design': 'SCIENTIFIC_GATE_CLOSED',
    'rescore': 'SCIENTIFIC_GATE_CLOSED',
    'protection': 'SCIENTIFIC_GATE_CLOSED',
    'stability': 'SCIENTIFIC_GATE_CLOSED',
    'codon': 'NO_ELIGIBLE_SEQUENCE',
}


def remote_payload(parent_job_id: str) -> str:
    return f'''import json
import sqlite3
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import ensure
from t01_phase1_real.development import Runtime

PARENT = {parent_job_id!r}
SUCCEEDED = {sorted(SUCCEEDED)!r}
SKIPPED = {SKIPPED!r}
root = Path('/var/lib/t01/runtime')
database = sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro', uri=True)
row = database.execute('select scope from jobs where id=?', (PARENT,)).fetchone()
ensure(row is not None, 'INVALID_REQUEST', 'Unknown AF3 workflow parent')
rt = Runtime(root, scope=row[0])
parent = rt.get(PARENT)
view = rt.workflow(PARENT)
ensure(parent['state'] == 'succeeded' and parent['error_code'] is None,
       'INVALID_STATE', 'AF3 workflow is not a successful terminal task')
run_id = parent['run_id']
nodes = view['nodes']
ensure(set(nodes) == set(SUCCEEDED) | set(SKIPPED),
       'OUTPUT_INVALID', 'Workflow node set differs')
verified_artifacts = 0
for name, node in nodes.items():
    if name in SUCCEEDED:
        ensure(node['state'] == 'succeeded' and node['origin'] == 'NEW_EXECUTION'
               and node['request_artifact']['run_id'] == run_id,
               'OUTPUT_INVALID', 'Successful workflow node identity differs: ' + name)
        for ref in node['artifacts']:
            raw = rt.artifact_bytes(node['job_id'], ref['artifact_id'])
            ensure(len(raw) == ref['size_bytes'], 'HASH_MISMATCH', 'Artifact size differs')
            ensure(ref['run_id'] == run_id and ref['job_id'] == node['job_id'],
                   'OUTPUT_INVALID', 'Artifact escaped workflow run')
            verified_artifacts += 1
    else:
        ensure(node['state'] == 'skipped' and node['reason_code'] == SKIPPED[name]
               and node.get('job_id') is None,
               'OUTPUT_INVALID', 'Expected skipped workflow branch differs: ' + name)

prediction_job = rt.get(nodes['prediction']['job_id'])
prediction = rt.result(prediction_job['job_id'])
p = prediction['prediction']
models = p['models']
ensure(prediction_job['state'] == 'succeeded'
       and prediction['status'] == 'predicted_engineering_unreviewed'
       and p['status'] == 'succeeded'
       and p['engine'] == 'alphafold3' and len(models) == 5,
       'OUTPUT_INVALID', 'AF3 standard result identity/count differs')
ensure([row['sample_index'] for row in models] == list(range(5))
       and {{row['seed'] for row in models}} == {{1}}
       and all(row['format'] == 'mmcif' and row['source'] == 'af3_predicted' for row in models),
       'OUTPUT_INVALID', 'AF3 native sample coverage differs')
highest = max(row['ptm'] for row in models)
tied = [row for row in models if row['ptm'] == highest]
selected = [row for row in models if row['selected']]
ensure(len(selected) == 1 and selected[0] == min(tied, key=lambda row: (row['seed'], row['sample_index']))
       and p['selection']['highest_ptm'] == highest
       and p['selection']['tied_model_ids'] == [row['model_id'] for row in tied]
       and p['selection']['official_ranking_score_used'] is False,
       'OUTPUT_INVALID', 'AF3 pTM selection/tie retention differs')
prediction_execution = rt.execution(prediction_job['job_id'])
prediction_receipt = prediction_execution.get('resident_receipt') or {{}}
ensure(prediction_execution.get('backend') == 'resident-process'
       and prediction_receipt.get('state') == 'succeeded'
       and prediction_receipt.get('stopped_confirmed') is True,
       'OUTPUT_INVALID', 'AF3 resident execution is not cleanly stopped')

structure_job = rt.get(nodes['structure']['job_id'])
structure = rt.result(structure_job['job_id'])
analysis = structure['analysis']
ensure(structure['status'] == 'review_required' and analysis is not None,
       'OUTPUT_INVALID', 'N01 structure result is not retained for review')
quality = analysis['quality']
ensure(quality['structure']['source'] == 'af3_predicted'
       and quality['structure']['ptm'] == highest
       and len(quality['structure']['plddt_per_residue']) == len(p['sequence'])
       and quality['s11_quality_condition'] is True,
       'OUTPUT_INVALID', 'AF3 S-09 quality consumption differs')
mapping = analysis['mapping']
ensure(mapping['sequence'] == p['sequence'] and mapping['target_chain_id'] == 'A'
       and len(mapping['entries']) == len(p['sequence']),
       'OUTPUT_INVALID', 'N01 sequence/structure mapping differs')
ensure(analysis['freesasa']['status'] == 'review_required'
       and analysis['freesasa']['error_code'] == 'ICODE_UNKNOWN'
       and analysis['rsa'] is None
       and any(row['code'] == 'ICODE_UNKNOWN' for row in analysis['warnings']),
       'OUTPUT_INVALID', 'Unknown AF3 iCode was not conservatively retained')
structure_execution = rt.execution(structure_job['job_id'])
structure_receipt = structure_execution.get('resident_receipt') or {{}}
ensure(structure_execution.get('backend') == 'resident-process'
       and structure_receipt.get('state') == 'succeeded'
       and structure_receipt.get('stopped_confirmed') is True,
       'OUTPUT_INVALID', 'Structure resident execution is not cleanly stopped')

delivery_job = rt.get(nodes['local_delivery']['job_id'])
delivery = rt.result(delivery_job['job_id'])
ensure(delivery_job['state'] == 'succeeded'
       and delivery['status'] == 'local_delivery_unreviewed'
       and delivery['usable_for_pipeline'] is False
       and delivery['automatic_handoff'] is False,
       'OUTPUT_INVALID', 'N18 delivery qualification differs')

result = {{
    'status': 'AF3_FIRST_N01_N18_ENGINEERING_AUDIT_PASS',
    'parent_job_id': PARENT,
    'run_id': run_id,
    'sequence_sha256': p['sequence_sha256'],
    'branch_counts': {{'succeeded': len(SUCCEEDED), 'skipped': len(SKIPPED), 'failed': 0}},
    'succeeded': sorted(SUCCEEDED),
    'skipped': {{name: SKIPPED[name] for name in sorted(SKIPPED)}},
    'artifact_refs_verified': verified_artifacts,
    'af3': {{
        'job_id': prediction_job['job_id'],
        'resident_execution_id': prediction_receipt.get('execution_id'),
        'native_sample_count': len(models),
        'model_ids': [row['model_id'] for row in models],
        'structure_sha256': [row['structure_sha256'] for row in models],
        'highest_ptm': highest,
        'selected_model_id': selected[0]['model_id'],
        'tied_model_ids': [row['model_id'] for row in tied],
        'official_ranking_score_used': False,
        'database_total_bytes': p['database_receipt']['total_bytes'],
    }},
    'n01_s09': {{
        'job_id': structure_job['job_id'],
        'resident_execution_id': structure_receipt.get('execution_id'),
        'mapping_status': mapping['mapping_status'],
        'mapped_residues': len(mapping['entries']),
        'confidence': quality['quality']['confidence'],
        'mean_plddt': quality['structure']['mean_plddt'],
        'ptm': quality['structure']['ptm'],
        'freesasa_status': analysis['freesasa']['status'],
        'freesasa_reason': analysis['freesasa']['error_code'],
        'rsa': None,
    }},
    'n18': {{'job_id': delivery_job['job_id'], 'status': delivery['status']}},
    'report_publication_called': False,
    'scientific_gate': 'CLOSED',
    'usable_for_pipeline': False,
    'automatic_handoff': False,
    'production_status': 'NOT_DEPLOYED',
}}
print('AF3_WORKFLOW_AUDIT_RESULT ' + json.dumps(result, sort_keys=True))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    batch_dir = ROOT / '.tmp' / ('cluster-workflow-probe-' + args.batch)
    batch = json.loads((batch_dir / 'batch.json').read_bytes())
    parent_job_id = batch.get('job_id')
    if not parent_job_id:
        raise RuntimeError('Batch has no submitted parent job')
    payload = remote_payload(parent_job_id)
    compile(payload, 'af3-workflow-audit-remote', 'exec')
    if args.check:
        print('AF3_WORKFLOW_AUDIT_PAYLOAD_CHECK_PASS')
        return
    completed = subprocess.run(
        K + ['exec', '-i', 'deployment/antigen-design', '-c', 'service', '--',
             'python', '-u', '-B', '-X', 'utf8', '-'],
        input=payload.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=300,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors='replace'))
    marker = 'AF3_WORKFLOW_AUDIT_RESULT '
    line = next((line for line in completed.stdout.decode(errors='replace').splitlines()
                 if line.startswith(marker)), None)
    if line is None:
        raise RuntimeError('Remote AF3 workflow audit returned no result')
    result = json.loads(line[len(marker):])
    output = ROOT / 'discovery/t01-phase1-real/af3-target-20260920' / ('workflow-' + args.batch) / 'audit-summary.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(result['status'])
    print('SAVED', output)


if __name__ == '__main__':
    main()
