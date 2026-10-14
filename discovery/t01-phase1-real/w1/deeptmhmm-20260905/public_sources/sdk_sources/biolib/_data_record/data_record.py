import os
from collections import namedtuple
from datetime import datetime
from pathlib import Path
from struct import Struct
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Union, cast

from biolib import api
from biolib._internal.data_record.data_record import validate_sqlite_v1
from biolib._internal.data_record.push_data import (
    _upload_from_iterator,
    push_data_path,
    validate_data_path_and_get_files_and_size_of_directory,
)
from biolib._internal.data_record.remote_storage_endpoint import DataRecordRemoteStorageEndpoint
from biolib._internal.http_client import HttpClient, HttpError
from biolib._shared import types
from biolib._shared.types import ResourceDetailedDict, ResourceVersionDetailedDict, ZipFileNodeDict
from biolib._shared.utils import parse_resource_uri
from biolib.api import client as api_client
from biolib.api.client import ApiClient
from biolib.biolib_api_client import BiolibApiClient
from biolib.biolib_api_client.biolib_app_api import _get_resource_uri_from_str
from biolib.biolib_api_client.lfs_types import DataRecordInfo
from biolib.biolib_binary_format import LazyLoadedFile
from biolib.biolib_binary_format.utils import RemoteIndexableBuffer
from biolib.biolib_errors import BioLibError, FileMaxCountExceededError
from biolib.biolib_logging import logger

PathFilter = Union[str, List[str], Callable[[str], bool]]

_VISIBILITY_UPDATES: Dict[str, Dict[str, Union[str, bool]]] = {
    'discoverable': {'state': 'public', 'is_unlisted': False},
    'unlisted': {'state': 'public', 'is_unlisted': True},
    'private': {'state': 'draft', 'is_unlisted': False},
}


class DataRecord:
    """A versioned data record on BioLib.

    Note:
        Do not instantiate this class directly. Use :func:`biolib.get_data_record` to obtain a data record
        instance::

            >>> record = biolib.get_data_record('biolib/sequences:1.0.0')
    """

    def __init__(self, _internal_state: ResourceDetailedDict, _api_client: Optional[ApiClient] = None):
        self._state = _internal_state
        self._api_client: ApiClient = _api_client or api_client

    def __repr__(self):
        return f'DataRecord: {self._state["uri"]}'

    @property
    def uri(self) -> str:
        return self._state['uri']

    @property
    def uuid(self) -> str:
        return self._state['uuid']

    @property
    def name(self) -> str:
        uri_parsed = parse_resource_uri(self._state['uri'], use_account_as_name_default=False)
        if not uri_parsed['resource_name']:
            raise ValueError('Expected parameter "resource_uri" to contain resource name')

        return uri_parsed['resource_name']

    @staticmethod
    def get_by_uri(uri: str, _api_client: Optional[ApiClient] = None) -> 'DataRecord':
        client = _api_client or api_client
        normalized_uri = _get_resource_uri_from_str(uri)
        try:
            resource_dict: ResourceDetailedDict = client.get(path='/resource/', params={'uri': normalized_uri}).json()
        except HttpError as error:
            raise BioLibError(f'Failed to get data record "{uri}". Error: {error}') from error

        if resource_dict['type'] != 'data-record':
            raise Exception(f'Resource "{resource_dict["uri"]}" is not a Data Record')

        return DataRecord(_internal_state=resource_dict, _api_client=_api_client)

    @staticmethod
    def create(destination: str, data_path: Optional[str] = None, record_type: Optional[str] = None) -> 'DataRecord':
        BiolibApiClient.assert_is_signed_in(authenticated_action_description='create a Data Record')
        if data_path is not None:
            assert os.path.isdir(data_path), f'The path "{data_path}" is not a directory.'
        uri_parsed = parse_resource_uri(destination, use_account_as_name_default=False)
        if uri_parsed['resource_name_normalized']:
            data_record_uri = destination
        else:
            record_name = 'data-record-' + datetime.now().isoformat().split('.')[0].replace(':', '-')
            data_record_uri = f'{destination}/{record_name}'

        try:
            response = api.client.post(
                path='/resources/data-records/',
                data={
                    'uri': data_record_uri,
                    'type': record_type,
                },
            )
        except HttpError as error:
            raise BioLibError(f'Failed to create data record "{data_record_uri}". Error: {error}') from error
        data_record_info: DataRecordInfo = response.json()
        logger.info(f"Successfully created new Data Record '{data_record_info['uri']}'")

        data_record = DataRecord.get_by_uri(uri=data_record_info['uri'])
        if data_path is not None:
            data_record.update(data_path=data_path)

        return data_record

    @staticmethod
    def fetch(uri: Optional[str] = None, count: Optional[int] = None) -> List['DataRecord']:
        # TODO: Simplify when backend exposes /api/resources/ instead of /api/apps/
        max_page_size = 1_000
        params: Dict[str, Union[str, int]] = {
            'page_size': str(count or max_page_size),
            'resource_type': 'data-record',
        }
        if uri:
            uri_parsed = parse_resource_uri(uri, use_account_as_name_default=False)
            params['account_handle'] = uri_parsed['account_handle_normalized']
            if uri_parsed['resource_name_normalized']:
                params['app_name'] = uri_parsed['resource_name_normalized']

        results = api_client.get(path='/apps/', params=params).json()['results']
        if count is None and len(results) == max_page_size:
            logger.warning(
                f'Fetch results exceeded maximum count of {max_page_size}. Some data records might not be fetched.'
            )

        return [
            DataRecord(
                _internal_state=ResourceDetailedDict(
                    uri=result['resource_uri'],
                    uuid=result['public_id'],
                    name=result['name'],
                    created_at=result['created_at'],
                    type=result['type'],
                    description=result['description'],
                    account_uuid=result['account_id'],
                    experiment=None,
                )
            )
            for result in results
        ]

    @staticmethod
    def clone(
        source: 'DataRecord',
        destination: 'DataRecord',
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> 'DataRecord':
        BiolibApiClient.assert_is_signed_in(authenticated_action_description='clone a Data Record')

        # pylint: disable=protected-access
        total_size_in_bytes = source._get_zip_size_bytes()

        if total_size_in_bytes == 0:
            raise ValueError('Source data record has no data to clone')

        min_chunk_size_bytes = 10_000_000
        chunk_size_in_bytes = max(min_chunk_size_bytes, int(total_size_in_bytes / 9_000))

        zip_iterator = source._iter_zip_bytes(chunk_size_bytes=chunk_size_in_bytes)

        new_resource_version_uuid = _upload_from_iterator(
            resource_uuid=destination._state['uuid'],
            payload_iterator=zip_iterator,
            payload_size_in_bytes=total_size_in_bytes,
            publish=True,
            on_progress=on_progress,
        )
        # pylint: enable=protected-access

        cloned_record = DataRecord._get_by_version_uuid(new_resource_version_uuid)
        logger.info(f"Successfully cloned data to '{cloned_record.uri}'")
        return cloned_record

    def list_files(
        self,
        path_filter: Optional[PathFilter] = None,
        max_count: Optional[int] = 100_000,
    ) -> List[LazyLoadedFile]:
        files = list(
            self._fetch_files(
                path_filter=path_filter,
                max_count=max_count + 1 if max_count is not None else None,
            )
        )

        if max_count is not None and len(files) > max_count:
            raise FileMaxCountExceededError(max_count=max_count)

        return files

    def get_file(self, path: str) -> LazyLoadedFile:
        try:
            files = self.list_files(path_filter=path, max_count=1)
        except FileMaxCountExceededError:
            raise FileNotFoundError(f'Multiple files matched the path: {path}') from None
        if not files:
            raise FileNotFoundError(f'File not found in data record: {path}')
        return files[0]

    def mount_files(self, mount_path: str) -> None:
        try:
            # Only attempt to import FUSE dependencies when strictly necessary
            from biolib._internal.fuse_mount import (  # pylint: disable=import-outside-toplevel
                DataRecordFuseMount as _DataRecordFuseMount,
            )
        except ImportError as error:
            raise ImportError(
                'Failed to import FUSE mounting utils. Please ensure FUSE is installed on your system.'
            ) from error

        _DataRecordFuseMount.mount_data_record(data_record=self, mount_path=mount_path)

    def download_zip(self, output_path: str):
        remote_storage_endpoint = DataRecordRemoteStorageEndpoint(uri=self.uri, _api_client=self._api_client)
        HttpClient.request(url=remote_storage_endpoint.get_remote_url(), response_path=output_path)

    def download_files(
        self,
        output_dir: str,
        path_filter: Optional[PathFilter] = None,
        max_count: Optional[int] = 100_000,
    ) -> None:
        filtered_files = self.list_files(path_filter=path_filter, max_count=max_count)

        if len(filtered_files) == 0:
            logger.debug('No files to save')
            return

        for file in filtered_files:
            file_path = os.path.join(output_dir, file.path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, mode='wb') as file_handle:
                for chunk in file.get_data_iterator():
                    file_handle.write(chunk)

    def save_files(
        self,
        output_dir: str,
        path_filter: Optional[PathFilter] = None,
        max_count: Optional[int] = 100_000,
    ) -> None:
        self.download_files(output_dir=output_dir, path_filter=path_filter, max_count=max_count)

    def update(self, data_path: str, chunk_size_in_mb: Optional[int] = None) -> None:
        BiolibApiClient.assert_is_signed_in(authenticated_action_description='push data to a Data Record')
        files_to_zip, data_size_in_bytes = validate_data_path_and_get_files_and_size_of_directory(data_path)

        # validate data record
        detailed_dict: types.DataRecordDetailedDict = self._get_detailed_dict()
        if detailed_dict['type']:
            # only validate if data record has a type
            data_record_type: types.DataRecordTypeDict = detailed_dict['type']
            logger.info(f'Validating data record of type {data_record_type["name"]}')
            for rule in data_record_type['validation_rules']:
                logger.info(f'Validating rule {rule["type"]} for {rule["path"]}...')
                if rule['type'] == 'sqlite-v1':
                    try:
                        validate_sqlite_v1(schema=rule['rule'], sqlite_file=Path(rule['path']))
                    except Exception as error:
                        raise Exception('Data Record Validation failed') from error
                else:
                    raise Exception(f'Error processing data record validation: unknown rule type {rule["type"]}')

        new_resource_version_uuid = push_data_path(
            data_path=data_path,
            data_size_in_bytes=data_size_in_bytes,
            files_to_zip=files_to_zip,
            resource_uuid=self._state['uuid'],
            chunk_size_in_mb=chunk_size_in_mb,
            publish=True,
        )

        updated_record = DataRecord._get_by_version_uuid(new_resource_version_uuid, _api_client=self._api_client)
        self._state = updated_record._state  # pylint: disable=protected-access
        logger.info(f"Successfully pushed a new Data Record version '{self.uri}'")

    def configure(self, visibility: Optional[str] = None) -> None:
        """Configure the settings of the data record.

        :param visibility: Who can access and discover the data record. One of "discoverable", "unlisted" or "private"

        Example::
            >>> record = DataRecord.get_by_uri("account/data-record")
            >>> record.configure(visibility="unlisted")
        """
        BiolibApiClient.assert_is_signed_in(authenticated_action_description='configure a Data Record')
        if visibility is None:
            raise ValueError('No settings to configure were given')

        updates = _VISIBILITY_UPDATES.get(visibility)
        if updates is None:
            raise ValueError(f'Invalid visibility "{visibility}". Valid choices are: {", ".join(_VISIBILITY_UPDATES)}')

        try:
            self._api_client.patch(path=f'/resources/{self.uuid}/', data=updates)
        except Exception as error:
            raise BioLibError(f'Failed to configure data record {self.uri} due to: {error}') from error

        logger.info(f'Visibility of data record {self.uri} is now "{visibility}"')

    def delete(self) -> None:
        """Delete the data record.

        Example::
            >>> record = DataRecord.get_by_uri("account/data-record")
            >>> record.delete()
        """
        try:
            self._api_client.delete(path=f'/apps/{self.uuid}/')
            logger.info(f'Data record {self.uri} deleted')
        except Exception as error:
            raise Exception(f'Failed to delete data record {self.uri} due to: {error}') from error

    @staticmethod
    def _get_by_version_uuid(version_uuid: str, _api_client: Optional[ApiClient] = None) -> 'DataRecord':
        client = _api_client or api_client
        response = client.get(path=f'/lfs/versions/{version_uuid}/')
        version_info = response.json()
        return DataRecord.get_by_uri(version_info['uri'], _api_client=_api_client)

    @staticmethod
    def _get_file(
        remote_storage_endpoint: DataRecordRemoteStorageEndpoint,
        file_node_dict: ZipFileNodeDict,
    ) -> LazyLoadedFile:
        local_file_header_signature_bytes = b'\x50\x4b\x03\x04'
        local_file_header_struct = Struct('<H2sHHHIIIHH')
        LocalFileHeader = namedtuple(
            'LocalFileHeader',
            (
                'version',
                'flags',
                'compression_raw',
                'mod_time',
                'mod_date',
                'crc_32_expected',
                'compressed_size_raw',
                'uncompressed_size_raw',
                'file_name_len',
                'extra_field_len',
            ),
        )

        local_file_header_start = file_node_dict['zip_meta']['header_start'] + len(local_file_header_signature_bytes)
        local_file_header_end = local_file_header_start + local_file_header_struct.size

        def file_start_func() -> int:
            local_file_header_response = HttpClient.request(
                url=remote_storage_endpoint.get_remote_url(),
                headers={'range': f'bytes={local_file_header_start}-{local_file_header_end - 1}'},
                timeout_in_seconds=300,
            )
            local_file_header = LocalFileHeader._make(
                local_file_header_struct.unpack(local_file_header_response.content)
            )
            file_start: int = (
                local_file_header_end + local_file_header.file_name_len + local_file_header.extra_field_len
            )
            return file_start

        return LazyLoadedFile(
            buffer=RemoteIndexableBuffer(endpoint=remote_storage_endpoint),
            length=file_node_dict['zip_meta']['size_on_disk'],
            path=file_node_dict['dir_path'] + file_node_dict['name'],
            start=None,
            start_func=file_start_func,
        )

    def _get_version(self) -> ResourceVersionDetailedDict:
        if 'version' not in self._state:
            # Version might be missing in state if initialized from the fetch method (list of data records)
            self._state = self.get_by_uri(self.uri, _api_client=self._api_client)._state

        version = self._state.get('version')
        if version is None:
            raise Exception(f'Data Record "{self._state["uri"]}" has no active version')

        return version

    def _fetch_files(
        self,
        max_count: Optional[int],
        path_filter: Optional[PathFilter] = None,
    ) -> Iterable[LazyLoadedFile]:
        if path_filter and not (isinstance(path_filter, (str, list)) or callable(path_filter)):
            raise Exception('Expected path_filter to be a string, a list of strings or a function')

        path_filters = (
            [path_filter] if isinstance(path_filter, str) else path_filter if isinstance(path_filter, list) else []
        )

        version = self._get_version()
        resource_version_uuid = version['uuid']
        remote_storage_endpoint = DataRecordRemoteStorageEndpoint(uri=self.uri, _api_client=self._api_client)

        page: Optional[int] = 1
        yielded_files: int = 0
        while page:
            response = self._api_client.post(
                path=f'/proxy/files/data-record-versions/{resource_version_uuid}/query/',
                data=dict(page=page, page_size=1_000, path_filters=path_filters),
            ).json()

            for file_node_dict in cast(List[ZipFileNodeDict], response['results']):
                if file_node_dict['is_dir']:
                    continue

                if callable(path_filter) and not path_filter(file_node_dict['dir_path'] + file_node_dict['name']):
                    continue

                yield self._get_file(remote_storage_endpoint, file_node_dict)
                yielded_files += 1

                if max_count is not None and yielded_files >= max_count:
                    page = None
                    break

            page = page + 1 if page is not None and response['page_count'] > page else None

    def _get_detailed_dict(self) -> types.DataRecordDetailedDict:
        return cast(types.DataRecordDetailedDict, self._api_client.get(f'/resources/data-records/{self.uuid}/').json())

    def _get_zip_size_bytes(self) -> int:
        remote_storage_endpoint = DataRecordRemoteStorageEndpoint(uri=self.uri, _api_client=self._api_client)
        presigned_url = remote_storage_endpoint.get_remote_url()
        response = HttpClient.request(url=presigned_url, headers={'range': 'bytes=0-0'})
        content_range = response.headers.get('Content-Range', '')
        if not content_range or '/' not in content_range:
            raise ValueError('Unable to determine zip size: Content-Range header missing or invalid')
        total_size = int(content_range.split('/')[1])
        return total_size

    def _iter_zip_bytes(self, chunk_size_bytes: int) -> Iterator[bytes]:
        remote_storage_endpoint = DataRecordRemoteStorageEndpoint(uri=self.uri, _api_client=self._api_client)
        presigned_url = remote_storage_endpoint.get_remote_url()
        response = HttpClient.request(url=presigned_url, headers={'range': 'bytes=0-0'})
        content_range = response.headers.get('Content-Range', '')
        if not content_range or '/' not in content_range:
            raise ValueError('Unable to determine zip size: Content-Range header missing or invalid')
        total_size = int(content_range.split('/')[1])

        for start in range(0, total_size, chunk_size_bytes):
            end = min(start + chunk_size_bytes - 1, total_size - 1)
            presigned_url = remote_storage_endpoint.get_remote_url()
            response = HttpClient.request(
                url=presigned_url,
                headers={'range': f'bytes={start}-{end}'},
                timeout_in_seconds=300,
            )
            yield response.content
