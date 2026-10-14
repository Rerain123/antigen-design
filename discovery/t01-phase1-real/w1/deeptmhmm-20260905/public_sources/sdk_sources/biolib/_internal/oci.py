import base64
import json
import os
import urllib.parse
import urllib.request

from biolib import utils
from biolib._internal.http_client import HttpClient, HttpError
from biolib._shared.types.typing import Any, Dict, List
from biolib.biolib_errors import BioLibError
from biolib.biolib_logging import logger


class _OciNoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        logger.debug(f'Suppressing redirect ({code}) from {req.full_url} to {newurl}')
        return None


class _OciProxyRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request:
        parsed = urllib.parse.urlparse(newurl)
        logger.debug(f'Received redirect ({code}) from {req.full_url} to {newurl}')
        if not parsed.path.startswith('/biolib-image-registry/'):
            raise BioLibError(f'Unexpected redirect ({code}) from {req.full_url} to {newurl}')

        # Push from within app requires rewrite to proxy, but for simplicity we do it always for OCI push
        query = f'?{parsed.query}' if parsed.query else ''
        rewritten_url = f'{utils.BIOLIB_BASE_URL}/api/proxy/storage{parsed.path}{query}'
        logger.debug(f'Rewriting redirect to proxy: {rewritten_url}')
        # Strip auth header as S3 presigned URL contains its own credentials in query params
        redirect_headers = {k: v for k, v in req.headers.items() if k.lower() != 'authorization'}
        new_req = urllib.request.Request(
            url=rewritten_url,
            headers=redirect_headers,
            method=req.get_method(),
        )
        new_req.data = req.data
        if req.data and hasattr(req.data, 'seek'):
            req.data.seek(0)  # type: ignore[union-attr]
        # Re-add Content-Length removed by the Request.data setter
        if 'Content-length' in redirect_headers:
            new_req.add_header('Content-length', redirect_headers['Content-length'])
        return new_req


def _push_blob(
    oci_path: str,
    repository: str,
    descriptor: Dict[str, Any],
    auth_header: str,
) -> None:
    digest = str(descriptor['digest'])

    try:
        HttpClient.request(
            method='HEAD',
            url=f'{utils.BIOLIB_BASE_URL}/v2/{repository}/blobs/{digest}',
            headers={'Authorization': auth_header},
            redirect_handler=_OciNoRedirectHandler,
        )
        logger.debug(f'Blob {digest} already exists in registry, skipping upload.')
        return
    except HttpError as error:
        if error.code == 404:
            logger.debug(f'Blob {digest} not found in registry, uploading.')
        elif error.code == 307:
            # Registry redirects HEAD to S3 when blob exists
            logger.debug(f'Blob {digest} already exists in registry (redirect), skipping upload.')
            return
        else:
            raise

    post_resp = HttpClient.request(
        method='POST',
        url=f'{utils.BIOLIB_BASE_URL}/v2/{repository}/blobs/uploads/',
        headers={'Authorization': auth_header, 'Content-Length': '0'},
        data=b'',
        redirect_handler=_OciProxyRedirectHandler,
    )
    if post_resp.status_code != 202:
        raise BioLibError(f'Failed to start blob upload: HTTP {post_resp.status_code}')

    location = next((v for k, v in post_resp.headers.items() if k.lower() == 'location'), '')
    logger.debug(f'Blob upload location: {location}')
    location_path = urllib.parse.urlparse(location).path if location else ''
    if not location_path:
        raise BioLibError(f'Registry did not return a valid Location header for blob upload of {digest}')
    query = urllib.parse.urlparse(location).query
    separator = '&' if query else '?'
    base_query = f'?{query}' if query else ''
    upload_url = (
        f'{utils.BIOLIB_BASE_URL}{location_path}{base_query}{separator}digest={urllib.parse.quote(digest, safe=":")}'
    )
    logger.debug(f'Blob upload URL: {upload_url}')

    blob_path = os.path.join(oci_path, 'blobs', digest.replace(':', os.sep))

    HttpClient.request(
        method='PUT',
        url=upload_url,
        data_file_path=blob_path,
        headers={'Authorization': auth_header},
        timeout_in_seconds=4000,
        redirect_handler=_OciProxyRedirectHandler,
    )


def push_oci_image_to_registry(
    oci_path: str,
    repository: str,
    tag: str,
    username: str,
    password: str,
) -> int:
    assert utils.BIOLIB_BASE_URL is not None, 'BIOLIB_BASE_URL must be set before pushing OCI images'

    with open(os.path.join(oci_path, 'index.json')) as f:
        index: Dict[str, Any] = json.load(f)

    manifests = index.get('manifests')
    if not manifests:
        raise BioLibError(f'OCI index.json contains no manifests: {oci_path}')

    manifest_digest = manifests[0]['digest']
    manifest_blob = os.path.join(oci_path, 'blobs', manifest_digest.replace(':', os.sep))
    with open(manifest_blob) as f:
        manifest: Dict[str, Any] = json.load(f)

    if 'config' not in manifest:
        raise BioLibError(
            'The OCI image appears to be a multi-platform image index rather than a single manifest. '
            'Please build a single-platform image with --platform linux/amd64.'
        )

    with open(manifest_blob, 'rb') as f:
        manifest_bytes = f.read()

    config_digest = manifest['config']['digest']
    with open(os.path.join(oci_path, 'blobs', config_digest.replace(':', os.sep))) as f:
        config: Dict[str, Any] = json.load(f)

    architecture = config.get('architecture', 'unknown')
    if architecture != 'amd64':
        raise BioLibError(
            f'OCI image is compiled for {architecture}, expected x86 (amd64). '
            'If you are on an ARM processor, try passing --platform linux/amd64 to your build tool.'
        )

    auth_header = 'Basic ' + base64.b64encode(f'{username}:{password}'.encode()).decode()

    descriptors: List[Dict[str, Any]] = [manifest['config']] + manifest.get('layers', [])
    total_size = 0
    for i, desc in enumerate(descriptors):
        blob_path = os.path.join(oci_path, 'blobs', str(desc['digest']).replace(':', os.sep))
        total_size += os.path.getsize(blob_path)
        logger.info(f'Pushing blob {i + 1}/{len(descriptors)}...')
        _push_blob(oci_path, repository, desc, auth_header)

    media_type = manifest.get('mediaType', 'application/vnd.oci.image.manifest.v1+json')
    HttpClient.request(
        method='PUT',
        url=f'{utils.BIOLIB_BASE_URL}/v2/{repository}/manifests/{tag}',
        data=manifest_bytes,
        headers={
            'Authorization': auth_header,
            'Content-Type': media_type,
            'Content-Length': str(len(manifest_bytes)),
        },
        redirect_handler=_OciProxyRedirectHandler,
    )

    logger.info(f'Successfully pushed OCI image to {repository}:{tag}')
    return total_size
