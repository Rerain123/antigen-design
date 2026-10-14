import errno
import os
import stat
from datetime import datetime, timezone

from biolib._internal.libs.fusepy import FUSE, FuseOSError, Operations
from biolib._shared.types.typing import Dict, List, Optional, TypedDict
from biolib.biolib_binary_format import LazyLoadedFile


class _AttributeDict(TypedDict):
    st_atime: int
    st_ctime: int
    st_gid: int
    st_mode: int
    st_mtime: int
    st_nlink: int
    st_size: int
    st_uid: int


class DataRecordFuseMount(Operations):
    def __init__(self, data_record):
        self._data_record = data_record
        self._files_map: Optional[Dict[str, LazyLoadedFile]] = None

    @staticmethod
    def mount_data_record(data_record, mount_path: str) -> None:
        os.makedirs(mount_path, exist_ok=True)
        FUSE(
            operations=DataRecordFuseMount(data_record),
            mountpoint=mount_path,
            nothreads=True,
            foreground=True,
            allow_other=False,
        )

    def getattr(self, path: str, fh=None) -> _AttributeDict:
        timestamp = self._get_created_at_epoch_seconds()
        if path == '/':
            return self._get_directory_attributes(timestamp_epoch_seconds=timestamp)

        path_in_record = path.lstrip('/')
        file = self._get_files_map().get(path_in_record)
        if file is not None:
            return self._get_file_attributes(timestamp_epoch_seconds=timestamp, size_in_bytes=file.length)

        directory_prefix = path_in_record + '/'
        if any(file_path.startswith(directory_prefix) for file_path in self._get_files_map()):
            return self._get_directory_attributes(timestamp_epoch_seconds=timestamp)

        raise FuseOSError(errno.ENOENT)  # No such file or directory

    def readdir(self, path: str, fh: int) -> List[str]:
        directory_prefix = '' if path == '/' else path.lstrip('/') + '/'
        depth = directory_prefix.count('/')
        entries = set(
            file_path.split('/')[depth] for file_path in self._get_files_map() if file_path.startswith(directory_prefix)
        )
        return ['.', '..', *entries]

    def read(self, path: str, size: int, offset: int, fh: int) -> bytes:
        file = self._get_files_map().get(path.lstrip('/'))
        if file is None:
            raise FuseOSError(errno.ENOENT)  # No such file or directory

        return file.get_data(start=offset, length=size)

    @staticmethod
    def _get_directory_attributes(timestamp_epoch_seconds: int) -> _AttributeDict:
        return _AttributeDict(
            st_atime=timestamp_epoch_seconds,
            st_ctime=timestamp_epoch_seconds,
            st_gid=os.getgid(),
            st_mode=stat.S_IFDIR | 0o555,  # Directory that is readable and executable by owner, group, and others.
            st_mtime=timestamp_epoch_seconds,
            st_nlink=1,
            st_size=1,
            st_uid=os.getuid(),
        )

    @staticmethod
    def _get_file_attributes(timestamp_epoch_seconds: int, size_in_bytes: int) -> _AttributeDict:
        return _AttributeDict(
            st_atime=timestamp_epoch_seconds,
            st_ctime=timestamp_epoch_seconds,
            st_gid=os.getgid(),
            st_mode=stat.S_IFREG | 0o444,  # Regular file with read permissions for owner, group, and others.
            st_mtime=timestamp_epoch_seconds,
            st_nlink=1,
            st_size=size_in_bytes,
            st_uid=os.getuid(),
        )

    def _get_created_at_epoch_seconds(self) -> int:
        version = self._data_record._get_version()  # pylint: disable=protected-access
        return int(datetime.fromisoformat(version['created_at'].rstrip('Z')).replace(tzinfo=timezone.utc).timestamp())

    def _get_files_map(self) -> Dict[str, LazyLoadedFile]:
        if self._files_map is None:
            self._files_map = {file.path: file for file in self._data_record.list_files()}

        return self._files_map
