"""A bounded CIF 1.1 reader retaining token spelling and source locations.

This is a facts reader, not a dictionary validator or a coordinate converter.
Only one data block, scalar items and flat loops are supported. No token is
coerced to an author integer; quoted '.'/'?' remain literal strings.
"""
from __future__ import annotations

from bisect import bisect_right
import re


class FactError(ValueError):
    def __init__(self, code, message, location=None):
        super().__init__(message)
        self.code = code
        self.location = location


class Source:
    def __init__(self, text):
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer('\n', text)]

    def field(self, start, end, value=None, *, style='bare'):
        raw = self.text[start:end]
        value = raw if value is None else value
        missing = {'?': 'unknown', '.': 'not_applicable'}.get(value) if style == 'bare' else None
        line = bisect_right(self.lines, start)
        return dict(value=None if missing else value, raw_value=raw,
                    missing=missing, style=style,
                    location=dict(start=start, end=end, line=line,
                                  column=start - self.lines[line - 1] + 1))


def tokens(source):
    text = source.text
    i, size = (1 if text.startswith('\ufeff') else 0), len(text)
    while i < size:
        if text[i].isspace():
            i += 1
            continue
        if text[i] == '#':
            end = text.find('\n', i)
            i = size if end < 0 else end + 1
            continue
        start = i
        if text[i] == ';' and (i == 0 or text[i - 1] == '\n'):
            end = re.search(r'\n;', text[i + 1:])
            if end is None:
                raise FactError('PARSE_FAILED', 'Unterminated CIF text field', source.field(i, i + 1)['location'])
            closing = i + 1 + end.start() + 1
            i = closing + 1
            if i < size and not text[i].isspace():
                raise FactError('PARSE_FAILED', 'Text terminator must be followed by whitespace')
            value = text[start + 1:closing].removesuffix('\n').removesuffix('\r')
            yield source.field(start, i, value, style='text')
        elif text[i] in "\"'":
            quote = text[i]
            i += 1
            while i < size:
                if text[i] in '\r\n':
                    raise FactError('PARSE_FAILED', 'Unterminated single-line CIF quote')
                if text[i] == quote and (i + 1 == size or text[i + 1].isspace()):
                    break
                i += 1
            if i == size:
                raise FactError('PARSE_FAILED', 'Unterminated CIF quote')
            i += 1
            yield source.field(start, i, text[start + 1:i - 1], style='quoted')
        else:
            while i < size and not text[i].isspace():
                i += 1
            if text[start] in '[]':
                raise FactError('INPUT_UNSUPPORTED', 'CIF 2.0 containers are outside this CIF 1.1 reader')
            yield source.field(start, i)


def _control(token):
    if token['style'] != 'bare' or token['missing']:
        return False
    value = token['value'].lower()
    return value.startswith(('_', 'data_', 'save_')) or value in {'loop_', 'stop_', 'global_'}


def read_cif(source):
    ts = list(tokens(source))
    if not ts or ts[0]['style'] != 'bare' or not str(ts[0]['value']).lower().startswith('data_'):
        raise FactError('PARSE_FAILED', 'Expected a CIF data block')
    if len(ts[0]['value']) == 5:
        raise FactError('PARSE_FAILED', 'CIF data block has no name')
    items, i = {}, 1

    def register(tag, values):
        name = tag['value'].lower()
        if name in items:
            raise FactError('PARSE_FAILED', 'Duplicate CIF data name: ' + tag['value'], tag['location'])
        items[name] = dict(field_name=tag['value'], field_location=tag['location'], values=values)

    while i < len(ts):
        token = ts[i]
        word = str(token['value']).lower() if token['style'] == 'bare' else ''
        if word.startswith(('data_', 'save_')) or word in {'global_', 'stop_'}:
            raise FactError('INPUT_UNSUPPORTED', 'Multiple blocks/save frames/global/stop are outside the supported branch', token['location'])
        if word == 'loop_':
            i += 1
            tags = []
            while i < len(ts) and ts[i]['style'] == 'bare' and str(ts[i]['value']).startswith('_'):
                tags.append(ts[i])
                i += 1
            start = i
            while i < len(ts) and not _control(ts[i]):
                i += 1
            values = ts[start:i]
            if not tags or not values or len(values) % len(tags):
                raise FactError('PARSE_FAILED', 'Empty or ragged CIF loop', token['location'])
            for column, tag in enumerate(tags):
                register(tag, values[column::len(tags)])
        elif word.startswith('_'):
            if i + 1 == len(ts) or _control(ts[i + 1]):
                raise FactError('PARSE_FAILED', 'CIF item is missing its value', token['location'])
            register(token, [ts[i + 1]])
            i += 2
        else:
            raise FactError('PARSE_FAILED', 'Unexpected CIF token', token['location'])
    return items
