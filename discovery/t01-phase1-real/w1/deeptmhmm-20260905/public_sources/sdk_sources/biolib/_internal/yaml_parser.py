import re
from typing import Any, Dict, List, Tuple


class YAMLParseError(Exception):
    pass


_UNQUOTED_TRUE = frozenset({'true', 'yes', 'on'})
_UNQUOTED_FALSE = frozenset({'false', 'no', 'off'})
_UNQUOTED_NULL = frozenset({'null', '~', ''})

_INT_RE = re.compile(r'^[-+]?[0-9][0-9_]*$')
_FLOAT_RE = re.compile(r'^[-+]?(\.[0-9][0-9_]*|[0-9][0-9_]*(\.[0-9_]*)?([eE][-+]?[0-9]+)?)$')
_INF_RE = re.compile(r'^[-+]?\.(inf|Inf|INF)$')
_NAN_RE = re.compile(r'^\.(nan|NaN|NAN)$')
_BLOCK_SCALAR_RE = re.compile(r'^([|>])([+-]?)(\d?)(?:\s+#.*)?$')


def _parse_scalar(value: str) -> Any:
    if value in _UNQUOTED_NULL:
        return None
    lower = value.lower()
    if lower in _UNQUOTED_TRUE:
        return True
    if lower in _UNQUOTED_FALSE:
        return False
    if _INF_RE.match(value):
        return float('inf') if not value.startswith('-') else float('-inf')
    if _NAN_RE.match(value):
        return float('nan')
    if _INT_RE.match(value):
        return int(value.replace('_', ''))
    if _FLOAT_RE.match(value):
        return float(value.replace('_', ''))
    return value


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '\\' and in_double:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == '#' and not in_single and not in_double and (i == 0 or line[i - 1] == ' '):
            return line[:i].rstrip()
        i += 1
    return line.rstrip()


def _unquote(value: str) -> str:
    if len(value) >= 2:
        if value[0] == "'" and value[-1] == "'":
            return value[1:-1].replace("''", "'")
        if value[0] == '"' and value[-1] == '"':
            inner = value[1:-1]
            result: List[str] = []
            i = 0
            while i < len(inner):
                if inner[i] == '\\' and i + 1 < len(inner):
                    next_ch = inner[i + 1]
                    if next_ch == 'n':
                        result.append('\n')
                    elif next_ch == 't':
                        result.append('\t')
                    elif next_ch == '"':
                        result.append('"')
                    elif next_ch == '\\':
                        result.append('\\')
                    else:
                        result.append(inner[i : i + 2])
                    i += 2
                else:
                    result.append(inner[i])
                    i += 1
            return ''.join(result)
    return value


def _is_quoted(value: str) -> bool:
    return len(value) >= 2 and ((value[0] == "'" and value[-1] == "'") or (value[0] == '"' and value[-1] == '"'))


def _parse_flow_value(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    if text.startswith('{'):
        return _parse_flow_mapping(text)
    if text.startswith('['):
        return _parse_flow_sequence(text)
    if _is_quoted(text):
        return _unquote(text)
    return _parse_scalar(text)


def _find_matching_bracket(text: str, open_ch: str, close_ch: str) -> int:
    depth = 0
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_double:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _split_flow_items(text: str) -> List[str]:
    items: List[str] = []
    depth_curly = 0
    depth_square = 0
    in_single = False
    in_double = False
    start = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_double:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '{':
                depth_curly += 1
            elif ch == '}':
                depth_curly -= 1
            elif ch == '[':
                depth_square += 1
            elif ch == ']':
                depth_square -= 1
            elif ch == ',' and depth_curly == 0 and depth_square == 0:
                items.append(text[start:i].strip())
                start = i + 1
        i += 1
    remainder = text[start:].strip()
    if remainder:
        items.append(remainder)
    return items


def _parse_flow_mapping(text: str) -> Dict[str, Any]:
    end = _find_matching_bracket(text, '{', '}')
    if end == -1:
        raise YAMLParseError('Unterminated flow mapping')
    inner = text[1:end].strip()
    result: Dict[str, Any] = {}
    if not inner:
        return result
    for item in _split_flow_items(inner):
        colon_pos = _find_colon_in_flow(item)
        if colon_pos == -1:
            raise YAMLParseError(f'Invalid flow mapping entry: {item}')
        key = item[:colon_pos].strip()
        val = item[colon_pos + 1 :].strip()
        key = _unquote(key)
        result[key] = _parse_flow_value(val)
    return result


def _find_colon_in_flow(text: str) -> int:
    in_single = False
    in_double = False
    depth_curly = 0
    depth_square = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_double:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '{':
                depth_curly += 1
            elif ch == '}':
                depth_curly -= 1
            elif ch == '[':
                depth_square += 1
            elif ch == ']':
                depth_square -= 1
            elif ch == ':' and depth_curly == 0 and depth_square == 0:
                return i
        i += 1
    return -1


def _parse_flow_sequence(text: str) -> List[Any]:
    end = _find_matching_bracket(text, '[', ']')
    if end == -1:
        raise YAMLParseError('Unterminated flow sequence')
    inner = text[1:end].strip()
    if not inner:
        return []
    return [_parse_flow_value(item) for item in _split_flow_items(inner)]


def _get_indent(line: str) -> int:
    return len(line) - len(line.lstrip(' '))


def _collect_block_scalar(raw_lines: List[str], start_line: int, style: str, chomp: str) -> Tuple[str, int]:
    if start_line >= len(raw_lines):
        return '', start_line

    first_content_line = start_line
    while first_content_line < len(raw_lines) and raw_lines[first_content_line].strip() == '':
        first_content_line += 1

    if first_content_line >= len(raw_lines):
        return '', first_content_line

    block_indent = _get_indent(raw_lines[first_content_line])
    if block_indent == 0:
        return '', start_line

    content_lines: List[str] = []
    pos = start_line
    while pos < len(raw_lines):
        raw = raw_lines[pos]
        if raw.strip() == '':
            content_lines.append('')
            pos += 1
            continue
        line_indent = _get_indent(raw)
        if line_indent < block_indent:
            break
        content_lines.append(raw[block_indent:])
        pos += 1

    while content_lines and content_lines[-1] == '':
        content_lines.pop()

    if style == '|':
        text = '\n'.join(content_lines)
    else:
        parts: List[str] = []
        current_paragraph: List[str] = []
        for cline in content_lines:
            if cline == '':
                if current_paragraph:
                    parts.append(' '.join(current_paragraph))
                    current_paragraph = []
                else:
                    parts.append('')
            else:
                current_paragraph.append(cline)
        if current_paragraph:
            parts.append(' '.join(current_paragraph))
        text = '\n'.join(parts)

    if chomp == '-':
        text = text.rstrip('\n')
    elif chomp == '+':
        trailing_count = 0
        check_pos = pos - 1
        while check_pos >= start_line and raw_lines[check_pos].strip() == '':
            trailing_count += 1
            check_pos -= 1
        text = text + '\n' * trailing_count
    else:
        text = text + '\n'

    return text, pos


def _preprocess_lines(text: str) -> List[Tuple[int, str, int]]:
    raw_lines = text.split('\n')
    processed: List[Tuple[int, str, int]] = []
    for line_num, raw_line in enumerate(raw_lines, 1):
        stripped = _strip_comment(raw_line)
        if not stripped or stripped.isspace():
            continue
        if '\t' in stripped[: len(stripped) - len(stripped.lstrip())]:
            raise YAMLParseError(f'Line {line_num}: tabs are not allowed for indentation in YAML')
        indent = _get_indent(stripped)
        content = stripped.strip()
        if indent == 0 and (
            content == '---' or content == '...' or content.startswith('--- ') or content.startswith('... ')
        ):
            raise YAMLParseError(f'Line {line_num}: document markers (--- / ...) are not supported')
        processed.append((indent, content, line_num))
    return processed


def _parse_block(
    lines: List[Tuple[int, str, int]], pos: int, _base_indent: int, raw_lines: List[str]
) -> Tuple[Any, int]:
    if pos >= len(lines):
        return None, pos

    indent, content, _line_num = lines[pos]

    if content.startswith('- ') or content == '-':
        return _parse_sequence(lines, pos, indent, raw_lines)

    if (':' in content or content.endswith(':')) and _find_key_colon(content) != -1:
        return _parse_mapping(lines, pos, indent, raw_lines)

    return _parse_scalar_value(content), pos + 1


def _parse_mapping(
    lines: List[Tuple[int, str, int]], pos: int, base_indent: int, raw_lines: List[str]
) -> Tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    while pos < len(lines):
        indent, content, _line_num = lines[pos]
        if indent < base_indent:
            break
        if indent > base_indent:
            break

        if content.startswith('- '):
            break

        colon_idx = _find_key_colon(content)
        if colon_idx == -1:
            break

        key = content[:colon_idx].strip()
        key = _unquote(key)
        after_colon = content[colon_idx + 1 :].strip()

        if after_colon:
            block_match = _BLOCK_SCALAR_RE.match(after_colon)
            if block_match:
                style = block_match.group(1)
                chomp = block_match.group(2) or ''
                result[key], pos = _handle_block_scalar(lines, pos, _line_num, style, chomp, raw_lines)
            else:
                result[key] = _parse_inline_value(after_colon)
                pos += 1
        else:
            pos += 1
            if pos < len(lines) and lines[pos][0] > base_indent:
                child_indent = lines[pos][0]
                result[key], pos = _parse_block(lines, pos, child_indent, raw_lines)
            elif (
                pos < len(lines)
                and lines[pos][0] == base_indent
                and (lines[pos][1].startswith('- ') or lines[pos][1] == '-')
            ):
                result[key], pos = _parse_sequence(lines, pos, base_indent, raw_lines)
            else:
                result[key] = None

    return result, pos


def _handle_block_scalar(
    lines: List[Tuple[int, str, int]], pos: int, line_num: int, style: str, chomp: str, raw_lines: List[str]
) -> Tuple[str, int]:
    scalar_value, raw_end_line = _collect_block_scalar(raw_lines, line_num, style, chomp)
    next_pos = pos + 1
    while next_pos < len(lines) and lines[next_pos][2] <= raw_end_line:
        next_pos += 1
    return scalar_value, next_pos


def _find_key_colon(content: str) -> int:
    in_single = False
    in_double = False
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == '\\' and in_double:
            i += 2
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == ':' and not in_single and not in_double and (i + 1 == len(content) or content[i + 1] == ' '):
            return i
        i += 1
    return -1


def _parse_inline_value(value: str) -> Any:
    if value.startswith('{'):
        return _parse_flow_mapping(value)
    if value.startswith('['):
        return _parse_flow_sequence(value)
    if _is_quoted(value):
        return _unquote(value)
    return _parse_scalar(value)


def _parse_sequence(
    lines: List[Tuple[int, str, int]], pos: int, base_indent: int, raw_lines: List[str]
) -> Tuple[List[Any], int]:
    result: List[Any] = []
    while pos < len(lines):
        indent, content, line_num = lines[pos]
        if indent < base_indent:
            break
        if indent > base_indent:
            break

        if not (content.startswith('- ') or content == '-'):
            break

        item_value = content[2:].strip() if content.startswith('- ') else ''

        if not item_value:
            pos += 1
            if pos < len(lines) and lines[pos][0] > base_indent:
                child_indent = lines[pos][0]
                value, pos = _parse_block(lines, pos, child_indent, raw_lines)
                result.append(value)
            else:
                result.append(None)
        elif item_value.startswith('{') or item_value.startswith('['):
            result.append(_parse_inline_value(item_value))
            pos += 1
        elif ':' in item_value and not _is_quoted(item_value):
            colon_idx = _find_key_colon(item_value)
            if colon_idx != -1:
                block_match = _BLOCK_SCALAR_RE.match(item_value[colon_idx + 1 :].strip())
                if block_match:
                    item_key = _unquote(item_value[:colon_idx].strip())
                    style = block_match.group(1)
                    chomp = block_match.group(2) or ''
                    scalar_val, pos = _handle_block_scalar(lines, pos, line_num, style, chomp, raw_lines)
                    mapping: Dict[str, Any] = {item_key: scalar_val}
                    child_indent = indent + 2
                    if pos < len(lines) and lines[pos][0] >= child_indent and lines[pos][0] > indent:
                        rest, pos = _parse_mapping(lines, pos, lines[pos][0], raw_lines)
                        mapping.update(rest)
                    result.append(mapping)
                else:
                    virtual_indent = indent + 2
                    virtual_lines: List[Tuple[int, str, int]] = [(virtual_indent, item_value, line_num)]
                    next_pos = pos + 1
                    while next_pos < len(lines) and lines[next_pos][0] > indent:
                        virtual_lines.append(lines[next_pos])
                        next_pos += 1
                    mapping, _ = _parse_mapping(virtual_lines, 0, virtual_indent, raw_lines)
                    result.append(mapping)
                    pos = next_pos
            else:
                result.append(_parse_inline_value(item_value))
                pos += 1
        else:
            result.append(_parse_inline_value(item_value))
            pos += 1

    return result, pos


def _parse_scalar_value(content: str) -> Any:
    if _is_quoted(content):
        return _unquote(content)
    return _parse_scalar(content)


def safe_load(text: str) -> Any:
    if not text or not text.strip():
        return None
    raw_lines = text.split('\n')
    lines = _preprocess_lines(text)
    if not lines:
        return None
    result, _ = _parse_block(lines, 0, lines[0][0], raw_lines)
    return result
