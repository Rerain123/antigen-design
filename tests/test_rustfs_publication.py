import pytest
from t01_phase1_real.service_api.object_storage import RustFSPublisher,StorageError,digest,report_name


def publisher():
    return RustFSPublisher(endpoint='https://storage.example.test',bucket='antigen-design',access_key='dummy-access',secret_key='dummy-secret')


def test_round_trip_and_retry_never_overwrite(monkeypatch):
    p=publisher(); objects={}; puts=[]
    def request(method,key,body=b'',extra=None,anonymous=False,max_bytes=0):
        if method=='HEAD':
            return (200,{'content-length':str(len(objects[key])),'x-amz-meta-sha256':digest(objects[key])},b'') if key in objects else (404,{},b'')
        if method=='PUT':
            assert extra['if-none-match']=='*'
            objects[key]=body;puts.append(key);return 200,{},b''
        if method=='GET':
            assert anonymous;return 200,{},objects[key]
        if method=='DELETE':
            objects.pop(key,None);return 204,{},b''
        raise AssertionError(method)
    monkeypatch.setattr(p,'_request',request)
    args=('svc-'+'a'*24,'t01p1r-job-'+'b'*32,b'zip-bytes','test report')
    kw=dict(created_at='2026-10-10T23:38:07.269646Z',html=b'<html>report</html>',native=b'native-zip')
    result=p.publish_report(*args,**kw)
    assert p.publish_report(*args,**kw)==result and len(puts)==4
    assert {a['fileName'] for a in result}=={'20261011-073807-bbbbbbbb-'+suffix
        for suffix in ('report.html','report.md','results.zip','tool-results.zip')}
    assert len({a['storageKey'].rsplit('/',1)[0] for a in result})==1
    assert all('/20261011-073807-bbbbbbbb/files-' in a['fileUrl'] for a in result)
    assert all('/antigen-design/data/svc-' in a['fileUrl'] for a in result)
    before=dict(objects)
    changed=p.publish_report(*args,**dict(kw,html=b'<html>updated rendering</html>'))
    assert len(puts)==8 and all(objects[key]==raw for key,raw in before.items())
    assert {a['storageKey'] for a in result}.isdisjoint(a['storageKey'] for a in changed)
    assert p.probe()['test_object_deleted']
    assert len(objects)==8


@pytest.mark.parametrize('stamp',['2026-10-10T23:38:07.269646Z','2026-10-11T07:38:07.269646+08:00'])
def test_report_name_uses_creation_time_in_beijing_across_date_boundary(stamp):
    assert report_name('t01p1r-job-7ff412a6d443473bae22b1be05429206',stamp)=='20261011-073807-7ff412a6'


@pytest.mark.parametrize('stamp',[None,'bad','2026-10-11T07:38:07','2026-02-30T00:00:00Z'])
def test_invalid_or_ambiguous_timestamp_is_rejected_before_upload(monkeypatch,stamp):
    p=publisher()
    monkeypatch.setattr(p,'_request',lambda *a,**k:pytest.fail('Invalid identity attempted an upload'))
    with pytest.raises(StorageError,match='creation time'):
        p.publish_report('svc-'+'a'*24,'t01p1r-job-'+'b'*32,b'zip','report',created_at=stamp)


def test_native_publication_uses_export_limit_and_checks_all_sizes_before_writing(monkeypatch):
    p=publisher();calls=[]
    monkeypatch.setattr(p,'_put',lambda key,raw,media,**kw:calls.append((key,len(raw),kw['max_bytes'])) or 'https://example.test/'+key)
    from t01_phase1_real.service_api.native_results import MAX_ARCHIVE
    from t01_phase1_real.service_api.object_storage import MAX_NATIVE_REPORT_BYTES
    assert MAX_NATIVE_REPORT_BYTES == MAX_ARCHIVE == 128*1024**2
    native=b'x'*(64*1024**2+1)
    p.publish_report('svc-'+'a'*24,'t01p1r-job-'+'b'*32,b'zip','report',
        created_at='2026-10-10T23:38:07Z',native=native)
    assert calls[-1][1:]==(len(native),MAX_ARCHIVE)
    calls.clear()
    with pytest.raises(StorageError,match='size limit'):
        p.publish_report('svc-'+'a'*24,'t01p1r-job-'+'b'*32,native,'report',
            created_at='2026-10-10T23:38:07Z')
    assert calls==[]


def test_native_size_boundary_is_rejected_before_any_storage_request(monkeypatch):
    from t01_phase1_real.service_api import object_storage
    monkeypatch.setattr(object_storage, 'MAX_NATIVE_REPORT_BYTES', 8)
    p=publisher(); calls=[]
    monkeypatch.setattr(p, '_put', lambda key,*a,**k: calls.append(key) or 'https://example.test/'+key)
    args=('svc-'+'a'*24, 't01p1r-job-'+'b'*32, b'zip', 'report')
    p.publish_report(*args, created_at='2026-10-10T23:38:07Z', native=b'x'*8)
    assert len(calls)==3
    calls.clear()
    with pytest.raises(StorageError, match='size limit'):
        p.publish_report(*args, created_at='2026-10-10T23:38:07Z', native=b'x'*9)
    assert calls==[]


def test_short_code_collision_keeps_full_job_identity_in_storage_version(monkeypatch):
    p=publisher()
    monkeypatch.setattr(p,'_put',lambda key,*a,**k:'https://example.test/'+key)
    kw=dict(created_at='2026-10-10T23:38:07Z')
    first=p.publish_report('svc-'+'a'*24,'t01p1r-job-'+'b'*32,b'zip','report',**kw)
    other=p.publish_report('svc-'+'a'*24,'t01p1r-job-'+'b'*8+'c'*24,b'zip','report',**kw)
    assert first[0]['fileName']==other[0]['fileName']
    assert first[0]['fileUrl']!=other[0]['fileUrl']


@pytest.mark.parametrize('bad', ['https://user:password@storage.test','http://storage.test','https://storage.test/console','https://storage.test?x=1'])
def test_reject_untrusted_endpoint_forms(bad):
    with pytest.raises(StorageError):
        RustFSPublisher(endpoint=bad,bucket='antigen-design',access_key='dummy-access',secret_key='dummy-secret')


def test_public_download_must_match_before_link_is_returned(monkeypatch):
    p=publisher()
    def request(method,key,**kwargs):
        if method=='HEAD':return 200,{'content-length':'3','x-amz-meta-sha256':digest(b'abc')},b''
        return 200,{},b'xyz'
    monkeypatch.setattr(p,'_request',request)
    with pytest.raises(StorageError,match='Public report download'):
        p._put('data/report',b'abc','text/plain')


def test_owner_key_validation_and_error_redaction(monkeypatch):
    p=publisher()
    with pytest.raises(StorageError):p.publish_report('../other','job',b'','',created_at='2026-10-10T23:38:07Z')
    monkeypatch.setattr(p,'_request',lambda *a,**k:(403,{},b'dummy-secret'))
    with pytest.raises(StorageError) as e:p._put('data/report',b'x','text/plain')
    assert 'dummy-secret' not in str(e.value)


def test_signing_binds_path_payload_and_metadata():
    p=publisher(); stamp='20260916T000000Z'
    a=p._headers('PUT','/antigen-design/data/a',b'x',{'x-amz-meta-sha256':digest(b'x')},stamp)
    b=p._headers('PUT','/antigen-design/data/b',b'x',{'x-amz-meta-sha256':digest(b'x')},stamp)
    assert a['authorization']!=b['authorization']
    assert a['x-amz-content-sha256']==digest(b'x')
    assert 'dummy-secret' not in a['authorization']
