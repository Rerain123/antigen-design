"""Same-run P3 scans and local delivery; never rewrite P1/P2 evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import run_m1_p2_probe as p2

ROOT = p2.ROOT
OUT = ROOT / 'discovery/t01-phase1-real/m1-p3-20260922/r01'
PREAMBLE = p2.PREAMBLE.replace('m1-p2-r01-', 'm1-p3-r01-')


def read(path):
    return json.loads(path.read_bytes())


def save(name, value, immutable=False):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if immutable and path.exists():
        assert path.read_bytes() == raw, 'Pinned P3 input changed: ' + name
    else:
        path.write_bytes(raw)


def scope(structure, topology, constraints):
    analysis = structure['result']['analysis']
    mapping = analysis['mapping']
    assert analysis['quality']['quality']['confidence'] != 'low'
    assert topology['result']['topology']['tm_count'] == 0
    assert len(mapping['chain_candidates']) == 1 and not mapping['fixed_chain_ids']
    covered = sorted(e['sequence_position'] for e in mapping['entries']
                     if e['reason'] == 'mapped' and not e['structure_residue']['insertion_code'])
    excluded = sorted(set(constraints['fixed_positions']) |
                      {r['position'] for r in constraints['restricted_positions']})
    eligible = sorted(set(covered) & set(constraints['open_positions']) - set(excluded))
    assert eligible, 'No covered explicitly OPEN site'
    return dict(scan_positions=eligible[:1], excluded_positions=excluded,
                covered_positions=covered, explicit_constraints=constraints,
                selection='LOWEST_COVERED_EXPLICIT_OPEN_POSITION_MINIMAL_NONEMPTY_TEST',
                scientific_permissions_inferred=False, homology='UNAVAILABLE', domains='UNAVAILABLE',
                structure_quality_declaration=analysis['input']['source_declaration'],
                foldx_calculation='POSITIONSCAN_SELECTED_SITE_AA20',
                thermompnn_calculation='PINNED_NATIVE_FULL_MONOMER_20xL_THEN_SELECT_REQUESTED_SCOPE',
                purpose='M1_P3_INTERNAL_ENGINEERING_ONLY')


def context():
    task = p2.context()
    assert read(p2.OUT / 'audit-summary.json')['status'] == 'M1_P2_N12_N15_PASS'
    task['p2_final'] = p2.ref(read(p2.OUT / 'final-report.json'))
    task['protected_evidence'] = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in (p2.P1, p2.OUT) for path in root.iterdir() if path.is_file()}
    save('continuation.json', task, immutable=True)
    return task


PREFLIGHT = r'''
from t01_phase1_real.development.variant_report.source import sources
from t01_phase1_real.development.variant_report.compute import evaluate
j=rt.get(task['p2_final']['job_id'])
ensure(source(j)==task['p2_final'],'HASH_MISMATCH','P2 final result identity changed')
body=decode(rt._request_bytes(j))
with rt._db() as db: files,values,receipts=sources(rt,db,body)
report=evaluate(body,files)
ensure(report==rt.result(j['job_id'])['report'],'OUTPUT_INVALID','P2 final report rebuild differs')
ensure(report['outcome']=='ALL_EXCLUDED' and len(report['records'])==24
       and all(r['disposition']=='EXCLUDED' for r in report['records']), 'OUTPUT_INVALID','P2 disposition differs')
ensure(report['m1_test']['scientific_release_gate']=='CLOSED','OUTPUT_INVALID','Unexpected release')
ensure(source(rt.get(task['structure_job_id']))['artifact']==task['structure_artifact'],
       'HASH_MISMATCH','WT structure differs')
print(json.dumps(dict(status='P3_SAME_RUN_P2_FINAL_REBUILT',run_id=run_id,
    p2_final=task['p2_final'],structure=source(rt.get(task['structure_job_id'])),
    all_excluded=True,report_api_called=False)))
'''


def step(task, name, tool, body):
    # Reuse transport/polling only, with a distinct output root and idempotency namespace.
    old = (p2.OUT, p2.PREAMBLE)
    try:
        p2.OUT, p2.PREAMBLE = OUT, PREAMBLE
        return p2.run_step(task, name, tool, body)
    finally:
        p2.OUT, p2.PREAMBLE = old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['preflight', 'scan', 'assemble'])
    args = parser.parse_args()
    task = context()
    if args.action in ('preflight', 'scan'):
        receipt = p2.deploy.remote(PREAMBLE + PREFLIGHT, task)
        save('preflight.json', receipt, immutable=True)
        design = read(p2.P1 / 'design.json')
        selection = scope(read(p2.P1 / 'structure.json'), read(p2.P1 / 'topology.json'), design['request']['constraints'])
        save('scan-scope.json', selection, immutable=True)
        base = dict(protein_sequence=task['sequence'], user_sequence_id='M1 P3 finite WT scan',
                    structure_artifact=task['structure_artifact'], scan_positions=selection['scan_positions'], timeout_seconds=900)
        source_id = 'M1-P3-20260922/r01 scan-scope.json; P1 explicit constraints; minimum covered OPEN site'
        requests = dict(foldx=dict(base, mode='positionscan', fixed_positions=selection['excluded_positions'], variants=[],
                        scope_source=dict(purpose='ENGINEERING_STABILITY_SCOPE', source_id=source_id)),
                        thermompnn=dict(base, excluded_positions=selection['excluded_positions'],
                        scope_source=dict(purpose='ENGINEERING_EXPLICIT_SCAN_SCOPE', source_id=source_id)))
        save('scan-requests.json', requests, immutable=True)
        if args.action == 'scan':
            for name, body in requests.items():
                step(task, 'foldx-r02' if name == 'foldx' else name, 't01.real.' + name, body)
        print(receipt['status'])
    else:
        base = dict(protein_sequence=task['sequence'], user_sequence_id='M1 P3 same-run local delivery', timeout_seconds=60)
        final = read(p2.OUT / 'final-report.json')
        reference = step(task, 'wt-reference', 't01.real.wt_reference', dict(base, upstream=dict(
            structure=p2.ref(read(p2.P1 / 'structure.json')), topology=p2.ref(read(p2.P1 / 'topology.json')),
            design_audit=final['request']['upstream']['design_audit'],
            foldx=p2.ref(read(OUT / 'foldx-r02.json')), thermompnn=p2.ref(read(OUT / 'thermompnn.json')))))
        step(task, 'local-delivery', 't01.real.local_delivery', dict(base, host_species=task['host'], expression_host=None,
            upstream=dict(wt_draft=p2.ref(read(p2.P1 / 'wt_draft.json')), variant_report=task['p2_final'],
                          wt_reference=p2.ref(reference)), dna_bindings=[]))


if __name__ == '__main__':
    main()
