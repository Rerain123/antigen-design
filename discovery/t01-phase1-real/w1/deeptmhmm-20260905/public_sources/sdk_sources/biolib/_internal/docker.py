import base64
import http.client
import json
import os
import socket
import urllib.parse

from biolib._shared.types.typing import Any, Dict, Generator, Optional, TypedDict, cast
from biolib.biolib_errors import BioLibError
from biolib.biolib_logging import logger


class DockerProgressDetail(TypedDict):
    current: int
    total: int


class DockerErrorDetail(TypedDict, total=False):
    message: str


class DockerStatusUpdate(TypedDict, total=False):
    status: str
    progressDetail: DockerProgressDetail
    progress: str
    id: str
    error: str
    errorDetail: DockerErrorDetail


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: int = 4000):
        super().__init__('localhost', timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._socket_path)


def _get_socket_path() -> str:
    docker_host = os.environ.get('DOCKER_HOST', 'unix:///var/run/docker.sock')
    if docker_host.startswith('unix://'):
        return docker_host[len('unix://') :]
    raise BioLibError(f'Unsupported DOCKER_HOST: {docker_host}. Only Unix sockets are supported.')


def _request(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 4000,
) -> http.client.HTTPResponse:
    conn = _UnixHTTPConnection(_get_socket_path(), timeout=timeout)
    all_headers: Dict[str, str] = {'Host': 'localhost'}
    if headers:
        all_headers.update(headers)
    conn.request(method, path, headers=all_headers)
    response = conn.getresponse()
    if response.status >= 400:
        body = response.read().decode()
        raise BioLibError(f'Docker API error ({response.status}): {body}')
    return response


def _stream_ndjson(
    method: str,
    path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 4000,
) -> Generator[DockerStatusUpdate, None, None]:
    conn = _UnixHTTPConnection(_get_socket_path(), timeout=timeout)
    all_headers: Dict[str, str] = {'Host': 'localhost'}
    if headers:
        all_headers.update(headers)
    conn.request(method, path, headers=all_headers)
    response = conn.getresponse()
    if response.status >= 400:
        body = response.read().decode()
        raise BioLibError(f'Docker API error ({response.status}): {body}')

    buffer = b''
    while True:
        chunk = response.read1(8192)
        if not chunk:
            break
        buffer += chunk
        while b'\n' in buffer:
            line, buffer = buffer.split(b'\n', 1)
            line = line.strip()
            if line:
                update = cast(DockerStatusUpdate, json.loads(line))
                logger.debug('Docker status update: %s', update)
                yield update

    if buffer.strip():
        update = cast(DockerStatusUpdate, json.loads(buffer))
        logger.debug('Docker status update: %s', update)
        yield update


def check_docker_running(timeout: int = 30) -> None:
    try:
        response = _request('GET', '/info', timeout=timeout)
        response.read()
    except Exception as error:
        raise BioLibError('Failed to connect to Docker, please make sure it is installed and running') from error


def pull_image(
    repository: str,
    tag: str,
    platform: str = 'linux/amd64',
    timeout: int = 4000,
) -> Generator[DockerStatusUpdate, None, None]:
    params = urllib.parse.urlencode({'fromImage': repository, 'tag': tag, 'platform': platform})
    yield from _stream_ndjson('POST', f'/images/create?{params}', timeout=timeout)


def get_image_info(name: str, timeout: int = 4000) -> Dict[str, Any]:
    encoded_name = urllib.parse.quote(name, safe='')
    response = _request('GET', f'/images/{encoded_name}/json', timeout=timeout)
    result: Dict[str, Any] = json.loads(response.read())
    return result


def tag_image(name: str, repo: str, tag: str, timeout: int = 4000) -> None:
    encoded_name = urllib.parse.quote(name, safe='')
    params = urllib.parse.urlencode({'repo': repo, 'tag': tag})
    response = _request('POST', f'/images/{encoded_name}/tag?{params}', timeout=timeout)
    response.read()


def push_image(
    repository: str,
    tag: str,
    auth_config: Dict[str, str],
    timeout: int = 4000,
) -> Generator[DockerStatusUpdate, None, None]:
    encoded_repo = urllib.parse.quote(repository, safe='')
    params = urllib.parse.urlencode({'tag': tag})
    auth_header = base64.urlsafe_b64encode(json.dumps(auth_config).encode()).decode()
    headers = {'X-Registry-Auth': auth_header}
    yield from _stream_ndjson('POST', f'/images/{encoded_repo}/push?{params}', headers=headers, timeout=timeout)
