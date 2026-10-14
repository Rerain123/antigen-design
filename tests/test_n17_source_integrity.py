"""N17 protects audited sites even when a scan request claims otherwise."""
import pytest
from t01_phase1_real.common import RuntimeFault, encode
from t01_phase1_real.development.wt_reference import source


@pytest.mark.parametrize('engine', ['foldx', 'thermompnn'])
@pytest.mark.parametrize('permission', ['FIXED', 'RESTRICTED'])
def test_verified_audit_overrides_scan_claims(monkeypatch, engine, permission):
    from t01_phase1_real.development.design_backend import source as upstream, compute
    structure = {'job_id': 'structure', 'artifact': {'artifact_id': 'wt'}}
    audit = {'permissions': {'per_residue': [dict(position=2, design_permission=permission)]}}
    monkeypatch.setattr(upstream, 'sources', lambda *a: ({}, {}, {'verified': True}))
    monkeypatch.setattr(compute, 'evaluate', lambda *a: audit)
    request = dict(structure_artifact=structure['artifact'], mode='positionscan', scan_positions=[1, 2])
    exclusion_key = 'fixed_positions' if engine == 'foldx' else 'excluded_positions'
    request[exclusion_key] = []
    files = {'input/design_audit-request.json': encode({'upstream': {'structure': structure}}),
             'input/' + engine + '-request.json': encode(request)}
    # Even failed scans (no available value) must retain valid permission provenance.
    values = {'design_audit': {'audit': audit}}
    receipts = {'design_audit': {}}
    body = {'upstream': {'structure': structure}}
    with pytest.raises(RuntimeFault, match='FIXED/RESTRICTED'):
        source.enrich(None, None, body, files, values, receipts)
    request[exclusion_key] = [2]
    files['input/' + engine + '-request.json'] = encode(request)
    source.enrich(None, None, body, files, values, receipts)
    assert receipts['design_audit']['upstream'] == {'verified': True}
