import json

from biolib._shared.types.typing import Dict, List
from biolib.biolib_logging import logger


def build_code_example(app_uri: str, arguments: List[Dict]) -> str:
    args = _build_default_args(arguments) or ['--help']
    args_str = json.dumps(args, indent=None, ensure_ascii=False, allow_nan=False)
    return f"""\
```python
import biolib
app = biolib.load('{app_uri}')
result = app.cli(args={args_str}, check=True, stream_logs=True)
result.save_files('output/')
```"""


def build_arguments_json(arguments: List[Dict]) -> str:
    minimal_args = [_minimize_argument(arg) for arg in sorted(arguments, key=_by_order)]
    return f"""\
```json
{json.dumps(minimal_args, indent=2, ensure_ascii=False, allow_nan=False)}
```"""


def _by_order(setting: Dict) -> int:
    order: int = setting.get('order', 0)
    return order


def _build_default_args(arguments: List[Dict]) -> List[str]:
    args: List[str] = []
    for setting in sorted(arguments, key=_by_order):
        if setting.get('render_type', '') == 'group':
            logger.warning('Skipping group argument in code example: %s', setting.get('key', ''))
            continue

        key = setting.get('key', '')
        value = setting.get('default_value', '')

        if not key and not value:
            continue

        separator = setting.get('key_value_separator') or ' '
        if separator.strip():
            args.append(f'{key}{separator}{value}')
        else:
            if key:
                args.append(key)
            if value:
                args.append(value)

    return args


def _minimize_argument(argument: Dict) -> Dict:
    minimal: Dict = {
        'key': argument.get('key', ''),
        'render_type': argument.get('render_type', ''),
        'default_value': argument.get('default_value', ''),
        'description': argument.get('description', ''),
        'required': argument.get('required', True),
    }
    for list_key in ('options', 'sub_arguments', 'group_arguments'):
        items = argument.get(list_key, [])
        if not items:
            continue
        if list_key == 'options':
            minimal[list_key] = [{'value': option['value'], 'description': option['key']} for option in items]
        else:
            minimal[list_key] = [_minimize_argument(sub) for sub in items]
    return minimal
