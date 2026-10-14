import base64
import hashlib
import io
import json

import pytest

from scripts.download_af3_databases import BASE, download_one


RAW = b'official-database-test-fixture'
NAME = 'test.fasta.zst'
IDENTITY = {'url': BASE+NAME, 'bytes': len(RAW), 'etag': '"fixed"',
            'md5_base64': base64.b64encode(hashlib.md5(RAW).digest()).decode()}
ASSET = {'file': NAME, 'identity': IDENTITY}


class Reply(io.BytesIO):
    def __init__(self, body, headers, status=200):
        super().__init__(body)
        self.headers, self.status = headers, status


def provider(mode='ok'):
    def open_request(request, timeout):
        assert request.full_url == BASE + NAME
        headers = {'Content-Length': str(len(RAW)), 'ETag': IDENTITY['etag'],
                   'x-goog-hash': 'md5='+IDENTITY['md5_base64']}
        if request.get_method() == 'HEAD':
            if mode == 'changed':
                headers['ETag'] = '"new"'
            return Reply(b'', headers)
        assert request.get_header('If-match') == IDENTITY['etag']
        start = int(request.get_header('Range', 'bytes=0-').split('=')[1][:-1])
        body = RAW[start:]
        headers['Content-Length'] = str(len(body))
        if start:
            headers['Content-Range'] = f'bytes {start}-{len(RAW)-1}/{len(RAW)}'
        if mode == 'corrupt':
            body = b'X'*len(body)
        if mode == 'short':
            body = body[:-1]
        if mode == 'bad_range':
            headers['Content-Range'] = 'bytes 0-1/2'
        return Reply(body, headers, 206 if start and mode != 'ignore_range' else 200)
    return open_request


@pytest.mark.parametrize('offset', [None, 0, 7, len(RAW)])
def test_download_resume_and_reverify(tmp_path, offset):
    if offset is not None:
        (tmp_path / (NAME+'.partial')).write_bytes(RAW[:offset])
        (tmp_path / (NAME+'.source.json')).write_text(json.dumps(IDENTITY))
    receipt = download_one(tmp_path, ASSET, provider())
    assert (tmp_path / NAME).read_bytes() == RAW
    assert receipt['sha256'] == hashlib.sha256(RAW).hexdigest()
    assert receipt['official_md5_verified'] and not receipt['decompressed']
    assert receipt['scientific_gate'] == 'CLOSED'
    assert download_one(tmp_path, ASSET, provider()) == receipt


@pytest.mark.parametrize('mode', ['corrupt', 'short', 'changed', 'ignore_range', 'bad_range'])
def test_reject_invalid_download(tmp_path, mode):
    (tmp_path / (NAME+'.partial')).write_bytes(RAW[:7])
    (tmp_path / (NAME+'.source.json')).write_text(json.dumps(IDENTITY))
    with pytest.raises(ValueError):
        download_one(tmp_path, ASSET, provider(mode))
    assert not (tmp_path / NAME).exists()
    assert not (tmp_path / (NAME+'.receipt.json')).exists()


def test_existing_unidentified_file_is_preserved(tmp_path):
    (tmp_path / NAME).write_bytes(b'unknown')
    with pytest.raises(ValueError, match='no source identity'):
        download_one(tmp_path, ASSET, provider())
    assert (tmp_path / NAME).read_bytes() == b'unknown'


def test_rancher_bundle_matches_sources_and_is_isolated():
    from pathlib import Path
    import yaml
    root = Path(__file__).resolve().parents[1]
    pvc, config, job = list(yaml.safe_load_all((root / 'deploy/alphafold3/databases-download.r01.rancher.yaml').read_text(encoding='utf-8')))
    assert pvc['metadata']['name'] == 'antigen-af3-databases'
    assert pvc['spec']['resources']['requests']['storage'] == '1Ti'
    for name in ('download_af3_databases.py', 'download_af3_weights.py'):
        assert config['data'][name] == (root/'scripts'/name).read_text(encoding='utf-8')
    manifest = json.loads(config['data']['database-manifest.json'])
    assert len(manifest['assets']) == 9
    assert sum(a['identity']['bytes'] for a in manifest['assets']) == 238784443666
    pod = job['spec']['template']['spec']
    assert [v['persistentVolumeClaim']['claimName'] for v in pod['volumes'] if 'persistentVolumeClaim' in v] == ['antigen-af3-databases']
    assert 'nvidia.com/gpu' not in pod['containers'][0]['resources']['limits']
