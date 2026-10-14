import hashlib
import io
import json
import tarfile

import pytest

from scripts.install_esmfold2_environment import digest, install


def fixture(root, *, extra=None, payload=b'import fixture\n', listed=None):
    raw = payload if listed is None else listed
    rows = [{'path': 'fixture/__init__.py', 'bytes': len(raw),
             'sha256': hashlib.sha256(raw).hexdigest()}]
    archive = root / 'site-packages.tar.gz'
    with tarfile.open(archive, 'w:gz') as t:
        info = tarfile.TarInfo('site-packages/fixture/__init__.py')
        info.size = len(payload)
        t.addfile(info, io.BytesIO(payload))
        if extra:
            t.addfile(extra, io.BytesIO(b''))
    tree = root / 'site-packages-files.json'
    tree.write_text(json.dumps({'files': rows}))
    sources = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in (archive, tree)]
    manifest = root / 'environment-pvc-manifest.json'
    manifest.write_text(json.dumps({'id': 'esmfold2-python312-cu126-pvc-r01',
                                   'scientific_gate': 'CLOSED', 'files': sources,
                                   'extracted': {'root': 'site-packages', 'manifest': tree.name,
                                                 'file_count': 1, 'total_bytes': len(raw)}}))
    return digest(manifest)


def test_install_then_reverify_and_reject_later_corruption(tmp_path):
    expected = fixture(tmp_path)
    result = install(tmp_path, expected)
    assert result['files'] == 1 and result['scientific_gate'] == 'CLOSED'
    assert (tmp_path / 'site-packages/fixture/__init__.py').read_bytes() == b'import fixture\n'
    assert install(tmp_path, expected) == result
    (tmp_path / 'site-packages/fixture/__init__.py').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        install(tmp_path, expected)
    assert (tmp_path / 'site-packages/fixture/__init__.py').read_bytes() == b'corrupt'


@pytest.mark.parametrize('kind', ['traversal', 'symlink', 'unlisted', 'duplicate'])
def test_reject_unsafe_members_without_publishing(tmp_path, kind):
    names = {'traversal': '../outside', 'symlink': 'site-packages/link',
             'unlisted': 'site-packages/extra', 'duplicate': 'site-packages/fixture/__init__.py'}
    extra = tarfile.TarInfo(names[kind])
    if kind == 'symlink':
        extra.type = tarfile.SYMTYPE
        extra.linkname = '../outside'
    expected = fixture(tmp_path, extra=extra)
    with pytest.raises(ValueError):
        install(tmp_path, expected)
    assert not (tmp_path / 'site-packages').exists()
    assert not (tmp_path / 'installation-receipt.json').exists()


def test_archive_payload_must_match_tree_hash(tmp_path):
    expected = fixture(tmp_path, payload=b'bad!', listed=b'good')
    with pytest.raises(ValueError, match='SHA-256'):
        install(tmp_path, expected)
    assert not (tmp_path / 'site-packages').exists()


def test_source_damage_rejected_before_unpack(tmp_path):
    expected = fixture(tmp_path)
    with (tmp_path / 'site-packages.tar.gz').open('ab') as f:
        f.write(b'corrupt')
    with pytest.raises(ValueError, match='source integrity'):
        install(tmp_path, expected)
    assert not (tmp_path / '.environment-unpack-r01').exists()


def test_interrupted_staging_can_be_rebuilt(tmp_path):
    expected = fixture(tmp_path)
    pending = tmp_path / '.environment-unpack-r01/site-packages/fixture/__init__.py.install-pending'
    pending.parent.mkdir(parents=True)
    pending.write_bytes(b'interrupted')
    assert install(tmp_path, expected)['files'] == 1


def test_empty_cache_directories_do_not_change_file_manifest(tmp_path):
    directory = tarfile.TarInfo('site-packages/fixture/__pycache__')
    directory.type = tarfile.DIRTYPE
    expected = fixture(tmp_path, extra=directory)
    assert install(tmp_path, expected)['files'] == 1
    assert not (tmp_path / 'site-packages/fixture/__pycache__').exists()
