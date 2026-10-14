import biolib.api
from biolib._app.skill import Skill, SkillState
from biolib._shared.types.typing import List, Optional
from biolib.api.client import ApiClient


class SkillIndex:
    def __init__(self, _api_client: Optional[ApiClient] = None) -> None:
        self._api_client: ApiClient = _api_client or biolib.api.client

    def list(self) -> List[Skill]:
        skills: List[Skill] = []
        page = 1
        while True:
            response = self._api_client.get(
                path='/resources/apps/index/',
                params={'page_size': 100, 'page': page},
            ).json()
            for app in response['results']:
                state = SkillState(app_version_uri=app['uri'], description=app.get('description', ''))
                skills.append(Skill(_internal_state=state, _api_client=self._api_client))
            if page >= response['page_count']:
                break
            page += 1
        return skills

    def list_as_markdown(self) -> str:
        skills = self.list()
        skill_list = '\n'.join(f'- **{skill.uri}**: {skill.description}' for skill in skills)
        return f"""\
---
name: biolib-skill-index
description: Index and usage of {len(skills)} available skills on BioLib.
---

# BioLib Skill Index

## Usage

1. Find the app URI for your task in the skill list below
2. Load the app and retrieve its skill *before writing any code that calls that app*

```python
import biolib
app = biolib.load('<skill-uri>')
skill = app.sdk.get_skill()
content = skill.get_markdown()
```

## Skill list

{skill_list}
"""
