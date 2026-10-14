import re
from urllib.parse import urlparse

import biolib.utils
from biolib._shared.types.typing import Optional, Tuple


def parse_result_id_or_url(
    result_id_or_url: str,
    default_token: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    result_id_or_url = result_id_or_url.strip()

    if '/' not in result_id_or_url:
        return (result_id_or_url, default_token)

    if not result_id_or_url.startswith('http://') and not result_id_or_url.startswith('https://'):
        result_id_or_url = 'https://' + result_id_or_url

    parsed_url = urlparse(result_id_or_url)

    expected_base_url = base_url or biolib.utils.BIOLIB_BASE_URL
    if expected_base_url:
        expected_base = urlparse(expected_base_url)
        if parsed_url.scheme != expected_base.scheme or parsed_url.netloc != expected_base.netloc:
            raise ValueError(f'URL must start with {expected_base_url}, got: {result_id_or_url}')

    pattern = r'/results?/(?P<uuid>[a-f0-9-]+)/?(?:\?token=(?P<token>[^&]+))?'
    match = re.search(pattern, result_id_or_url, re.IGNORECASE)

    if not match:
        raise ValueError(f'URL must be in format <base_url>/results/<UUID>/?token=<token>, got: {result_id_or_url}')

    uuid = match.group('uuid')
    token = match.group('token') or default_token

    return (uuid, token)
