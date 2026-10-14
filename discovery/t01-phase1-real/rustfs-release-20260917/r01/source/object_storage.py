"""Bounded public-read report publication to an operator-configured S3 endpoint.

Only verified report bytes enter this module. No caller-supplied URL, credentials,
or filesystem path is accepted. SigV4 requests use TLS and never follow redirects.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import http.client
import os
import re
import ssl
from urllib.parse import quote, urlsplit
from uuid import uuid4


class StorageError(Exception):
    """Messages contain neither response bodies nor credentials."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class RustFSPublisher:
    def __init__(self, *, endpoint, bucket, access_key, secret_key,
                 public_base=None, prefix='data', region='us-east-1'):
        self.endpoint = self._endpoint(endpoint)
        self.public_base = self._endpoint(public_base or endpoint)
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
            raise StorageError('Invalid storage bucket configuration')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*', prefix):
            raise StorageError('Invalid storage prefix configuration')
        if not re.fullmatch(r'[a-z0-9-]+', region):
            raise StorageError('Invalid storage region configuration')
        if any(not v or any(ord(c)<33 or ord(c)>126 for c in v) for v in (access_key,secret_key)):
            raise StorageError('Missing or invalid storage credentials')
        self.bucket, self.prefix, self.region = bucket, prefix, region
        self._access_key, self._secret_key = access_key, secret_key

    @staticmethod
    def _endpoint(value):
        u=urlsplit(value)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/') or u.query or u.fragment:
            raise StorageError('Storage endpoint must be an HTTPS origin')
        return value.rstrip('/')

    @classmethod
    def from_environment(cls):
        enabled=os.environ.get('RUSTFS_ENABLED','false').lower()
        if enabled=='false':
            return None
        if enabled!='true':
            raise StorageError('Invalid RUSTFS_ENABLED value')
        return cls(endpoint=os.environ.get('RUSTFS_ENDPOINT_URL',''),
                   public_base=os.environ.get('RUSTFS_PUBLIC_BASE_URL') or None,
                   bucket=os.environ.get('RUSTFS_BUCKET',''),
                   access_key=os.environ.get('RUSTFS_ACCESS_KEY_ID',''),
                   secret_key=os.environ.get('RUSTFS_SECRET_ACCESS_KEY',''),
                   prefix=os.environ.get('RUSTFS_OBJECT_PREFIX','data'),
                   region=os.environ.get('RUSTFS_REGION','us-east-1'))

    def _path(self,key):
        if not key.startswith(self.prefix+'/') or any(p in ('','.','..') for p in key.split('/')):
            raise StorageError('Object key outside configured report prefix')
        return '/'+self.bucket+'/'+quote(key,safe='/-_.~')

    def _headers(self, method, path, body, extra, stamp):
        headers={'host':urlsplit(self.endpoint).netloc, 'x-amz-date':stamp,
                 'x-amz-content-sha256':digest(body), **extra}
        names=';'.join(sorted(headers))
        canonical=''.join(k+':'+str(headers[k]).strip()+'\n' for k in sorted(headers))
        request='\n'.join([method,path,'',canonical,names,digest(body)])
        scope=stamp[:8]+'/'+self.region+'/s3/aws4_request'
        to_sign='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+digest(request.encode())
        key=('AWS4'+self._secret_key).encode()
        for value in (stamp[:8],self.region,'s3','aws4_request'):
            key=hmac.new(key,value.encode(),hashlib.sha256).digest()
        signature=hmac.new(key,to_sign.encode(),hashlib.sha256).hexdigest()
        headers['authorization']='AWS4-HMAC-SHA256 Credential='+self._access_key+'/'+scope+', SignedHeaders='+names+', Signature='+signature
        return headers

    @staticmethod
    def _exchange(origin,method,path,body,headers,max_bytes):
        u=urlsplit(origin)
        connection=http.client.HTTPSConnection(u.hostname,u.port or 443,timeout=30,context=ssl.create_default_context())
        try:
            connection.request(method,path,body=body,headers=headers)
            response=connection.getresponse()
            response_headers={k.lower():v for k,v in response.getheaders()}
            # Never follow a redirect, and never propagate server error bodies.
            if method=='HEAD' or response.status>=300:
                data=b''
            else:
                data=response.read(max_bytes+1)
                if len(data)>max_bytes:
                    raise StorageError('Storage response exceeded expected size')
            return response.status,response_headers,data
        except (OSError,http.client.HTTPException):
            raise StorageError('Storage connection failed; retry report publication') from None
        finally:
            connection.close()

    def _request(self,method,key,body=b'',extra=None,anonymous=False,max_bytes=0):
        path=self._path(key)
        origin=self.public_base if anonymous else self.endpoint
        headers={} if anonymous else self._headers(method,path,body,extra or {},datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        return self._exchange(origin,method,path,body,headers,max_bytes)

    def _verify(self,key,raw):
        status,headers,_=self._request('HEAD',key)
        if status!=200 or headers.get('content-length')!=str(len(raw)) or headers.get('x-amz-meta-sha256')!=digest(raw):
            raise StorageError('Uploaded report metadata verification failed')
        status,_,observed=self._request('GET',key,anonymous=True,max_bytes=len(raw))
        if status!=200 or digest(observed)!=digest(raw):
            raise StorageError('Public report download verification failed; check bucket read policy')

    def _put(self,key,raw,media_type):
        if not isinstance(raw,bytes) or len(raw)>32*1024**2:
            raise StorageError('Report exceeds publication size limit')
        status,headers,_=self._request('HEAD',key)
        if status==404:
            status,_,_=self._request('PUT',key,raw,{'content-type':media_type,'x-amz-meta-sha256':digest(raw),'if-none-match':'*'})
            if status not in (200,201,204,412):
                raise StorageError('Report upload failed (HTTP '+str(status)+')')
        elif status!=200:
            raise StorageError('Report storage access failed (HTTP '+str(status)+')')
        self._verify(key,raw)
        return self.public_base+self._path(key)

    def publish_report(self,principal_scope,job_id,package,markdown):
        if not re.fullmatch(r'svc-[a-f0-9]{24}',principal_scope) or not re.fullmatch(r't01p1r-job-[a-f0-9]{32}',job_id):
            raise StorageError('Invalid report owner/job identity')
        attachments=[]
        for name,raw,media in [('report.zip',package,'application/zip'),('report.md',markdown.encode('utf-8'),'text/markdown; charset=utf-8')]:
            key='/'.join([self.prefix,principal_scope,job_id,digest(raw),name])
            url=self._put(key,raw,media)
            attachments.append({'fileName':name,'fileUrl':url,'mediaType':media,'sizeBytes':len(raw),'sha256':digest(raw)})
        return attachments

    def probe(self):
        key=self.prefix+'/_probes/'+uuid4().hex+'.txt'
        raw=('antigen-design storage connectivity probe '+uuid4().hex+'\n').encode()
        uploaded=False
        try:
            # The exact unique key may be cleaned even if the upload reply is lost.
            uploaded=True
            self._put(key,raw,'text/plain; charset=utf-8')
        finally:
            if uploaded:
                status,_,_=self._request('DELETE',key)
                if status not in (200,204):
                    raise StorageError('Storage probe cleanup failed (HTTP '+str(status)+'); object key: '+key)
        status,_,_=self._request('HEAD',key)
        if status!=404:
            raise StorageError('Storage probe deletion could not be confirmed')
        return {'status':'ready','bucket':self.bucket,'write_verified':True,'public_download_verified':True,'test_object_deleted':True}
