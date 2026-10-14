"""Guard the shared boundary, especially false success and evidence mix-ups."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / '工作流设计/02-数据契约/tool-interface-v0.1'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


V = load_module('tool_interface_under_test', CONTRACT / 'validate.py')
P = load_module('tool_handoff_under_test', ROOT / 'scripts/package_tool_handoffs.py')


def pair(name):
    folder = CONTRACT / 'examples' / name
    return V.strict_json(folder / 'request.json'), V.strict_json(folder / 'output/result.json')


@pytest.mark.parametrize('name', sorted(p.name for p in (CONTRACT / 'examples').iterdir() if p.is_dir()))
def test_bundled_examples_are_consistent_and_never_pipeline(name):
    folder = CONTRACT / 'examples' / name
    assert V.validate_paths(folder / 'request.json', folder / 'output/result.json', True) == []
    request, result = pair(name)
    assert request['run_mode'] == 'engineering_example'
    assert result['usable_for_pipeline'] is False


@pytest.mark.parametrize('name,path,value,expected', [
    ('bepipred-success-shape', ('usable_for_pipeline',), True, 'run_mode'),
    ('bepipred-rules-pending', ('review_required',), False, 'review'),
    ('bepipred-rules-pending', ('result',), {'linear_scores': [.1] * 10, 'linear_peaks': []}, 'unresolved'),
    ('bepipred-failed', ('result',), {'linear_scores': [.1] * 10, 'linear_peaks': []}, 'result'),
    ('bepipred-failed', ('issues',), [], 'error severity'),
    ('bepipred-failed', ('issues', 0, 'severity'), 'warning', 'severity must be error'),
    ('bepipred-success-shape', ('execution_status',), 'skipped', 'result'),
    ('bepipred-success-shape', ('request_id',), 'another-request', 'does not match'),
    ('bepipred-success-shape', ('contract_version',), '0.2.0', 'contract_version'),
    ('bepipred-success-shape', ('provenance', 'parameters_sha256'), '0' * 64, 'parameters_sha256'),
    ('bepipred-success-shape', ('provenance', 'rule_profile'), None, 'rule_profile'),
    ('bepipred-success-shape', ('provenance', 'tool_exit_code'), 1, 'zero tool exit code'),
    ('bepipred-success-shape', ('provenance', 'finished_at'), '2026-09-04T00:00:00Z', 'precedes'),
    ('bepipred-success-shape', ('provenance', 'environment_artifact_id'), 'missing', 'environment_artifact_id'),
    ('bepipred-success-shape', ('result', 'linear_scores'), [.1], 'array length'),
    ('bepipred-success-shape', ('result', 'linear_peaks'), [{'start': 0, 'end': 2, 'mean_score': .1}], 'start'),
    ('bepipred-success-shape', ('result', 'linear_peaks'), [{'start': 8, 'end': 7, 'mean_score': .1}], 'intervals'),
    ('bepipred-success-shape', ('result', 'linear_peaks'), [{'start': 1, 'end': 11, 'mean_score': .1}], 'intervals'),
    ('bepipred-success-shape', ('result', 'linear_peaks'), [{'start': 1, 'end': 6, 'mean_score': .1}, {'start': 6, 'end': 9, 'mean_score': .1}], 'intervals'),
    ('freesasa-partial', ('issues',), [], 'every null'),
    ('freesasa-partial', ('issues', 0, 'positions'), [4], 'exceeds'),
    ('freesasa-success', ('result', 'per_residue'), [1.1, .5, .5], 'per_residue'),
    ('freesasa-skipped', ('provenance', 'command'), ['freesasa'], 'must not'),
    ('bepipred-success-shape', ('artifacts', 0, 'path'), '../outside.txt', 'path'),
    ('bepipred-success-shape', ('artifacts', 0, 'path'), 'result.json', 'itself'),
    ('bepipred-success-shape', ('artifacts', 1, 'artifact_id'), 'raw-example', 'duplicate'),
    ('bepipred-success-shape', ('provenance', 'environment_artifact_id'), 'raw-example', 'environment_artifact_id'),
])
def test_reject_inconsistent_results(name, path, value, expected):
    request, result = pair(name)
    target = result
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert expected in '\n'.join(V.pair_errors(request, result))


def test_mismatched_tool_returns_validation_error_not_exception():
    request, _ = pair('freesasa-success')
    _, result = pair('bepipred-success-shape')
    assert 'tool_id' in '\n'.join(V.pair_errors(request, result))


def test_n13_cannot_inherit_n02_skip():
    request, result = pair('freesasa-skipped')
    request['node_id'] = 'N13'
    assert 'only N02' in '\n'.join(V.pair_errors(request, result))


def test_low_quality_n02_cannot_run_tool():
    request, result = pair('freesasa-success')
    request['inputs']['quality_confidence'] = 'low'
    assert 'must not' in '\n'.join(V.pair_errors(request, result))


def test_unverified_mapping_cannot_produce_aligned_payload():
    request, result = pair('freesasa-success')
    request['inputs']['mapping_status'] = 'unverified'
    assert 'verified mapping' in '\n'.join(V.pair_errors(request, result))


def test_threshold_relaxation_requires_reason_and_decision_reference():
    request, _ = pair('bepipred-rules-pending')
    request['parameters']['threshold'] = .12
    assert 'relaxation_metadata' in '\n'.join(V.request_errors(request))
    request['parameters']['relaxation_metadata'] = {'reason': 'example', 'decision_ref': 'example-only'}
    assert V.request_errors(request) == []  # Format only, does not approve the decision.


def test_old_flat_request_and_arbitrary_extensions_rejected():
    request, _ = pair('bepipred-rules-pending')
    request['sequence'] = request['inputs']['sequence']
    request['output_dir'] = 'out'
    assert 'Additional properties' in '\n'.join(V.request_errors(request))


def test_pipeline_computation_requires_asset_references_but_skip_does_not():
    request, _ = pair('freesasa-success')
    request['run_mode'] = 'pipeline'
    assert 'file and hash' in '\n'.join(V.request_errors(request))
    request, _ = pair('freesasa-skipped')
    request['run_mode'] = 'pipeline'
    assert V.request_errors(request) == []


def test_g0_can_record_success_but_never_publish_pipeline_result():
    request, result = pair('bepipred-rules-pending')
    request['run_mode'] = result['run_mode'] = 'g0_probe'
    assert V.pair_errors(request, result) == []
    result['usable_for_pipeline'] = True
    assert V.pair_errors(request, result)


def test_pipeline_shape_does_not_claim_to_validate_scientific_approval():
    request, result = pair('bepipred-success-shape')
    request['run_mode'] = result['run_mode'] = 'pipeline'
    result['usable_for_pipeline'] = True
    assert V.pair_errors(request, result) == []
    # The caller must authenticate the actual approved profile/G1; the format cannot prove it.
    result['review_required'] = True
    assert V.pair_errors(request, result)


@pytest.mark.parametrize('text', ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_strict_json_rejects_ambiguous_or_nonfinite_values(tmp_path, text):
    path = tmp_path / 'bad.json'
    path.write_text(text, encoding='utf-8')
    with pytest.raises(ValueError):
        V.strict_json(path)


@pytest.mark.parametrize('path', ['../x', '/x', 'C:/x', 'https://example.com/x', 'a\\x', 'a/../x', 'a//x', 'a/./x'])
def test_local_paths_never_escape_or_fetch(tmp_path, path):
    with pytest.raises(ValueError):
        V.local_path(tmp_path, path)


def test_symlink_escape_rejected_when_os_allows_symlink(tmp_path):
    root = tmp_path / 'root'
    root.mkdir()
    outside = tmp_path / 'outside.txt'
    outside.write_text('outside', encoding='utf-8')
    try:
        (root / 'link').symlink_to(outside)
    except OSError:
        pytest.skip('Creating symlinks is not available to this Windows account')
    with pytest.raises(ValueError, match='escapes'):
        V.local_path(root, 'link')


def test_request_raw_bytes_hash_detects_even_whitespace_change(tmp_path):
    source = CONTRACT / 'examples/bepipred-success-shape'
    shutil.copytree(source, tmp_path / 'case')
    request = tmp_path / 'case/request.json'
    request.write_bytes(request.read_bytes() + b'\n')
    errors = V.validate_paths(request, tmp_path / 'case/output/result.json', True)
    assert 'exact request bytes' in '\n'.join(errors)


def test_artifact_hash_detects_tampering_without_changing_json_shape(tmp_path):
    source = CONTRACT / 'examples/bepipred-success-shape'
    shutil.copytree(source, tmp_path / 'case')
    (tmp_path / 'case/output/raw/fixture.txt').write_bytes(b'changed')
    errors = V.validate_paths(tmp_path / 'case/request.json', tmp_path / 'case/output/result.json', True)
    assert 'SHA-256' in '\n'.join(errors)
    assert 'size_bytes' in '\n'.join(errors)


def test_input_asset_hash_is_checked_from_request_directory(tmp_path):
    request, _ = pair('freesasa-success')
    asset = tmp_path / 'structure.pdb'
    asset.write_bytes(b'engineering-test-only')
    request['inputs']['structure'] = {'path': 'structure.pdb', 'sha256': V.sha256(asset.read_bytes())}
    assert V.check_files(request, None, tmp_path, tmp_path) == []
    asset.write_bytes(b'tampered')
    assert 'SHA-256' in '\n'.join(V.check_files(request, None, tmp_path, tmp_path))


def test_cli_failure_is_nonzero_and_pass_scope_is_explicit(tmp_path):
    path = tmp_path / 'invalid.json'
    path.write_text('{"x":1e999}', encoding='utf-8')
    result = subprocess.run([sys.executable, str(CONTRACT / 'validate.py'), '--request', str(path)], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output['status'] == 'FAIL'
    assert output['scientific_acceptance'] == 'NOT_EVALUATED'


def test_current_packages_match_canonical_and_archives():
    report = P.check()
    assert report['status'] == 'PASS'
    assert len(report['packages']) == 2


@pytest.mark.parametrize('package', P.PACKAGES)
def test_extracted_package_validator_runs_without_repository(tmp_path, package):
    import zipfile
    archive = P.BASE / 'releases' / f'{package}-v0.1.zip'
    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp_path)
    folder = tmp_path / package
    result = subprocess.run([sys.executable, str(folder / 'interface/validate.py'), '--examples'], cwd=tmp_path, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['checked'] == 8


def test_packaging_is_repeatable_and_preserves_source_copies(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    base = root / 'docs/project/phase1/handoffs'
    contract = root / '工作流设计/02-数据契约/tool-interface-v0.1'
    shutil.copytree(P.BASE, base, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(CONTRACT, contract, ignore=shutil.ignore_patterns('__pycache__'))
    for package in P.PACKAGES:
        manifest = json.loads((base / package / 'references/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
        for row in manifest['sources']:
            dst = root / row['source_path']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / row['source_path'], dst)
    monkeypatch.setattr(P, 'ROOT', root)
    monkeypatch.setattr(P, 'BASE', base)
    monkeypatch.setattr(P, 'CONTRACT', contract)
    P.build()
    assert P.check()['status'] == 'PASS'
    before = {p.name: p.read_bytes() for p in (base / 'releases').glob('*.zip')}
    P.build()
    assert before == {p.name: p.read_bytes() for p in (base / 'releases').glob('*.zip')}
    manifest = json.loads((base / P.PACKAGES[0] / 'references/SOURCE_MANIFEST.json').read_text(encoding='utf-8'))
    first = manifest['sources'][0]
    (root / first['source_path']).write_bytes(b'changed-original')
    with pytest.raises(ValueError, match='authoritative copy drift'):
        P.build()
    assert before == {p.name: p.read_bytes() for p in (base / 'releases').glob('*.zip')}
