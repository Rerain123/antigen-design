import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from biolib._shared.types import ResourceDetailedDict
from biolib._shared.types.typing import Optional
from biolib.api import client as api_client
from biolib.api.client import ApiClient
from biolib.biolib_binary_format.utils import RemoteEndpoint
from biolib.biolib_logging import logger


class DataRecordRemoteStorageEndpoint(RemoteEndpoint):
    def __init__(self, uri: str, _api_client: Optional[ApiClient] = None):
        self._uri: str = uri
        self._api_client: ApiClient = _api_client or api_client
        self._expires_at: Optional[datetime] = None
        self._presigned_url: Optional[str] = None

    def get_remote_url(self) -> str:
        if not self._presigned_url or not self._expires_at or datetime.now(timezone.utc) > self._expires_at:
            resource_response: ResourceDetailedDict = self._api_client.get(
                path='/resource/',
                params={'uri': self._uri},
            ).json()

            version = resource_response.get('version')
            assets = version.get('assets') if version else None
            if not assets:
                raise Exception(f'Resource "{self._uri}" has no downloadable assets')

            download_url = assets['download_url']
            app_caller_proxy_job_storage_base_url = os.getenv('BIOLIB_CLOUD_JOB_STORAGE_BASE_URL', '')
            if app_caller_proxy_job_storage_base_url:
                parsed_url = urlparse(download_url)
                self._presigned_url = f'{app_caller_proxy_job_storage_base_url}{parsed_url.path}?{parsed_url.query}'
            else:
                self._presigned_url = download_url

            self._expires_at = datetime.now(timezone.utc) + timedelta(minutes=8)
            logger.debug(
                f'DataRecord "{self._uri}" fetched presigned URL with expiry at {self._expires_at.isoformat()}'
            )

        return self._presigned_url
