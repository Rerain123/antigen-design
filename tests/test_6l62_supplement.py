"""Real-source regression checks for the offline 6L62 data import."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('build_6l62_supplement',ROOT/'scripts/build_6l62_supplement.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

def test_rebuild_is_byte_identical_and_includes_assembly_neighbors(tmp_path,monkeypatch):
    original=builder.OUT
    monkeypatch.setattr(builder,'OUT',tmp_path)
    summary=builder.build()
    assert summary['contact_count']==23
    assert {88,189,231}<=set(summary['contacts'])
    assert summary['mapped_residues']==185
    for f in original.joinpath('supplement').rglob('*'):
        if f.is_file():assert f.read_bytes()==(tmp_path/'supplement'/f.relative_to(original/'supplement')).read_bytes()
    # A repeated build must neither modify source nor silently regenerate different bytes.
    assert builder.build()==summary

def test_official_source_tampering_is_rejected(tmp_path,monkeypatch):
    source=tmp_path/'source';source.mkdir()
    for f in builder.SOURCE.iterdir():
        if f.is_file():(source/f.name).write_bytes(f.read_bytes())
    with (source/'6L62.pdb').open('ab') as f:f.write(b'REMARK changed\n')
    monkeypatch.setattr(builder,'SOURCE',source)
    monkeypatch.setattr(builder,'OUT',tmp_path)
    with pytest.raises(AssertionError):builder.build()

def test_contact_mapping_cannot_accept_wrong_residue_identity():
    entry=json.loads((builder.OUT/'coordinate-entry.json').read_bytes())
    meta=json.loads((builder.SOURCE/'iedb-source-records.json').read_bytes())
    raw=(builder.OUT/'supplement'/entry['path']).read_bytes()
    package=dict(pdb_text=raw.decode(),coordinate_sha256=builder.sha(raw),residue_map=entry['residue_map'],source_iedb_id='1065884')
    next(r for r in package['residue_map'] if r['resseq']==55)['subject_position']=56
    with pytest.raises(ValueError,match='identity differs'):
        builder.complex_contacts(package,meta['structures'][0],meta['proteins'][0]['sequence'])

def test_nonidentical_residues_are_excluded_and_contacts_fully_mapped():
    proof=json.loads((builder.OUT/'local-validation.json').read_bytes())
    excluded={r['author_position'] for r in proof['excluded_nonidentical']}
    assert excluded=={51,77,191,200,206}
    assert not excluded & {r['resseq'] for r in proof['contacts']}
    assert proof['checked_operators']==60
    assert proof['contact_boundary_classification_unchanged'] is True
    assert proof['antigen_coordinates_unchanged'] is True

def test_himat_new_database_matches_registered_manifest_and_separates_replay(monkeypatch):
    from t01_phase1_real.service_api import himat
    from t01_phase1_real.service_api.app import Principal
    captured=[]
    class Capture:
        def submit(self,principal,body):
            captured.append(body)
            return dict(job_id='capture-only',state='queued')
    principal=Principal('himat-t01-test',frozenset(['submit','query','download']),'capture-only')
    adapter=himat.HiMatIntegration(Capture(),'https://example.invalid',b'x'*32)
    sequence=json.loads((builder.SOURCE/'iedb-source-records.json').read_bytes())['proteins'][0]['sequence']
    for _ in range(2):adapter.submit_sequence(principal,sequence,'猪')
    assert captured[0]==captured[1]
    manifest=(builder.OUT/'manifest.json').read_bytes()
    blast=captured[0]['request']['analysis']['blast']
    assert blast['database_id']==json.loads(manifest)['database_id']==builder.NEW_ID
    assert blast['database_manifest_sha256']==builder.sha(manifest)
    monkeypatch.setattr(himat,'TARGET_IEDB_DATABASE_ID','iedb-20260924-r01')
    monkeypatch.setattr(himat,'TARGET_IEDB_MANIFEST_SHA256','96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12')
    adapter.submit_sequence(principal,sequence,'猪')
    assert captured[0]['idempotency_key']!=captured[2]['idempotency_key']
    assert captured[0]['request']['revision_config']==captured[2]['request']['revision_config']
    assert captured[0]['request']['prediction']['engine']=='af3'
