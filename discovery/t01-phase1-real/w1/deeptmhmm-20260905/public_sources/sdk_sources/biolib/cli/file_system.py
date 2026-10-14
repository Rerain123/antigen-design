import logging
from collections import OrderedDict

from biolib import api
from biolib._internal import cli
from biolib._internal.tables import BioLibTable
from biolib._shared.types import UserDetailedDict
from biolib._shared.types.typing import Dict, Union
from biolib.biolib_api_client import BiolibApiClient
from biolib.biolib_logging import logger, logger_no_user_data


@cli.group(help='Manage File Systems', hidden=True)
def file_system() -> None:
    logger.configure(default_log_level=logging.INFO)
    logger_no_user_data.configure(default_log_level=logging.INFO)


@file_system.command(help='Create a File System')
@cli.argument('uri', required=True)
@cli.option('--size-in-gib', required=True, type=cli.INT, help='Size of the File System in GiB')
def create(uri: str, size_in_gib: int) -> None:
    BiolibApiClient.assert_is_signed_in(authenticated_action_description='create a File System')
    response = api.client.post(
        path='/resources/file-systems/',
        data={'uri': uri, 'size_in_gib': size_in_gib},
        retries=0,
    )
    logger.info(f'Successfully created File System {response.json()["uri"]}')


@file_system.command(name='list', help='List File Systems of your account')
def list_file_systems() -> None:
    BiolibApiClient.assert_is_signed_in(authenticated_action_description='list File Systems')
    user: UserDetailedDict = api.client.get(path='/users/me/').json()
    params: Dict[str, Union[str, int]] = {
        'account_handle': user['account']['handle'],
        'page_size': 100,
        'resource_type': 'file-system',
    }
    response = api.client.get(path='/apps/', params=params).json()
    results = list(response['results'])
    for page_number in range(2, response['page_count'] + 1):
        page_response = api.client.get(path='/apps/', params=dict(**params, page=page_number)).json()
        results.extend(page_response['results'])

    BioLibTable(
        columns_to_row_map=OrderedDict(
            {
                'URI': {'key': 'resource_uri', 'params': {}},
                'Created At': {'key': 'created_at', 'params': {}},
            }
        ),
        rows=results,
        title='File Systems',
    ).print_table()
