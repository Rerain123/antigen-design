import base64
import hashlib
import json

import scripts.run_n12_esmfold2_acceptance as acceptance


def test_remote_payload_compiles_and_contains_same_run_chain():
    payload = acceptance.remote_payload()
    compile(payload, 'n12-remote-test', 'exec')
    for token in (
        'submit_structure_in_run',
        'submit_sequence_in_run',
        "scope='n12-esmfold2-same-run-r05'",
        'inspect_prediction',
        'EXPLICIT_ENGINEERING_ONLY_NOT_R04',
        'install_platform_modules()',
        'failure_artifacts',
        'stderr.txt',
    ):
        assert token in payload
    assert payload.index('install_platform_modules()') < payload.index('from t01_phase1_real.development import Runtime')


def test_source_hash_manifest_covers_provenance_files():
    hashes = acceptance.source_hashes()
    assert tuple(hashes) == acceptance.SOURCE_PATHS
    assert all(len(value) == 64 for value in hashes.values())


def test_save_and_verify_preserves_closed_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, 'OUT', tmp_path)
    raw = b'evidence'
    digest = hashlib.sha256(raw).hexdigest()
    jobs = ['structure', 'n11', 'n12', 'prediction']
    evidence = []
    for job_id in jobs:
        evidence.append(dict(
            job=dict(job_id=job_id, run_id='run-one', state='succeeded', usable_for_pipeline=False),
            artifacts=[dict(
                ref=dict(artifact_id='a-' + job_id, sha256=digest, size_bytes=len(raw)),
                base64=base64.b64encode(raw).decode(),
            )],
        ))
    receipt = dict(
        status='N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS',
        run_id='run-one',
        structure_job_id='structure',
        n11_job_id='n11',
        n12_job_id='n12',
        prediction_job_id='prediction',
        scientific_gate='CLOSED',
        usable_for_pipeline=False,
        automatic_handoff=False,
        production_status='NOT_DEPLOYED',
        linkage=dict(engine_selection='EXPLICIT_ENGINEERING_ONLY_NOT_R04'),
    )
    count = acceptance.save_and_verify(dict(receipt=receipt, evidence=evidence), {'x': '0' * 64})
    assert count == 4
    index = json.loads((tmp_path / 'index.json').read_text(encoding='utf-8'))
    assert index['scientific_gate'] == 'CLOSED'
    assert index['automatic_handoff'] is False
    assert index['complete_scientific_n12'] is False


def test_save_and_verify_rejects_cross_run(tmp_path, monkeypatch):
    monkeypatch.setattr(acceptance, 'OUT', tmp_path)
    receipt = dict(
        status='N12_ESMFOLD2_SAME_RUN_ENGINEERING_PASS',
        run_id='run-one',
        structure_job_id='structure',
        n11_job_id='n11',
        n12_job_id='n12',
        prediction_job_id='prediction',
        scientific_gate='CLOSED',
        usable_for_pipeline=False,
        automatic_handoff=False,
        production_status='NOT_DEPLOYED',
        linkage=dict(engine_selection='EXPLICIT_ENGINEERING_ONLY_NOT_R04'),
    )
    evidence = [
        dict(job=dict(job_id=j, run_id='run-two' if j == 'n11' else 'run-one',
                      state='succeeded', usable_for_pipeline=False), artifacts=[])
        for j in ('structure', 'n11', 'n12', 'prediction')
    ]
    try:
        acceptance.save_and_verify(dict(receipt=receipt, evidence=evidence), {})
    except RuntimeError as exc:
        assert 'exact same run' in str(exc)
    else:
        raise AssertionError('Cross-run evidence was accepted')
