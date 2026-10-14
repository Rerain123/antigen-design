import json
import logging
import os
import sys
from typing import Dict, List

from biolib import biolib_errors
from biolib._data_record.data_record import DataRecord
from biolib._internal import cli
from biolib._shared.types.typing import Optional
from biolib.biolib_errors import FileMaxCountExceededError
from biolib.biolib_logging import logger, logger_no_user_data


@cli.group(help='Manage Large File Systems', hidden=True)
def lfs() -> None:
    pass


@lfs.command(help='Create a Large File System')
@cli.argument('uri', required=True)
def create(uri: str) -> None:
    logger.warning('This is command deprecated, please use "biolib data-record create" instead.')
    logger.configure(default_log_level=logging.INFO)
    logger_no_user_data.configure(default_log_level=logging.INFO)
    DataRecord.create(destination=uri)


@lfs.command(help='Push a new version of a Large File System')
@cli.argument('uri', required=True)
@cli.option('--path', required=True, type=cli.Path(exists=True))
@cli.option('--chunk-size', default=None, required=False, type=cli.INT, help='The size of each chunk (In MB)')
def push(uri: str, path: str, chunk_size: Optional[int]) -> None:
    logger.warning('This is command deprecated, please use "biolib data-record update" instead.')
    logger.configure(default_log_level=logging.INFO)
    logger_no_user_data.configure(default_log_level=logging.INFO)
    try:
        DataRecord.get_by_uri(uri=uri).update(data_path=path, chunk_size_in_mb=chunk_size)
    except biolib_errors.BioLibError as error:
        print(f'An error occurred:\n{error.message}', file=sys.stderr)
        exit(1)


@lfs.command(help='Download a file from a Large File System')
@cli.argument('uri', required=True)
@cli.option('--file-path', required=True, type=str)
def download_file(uri: str, file_path: str) -> None:
    logger.warning('This is command deprecated, please use "biolib data-record download" instead.')
    logger.configure(default_log_level=logging.INFO)
    logger_no_user_data.configure(default_log_level=logging.INFO)
    try:
        record = DataRecord.get_by_uri(uri=uri)
        try:
            file_obj = [file_obj for file_obj in record.list_files() if file_obj.path == file_path][0]
        except IndexError:
            raise Exception('File not found in data record') from None

        assert not os.path.exists(file_obj.name), 'File already exists in current directory'
        with open(file_obj.name, 'wb') as file_handle:
            file_handle.write(file_obj.get_data())

    except biolib_errors.BioLibError as error:
        print(f'An error occurred:\n{error.message}', file=sys.stderr)
        exit(1)


@lfs.command(help='Describe a Large File System')
@cli.argument('uri', required=True)
@cli.option('--json', 'output_as_json', is_flag=True, default=False, required=False, help='Format output as JSON')
@cli.option(
    '--max-count',
    default=100_000,
    required=False,
    type=cli.INT,
    help='Maximum number of files to list (use 0 for unlimited)',
)
def describe(uri: str, output_as_json: bool, max_count: int) -> None:
    logger.warning('This is command deprecated, please use "biolib data-record describe" instead.')
    data_record = DataRecord.get_by_uri(uri)
    files_info: List[Dict] = []
    total_size_in_bytes = 0
    effective_max_count = max_count if max_count > 0 else None
    try:
        for file in data_record.list_files(max_count=effective_max_count):
            files_info.append({'path': file.path, 'size_bytes': file.length})
            total_size_in_bytes += file.length
    except FileMaxCountExceededError as error:
        raise SystemExit(
            f'Error: More than {error.max_count} files in data record. Use --max-count to set a higher limit.'
        ) from None

    if output_as_json:
        print(
            json.dumps(
                obj={'uri': data_record.uri, 'size_bytes': total_size_in_bytes, 'files': files_info},
                indent=4,
            )
        )
    else:
        print(f'Large File System {data_record.uri}\ntotal {total_size_in_bytes} bytes\n')
        print('size bytes    path')
        for file_info in files_info:
            size_string = str(file_info['size_bytes'])
            leading_space_string = ' ' * (10 - len(size_string))
            print(f'{leading_space_string}{size_string}    {file_info["path"]}')
