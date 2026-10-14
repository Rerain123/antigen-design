import base64
import hashlib
import io
import json

import pytest

from scripts.download_af3_weights import URL, download, source_identity, crc32c_update


class Reply(io.BytesIO):
    def __init__(self, raw=b'', *, status=200, headers=None):
        super().__init__(raw)
        self.status = status
        self.headers = headers or {}


def provider(raw, *, ignore_range=False, damage=False):
    headers = {'Content-Length': str(len(raw)), 'ETag': '"fixed-object"',
               'x-goog-hash': 'md5=' + base64.b64encode(hashlib.md5(raw).digest()).decode()}

    def open_request(request, timeout):
        assert request.full_url == URL
        if request.get_method() == 'HEAD':
            return Reply(headers=headers)
        assert request.get_header('If-match') == headers['ETag']
        start = int(request.get_header('Range', 'bytes=0-').split('=')[1].split('-')[0])
        body = raw[start:]
        if damage:
            body = b'X' * len(body)
        if ignore_range:
            return Reply(raw, headers=headers)
        out = {**headers, 'Content-Length': str(len(body))}
        if start:
            out['Content-Range'] = f'bytes {start}-{len(raw)-1}/{len(raw)}'
        return Reply(body, status=206 if start else 200, headers=out)
    return open_request


def stage_partial(root, raw):
    root.mkdir()
    (root / 'af3.bin.zst.partial').write_bytes(raw[:3])
    (root / 'download-source.json').write_text(json.dumps({
        'url': URL, 'bytes': len(raw), 'etag': '"fixed-object"',
        'md5_base64': base64.b64encode(hashlib.md5(raw).digest()).decode()}))


def test_success_recheck_and_resume(tmp_path):
    raw = b'official-test-fixture'
    root = tmp_path / 'weights'
    stage_partial(root, raw)
    receipt = download(root, provider(raw))
    assert (root / 'af3.bin.zst').read_bytes() == raw
    assert receipt['sha256'] == hashlib.sha256(raw).hexdigest()
    assert receipt['scientific_gate'] == 'CLOSED'
    assert download(root, provider(raw)) == receipt


@pytest.mark.parametrize('empty_partial', [False, True])
def test_fresh_and_empty_partial(tmp_path, empty_partial):
    raw = b'official-test-fixture'
    root = tmp_path / 'weights'
    if empty_partial:
        stage_partial(root, raw)
        (root / 'af3.bin.zst.partial').write_bytes(b'')
    assert download(root, provider(raw))['official_md5_verified'] is True
    assert (root / 'af3.bin.zst').read_bytes() == raw


def test_range_ignored_preserves_partial(tmp_path):
    raw = b'official-test-fixture'
    root = tmp_path / 'weights'
    stage_partial(root, raw)
    with pytest.raises(ValueError, match='honor'):
        download(root, provider(raw, ignore_range=True))
    assert (root / 'af3.bin.zst.partial').read_bytes() == raw[:3]


def test_corrupt_download_never_promoted(tmp_path):
    with pytest.raises(ValueError, match='MD5 mismatch'):
        download(tmp_path, provider(b'official-test-fixture', damage=True))
    assert not (tmp_path / 'af3.bin.zst').exists()
    assert not (tmp_path / 'download-receipt.json').exists()


def test_changed_source_refuses_resume(tmp_path):
    root = tmp_path / 'weights'
    stage_partial(root, b'old-version')
    with pytest.raises(ValueError, match='Remote object changed'):
        download(root, provider(b'new-version'))
    assert (root / 'af3.bin.zst.partial').read_bytes() == b'old'


def test_crc32c_standard_vector_chunked():
    state = crc32c_update(0xffffffff, b'1234')
    assert crc32c_update(state, b'56789') ^ 0xffffffff == 0xe3069283


@pytest.mark.parametrize('damage', [False, True])
def test_crc32c_only_official_object(tmp_path, damage):
    # Published CRC32C check vector; independent of the implementation.
    raw = b'123456789'
    headers = {'Content-Length':'9', 'ETag':'"crc-object"', 'x-goog-hash':'crc32c=4waSgw=='}
    def open_request(request, timeout):
        return Reply(b'' if request.get_method() == 'HEAD' else (b'123456780' if damage else raw), headers=headers)
    if damage:
        with pytest.raises(ValueError, match='CRC32C mismatch'):
            download(tmp_path, open_request)
        assert not (tmp_path / 'af3.bin.zst').exists()
    else:
        receipt = download(tmp_path, open_request)
        assert receipt['official_crc32c_verified'] is True
        assert receipt['official_md5_verified'] is False


def test_repeated_hash_headers():
    from email.message import Message
    h = Message()
    h['Content-Length'] = '9'
    h['ETag'] = '"both"'
    h['x-goog-hash'] = 'crc32c=4waSgw=='
    h['x-goog-hash'] = 'md5=' + base64.b64encode(hashlib.md5(b'123456789').digest()).decode()
    result = source_identity(h)
    assert 'crc32c_base64' in result and 'md5_base64' in result


def test_missing_checksum_rejected():
    with pytest.raises(ValueError, match='incomplete'):
        source_identity({'Content-Length':'9', 'ETag':'"missing"'})
