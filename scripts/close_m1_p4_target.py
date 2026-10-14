"""Consolidate the planned P4/M1 minimum only after all target paths pass."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'discovery/t01-phase1-real/m1-p4-20260922'


def read(path):
    return json.loads(path.read_bytes())


def close(design_batch, wt_batch, failure_batch):
    batches = (design_batch, wt_batch, failure_batch)
    assert len(set(batches)) == 3 and all(re.fullmatch(r'r[0-9]{2,4}', b) for b in batches)
    inspect = read(BASE / 'nr-inspect-r01.json')
    info = read(BASE / 'nr-info-r01.json')
    sizes = read(BASE / 'nr-sizes-r01.json')
    manifest = read(BASE / 'nr-manifest-r01.json')
    full_hash = read(BASE / 'nr-hash-r01.json')
    contract = read(BASE / 'nr-contract-r01.json')
    deployed = read(BASE / 'nr-deployment-verification-r01.json')
    assert inspect['result']['size_checks_pass'] and inspect['result']['sha256sums_matches_receipt']
    assert inspect['result']['receipt_file_count'] == 1113
    assert info['read_only_mount'] and 'BLASTDB Version: 5' in info['log']
    assert sizes['read_only_mount'] and sizes['result']['pal'][0] == 1
    assert manifest['result']['status'] == 'REGISTERED_NOT_VERIFIED'
    assert full_hash['result']['status'] == 'VERIFIED_FULL_SHA256' and full_hash['read_only_mount']
    digest = manifest['result']['manifest_sha256']
    assert full_hash['result']['manifest_sha256'] == deployed['manifest_sha256'] == contract['manifest_sha256'] == digest
    assert contract['status'] == 'REAL_TARGET_PREBUILT_CONTRACT_PASS'
    assert deployed['status'] == 'P4_NR_DEPLOYED_READONLY_PASS' and deployed['read_only']
    paths = {}
    for batch, branch in ((design_batch, 'DESIGN'), (wt_batch, 'WT'), (failure_batch, 'FAILURE')):
        audit = read(BASE / batch / 'audit-summary.json')
        snap = read(BASE / batch / 'workflow-snapshot.json')
        submitted = read(BASE / batch / 'batch.json')
        assert submitted['branch'] == branch.lower() and submitted['database_kind'] == 'target-nr'
        request = submitted['request']
        assert audit['status'] == 'P4_TARGET_' + branch + '_PASS'
        assert audit['database'] == 'nr-20250624' and audit['p4_m1_complete'] is False
        assert audit['scientific_release_gate'] == 'CLOSED'
        assert audit['usable_for_pipeline'] is False and audit['production_status'] == 'NOT_DEPLOYED'
        assert request['analysis']['blast']['database_id'] == 'nr-20250624'
        assert request['analysis']['blast']['database_manifest_sha256'] == ('0'*64 if branch == 'FAILURE' else digest)
        assert snap['job']['job_id'] == audit['job_id'] and snap['job']['run_id'] == audit['run_id']
        assert (snap['job']['state'] == 'failed') == (branch == 'FAILURE')
        if branch != 'FAILURE':
            assert audit['target_nr_accepted']
            assert read(BASE / batch / 'download-verification.json')['target_database_connected']
        else:
            assert not audit['target_nr_accepted']
        paths[branch.lower()] = dict(batch=batch, job_id=audit['job_id'], run_id=audit['run_id'],
                                    audit_status=audit['status'],
                                    verified_artifacts=audit['verified_artifacts'])
    assert len({row['job_id'] for row in paths.values()}) == 3
    assert len({row['run_id'] for row in paths.values()}) == 3
    value = dict(status='P4_M1_MINIMAL_PASS', database='nr-20250624',
                 database_manifest_sha256=digest, target_database_qualification='TARGET_DATABASE_UNREVIEWED',
                 database_files_verified=full_hash['result']['files'],
                 database_bytes_verified=full_hash['result']['bytes'],
                 paths=paths, himat_minimal_integration_pending=True,
                 scientific_release_gate='CLOSED', usable_for_pipeline=False,
                 production_status='NOT_DEPLOYED', public_report_api_called=False)
    path = BASE / 'p4-m1-acceptance-r01.json'
    assert not path.exists()
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(value['status'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--design-batch', required=True)
    ap.add_argument('--wt-batch', required=True)
    ap.add_argument('--failure-batch', required=True)
    args = ap.parse_args()
    close(args.design_batch, args.wt_batch, args.failure_batch)


if __name__ == '__main__':
    main()
