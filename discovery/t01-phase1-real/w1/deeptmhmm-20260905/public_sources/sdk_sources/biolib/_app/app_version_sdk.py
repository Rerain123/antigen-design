import biolib.api
from biolib._app.skill import Skill, SkillState
from biolib._data_record.data_record import DataRecord
from biolib._shared.types import ResourceDetailedDict
from biolib._shared.types.typing import Optional
from biolib.api.client import ApiClient
from biolib.biolib_api_client.app_types import AppVersion
from biolib.biolib_logging import logger


class AppVersionSdk:
    def __init__(self, app_version: AppVersion, _api_client: Optional[ApiClient] = None) -> None:
        self._app_version = app_version
        self._api_client = _api_client or biolib.api.client

    def get_skill(self) -> Skill:
        description = self._app_version.get('app_description', '')
        if not description:
            logger.warning(f"App '{self._app_version['app_uri']}' does not have a short description set")
        return Skill(
            _internal_state=SkillState(app_version_uri=self._app_version['app_uri'], description=description),
            _api_client=self._api_client,
        )

    def get_assets(self) -> DataRecord:
        resource_dict: ResourceDetailedDict = self._api_client.get(
            path='/resource/',
            params={'uri': self._app_version['app_uri']},
        ).json()
        return DataRecord(_internal_state=resource_dict, _api_client=self._api_client)

    def set_as_published(self, published: bool = True) -> None:
        app_version_uuid = self._app_version['public_id']
        self._api_client.patch(
            path=f'/app_versions/{app_version_uuid}/',
            data={'set_as_published': published},
        )

    def set_as_default(self) -> None:
        app_version_uuid = self._app_version['public_id']
        self._api_client.patch(
            path=f'/app_versions/{app_version_uuid}/',
            data={'set_as_active': True},
        )
