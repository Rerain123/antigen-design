import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


def loader():
    file = Path(__file__).resolve().parents[1] / 'scripts/restore_pinned_build_sources.py'
    spec = importlib.util.spec_from_file_location('restore_sources', file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(root, entries):
    manifest = root / 'src/t01_phase1_real/development/structure/sources.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'files': [dict(path=name, sha256=hashlib.sha256(original).hexdigest()) for name, original, checkout in entries]}))
    for name, original, checkout in entries:
        (root / name).write_bytes(checkout)


def test_mixed_endings_restore_to_exact_manifest(tmp_path):
    fixture(tmp_path, [('a.md', b'a\r\nb\r\n', b'a\nb\n'), ('b.py', b'x\ny\n', b'x\ny\n')])
    m = loader()
    assert m.restore(tmp_path) == dict(verified=2, restored=1)
    assert (tmp_path / 'a.md').read_bytes() == b'a\r\nb\r\n'
    assert m.restore(tmp_path)['restored'] == 0


def test_content_change_fails_before_any_write(tmp_path):
    fixture(tmp_path, [('a.md', b'a\r\n', b'a\n'), ('b.md', b'b\r\n', b'changed\n')])
    with pytest.raises(ValueError, match='content differs'):
        loader().restore(tmp_path)
    assert (tmp_path / 'a.md').read_bytes() == b'a\n'


def test_refuses_working_tree(tmp_path):
    (tmp_path / '.git').mkdir()
    with pytest.raises(ValueError, match='Git working tree'):
        loader().restore(tmp_path)


def test_bepipred_provenance_required_but_model_volume_excluded(tmp_path):
    fixture(tmp_path, [('a.md', b'a\r\n', b'a\n')])
    manifest = tmp_path / 'src/t01_phase1_real/development/bepipred/assets.json'
    manifest.parent.mkdir()
    rows = [dict(path='provenance.txt', sha256=hashlib.sha256(b'frozen\r\n').hexdigest()),
            dict(path='var/t01-phase1-real/tool-assets/model.pt', sha256='0'*64)]
    manifest.write_text(json.dumps(dict(files=rows)))
    with pytest.raises(FileNotFoundError):
        loader().restore(tmp_path)
    assert (tmp_path / 'a.md').read_bytes() == b'a\n'
    (tmp_path / 'provenance.txt').write_bytes(b'frozen\n')
    assert loader().restore(tmp_path) == dict(verified=2, restored=2)


def test_codon_windows_manifest_restored_only_in_build_copy(tmp_path):
    fixture(tmp_path, [])
    relative='src/t01_phase1_real/development/codon/assets/manifest.json'
    source=Path(__file__).resolve().parents[1]/relative
    raw=source.read_bytes();path=tmp_path/relative;path.parent.mkdir(parents=True)
    table=json.loads(raw)['table'];table_raw=(source.parent/table['file']).read_bytes()
    (path.parent/table['file']).write_bytes(table_raw.replace(b'\r\n',b'\n'))
    lf=raw.replace(b'\r\n',b'\n');crlf=lf.replace(b'\n',b'\r\n')
    path.write_bytes(crlf if raw!=crlf else lf)
    check=loader().restore(tmp_path)
    assert check['verified']==2 and check['restored']>=1
    assert path.read_bytes()==raw and source.read_bytes()==raw
    assert (path.parent/table['file']).read_bytes()==table_raw
    path.write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='content differs'):loader().restore(tmp_path)


def profile_fixture(root):
    fixture(root, [])
    repo = Path(__file__).resolve().parents[1]
    manifest = Path('requirements/control-profile-inputs.json')
    (root / manifest).parent.mkdir(parents=True)
    (root / manifest).write_bytes((repo / manifest).read_bytes())
    for entry in json.loads((repo / manifest).read_bytes())['files']:
        name = entry['path']
        source = repo / name
        if name == 'scripts/w1_runtime_worker.py':
            source = repo / 'scripts/t01_linux_w1_worker.py'
        elif name == 'scripts/w1_runtime_supervisor.py':
            source = repo / 'scripts/t01_linux_w1_supervisor.py'
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes().replace(b'\r\n', b'\n'))
    return manifest


def test_linux_checkout_restores_all_historical_profile_inputs(tmp_path):
    manifest = profile_fixture(tmp_path)
    result = loader().restore(tmp_path, manifest)
    # The SOP was already restored by the structure manifest in full images;
    # this isolated all-LF fixture also needs that sixth restoration.
    assert result == dict(verified=9, restored=6)
    for entry in json.loads((tmp_path / manifest).read_bytes())['files']:
        assert hashlib.sha256((tmp_path / entry['path']).read_bytes()).hexdigest() == entry['sha256']
    assert loader().restore(tmp_path, manifest)['restored'] == 0


def test_profile_content_tampering_fails_without_partial_restoration(tmp_path):
    manifest = profile_fixture(tmp_path)
    entries = json.loads((tmp_path / manifest).read_bytes())['files']
    target = tmp_path / entries[-1]['path']
    target.write_bytes(target.read_bytes() + b'changed')
    before = {r['path']: (tmp_path / r['path']).read_bytes() for r in entries}
    with pytest.raises(ValueError, match='content differs'):
        loader().restore(tmp_path, manifest)
    assert before == {r['path']: (tmp_path / r['path']).read_bytes() for r in entries}


def test_missing_profile_manifest_and_path_escape_fail_closed(tmp_path):
    fixture(tmp_path, [])
    with pytest.raises(FileNotFoundError):
        loader().restore(tmp_path, Path('missing.json'))
    with pytest.raises(ValueError, match='escapes build root'):
        loader().restore(tmp_path, Path('../outside.json'))
