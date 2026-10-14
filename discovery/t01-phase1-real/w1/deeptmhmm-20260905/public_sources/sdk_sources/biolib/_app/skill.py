import json

import biolib.api
from biolib._data_record.data_record import DataRecord
from biolib._internal.skill_content import build_arguments_json, build_code_example
from biolib._shared.types import ResourceDetailedDict
from biolib._shared.types.typing import Dict, List, Optional, TypedDict
from biolib._shared.utils import parse_resource_uri
from biolib.api.client import ApiClient
from biolib.biolib_logging import logger


class SkillState(TypedDict):
    app_version_uri: str
    description: str


class Skill:
    def __init__(self, _internal_state: SkillState, _api_client: Optional[ApiClient] = None) -> None:
        self._state = _internal_state
        self._api_client: ApiClient = _api_client or biolib.api.client

    @property
    def uri(self) -> str:
        return self._state['app_version_uri']

    @property
    def name(self) -> str:
        uri_parsed = parse_resource_uri(self._state['app_version_uri'])
        if not uri_parsed['resource_name']:
            raise ValueError(f"Expected URI '{self._state['app_version_uri']}' to contain a resource name")
        return uri_parsed['resource_name']

    @property
    def description(self) -> str:
        return self._state['description']

    def get_markdown(self) -> str:
        response = self._api_client.get(
            path='/resources/apps/index-detailed/',
            params={'uris': self._state['app_version_uri']},
        ).json()
        results = response.get('results', [])
        if not results:
            raise ValueError(f"No results found for URI '{self._state['app_version_uri']}'")
        active_version = results[0].get('active_version')
        if not active_version:
            raise ValueError(f"No active version found for URI '{self._state['app_version_uri']}'")

        description = active_version.get('description', '')
        example_notebooks: str = active_version.get('example_notebooks', '') or ''

        frontmatter = f"""\
---
name: {json.dumps(self.name, ensure_ascii=False, indent=None)}
description: {json.dumps(self.description, ensure_ascii=False, indent=None)}
---
"""

        content_parts = [frontmatter, description]
        if example_notebooks.startswith('assets://') and example_notebooks.endswith('.ipynb'):
            try:
                content_parts.append(self._load_notebook_from_assets(example_notebooks))
                return '\n\n'.join(content_parts)
            except Exception as error:
                logger.warning('Failed to load example notebook %s: %s', example_notebooks, error)

        arguments: List[Dict] = active_version.get('arguments', [])
        if arguments:
            content_parts.append(build_code_example(self._state['app_version_uri'], arguments))
            content_parts.append(build_arguments_json(arguments))

        return '\n\n'.join(content_parts)

    def _load_notebook_from_assets(self, example_notebooks: str) -> str:
        asset_path = example_notebooks[len('assets://') :]
        resource_dict: ResourceDetailedDict = self._api_client.get(
            path='/resource/',
            params={'uri': self._state['app_version_uri']},
        ).json()
        assets = DataRecord(_internal_state=resource_dict, _api_client=self._api_client)
        notebook_file = assets.get_file(asset_path)
        return notebook_file.get_data().decode('utf-8')
