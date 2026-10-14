import base64
import binascii
import json
from typing import Any, Dict, cast

from biolib._internal.http_client import HttpClient
from biolib.biolib_errors import BioLibError


class JwtDecodeError(Exception):
    pass


def _urlsafe_b64decode_with_restored_padding(segment: bytes) -> bytes:
    padding = b'=' * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def decode_jwt_without_checking_signature(jwt: str) -> Dict[str, Any]:
    jwt_bytes = jwt.encode('utf-8')

    try:
        signing_input, _ = jwt_bytes.rsplit(b'.', 1)
        header_segment, payload_segment = signing_input.split(b'.', 1)
    except ValueError as error:
        raise JwtDecodeError('Not enough segments') from error

    try:
        header_data = _urlsafe_b64decode_with_restored_padding(header_segment)
    except (TypeError, binascii.Error) as error:
        raise JwtDecodeError('Invalid header padding') from error

    try:
        header = json.loads(header_data)
    except ValueError as error:
        raise JwtDecodeError(f'Invalid header string: {error}') from error

    if not isinstance(header, dict):
        raise JwtDecodeError('Invalid header string: must be a json object')

    try:
        payload_data = _urlsafe_b64decode_with_restored_padding(payload_segment)
    except (TypeError, binascii.Error) as error:
        raise JwtDecodeError('Invalid payload padding') from error

    try:
        payload = json.loads(payload_data)
    except ValueError as error:
        raise JwtDecodeError(f'Invalid payload string: {error}') from error

    if not isinstance(payload, dict):
        raise JwtDecodeError('Invalid payload string: must be a json object')

    return dict(header=header, payload=payload)


def exchange_azure_oauth_token_for_biolib_refresh_token(azure_oauth_access_token: str, base_url: str) -> str:
    response = HttpClient.request(
        method='POST',
        url=f'{base_url}/api/sso/enterprise/azure_oauth/signin/',
        data={'access_token': azure_oauth_access_token},
    )
    response_dict = response.json()
    auth_tokens = response_dict.get('auth_tokens')
    if not auth_tokens or 'refresh' not in auth_tokens:
        raise BioLibError('Failed to exchange Azure OAuth access token for BioLib auth tokens')

    return cast(str, auth_tokens['refresh'])
