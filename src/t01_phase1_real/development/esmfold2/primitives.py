"""Small worker JSON helpers; backend uses the existing RuntimeFault class."""
import hashlib
import json
import math

try:
    from ...common import RuntimeFault
except ModuleNotFoundError as exc:
    if exc.name != 'jsonschema': raise
    class RuntimeFault(Exception):
        def __init__(self, code, message):
            self.code = code
            super().__init__(message)


def ensure(value, code, message):
    if not value: raise RuntimeFault(code, message)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def decode(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            ensure(key not in result, 'INVALID_REQUEST', 'Duplicate JSON key')
            result[key]=value
        return result
    def invalid(value): raise RuntimeFault('INVALID_REQUEST','Nonfinite JSON number')
    def number(value):
        result=float(value)
        ensure(math.isfinite(result),'INVALID_REQUEST','Nonfinite JSON number')
        return result
    try: return json.loads(raw,object_pairs_hook=pairs,parse_constant=invalid,parse_float=number)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise RuntimeFault('INVALID_REQUEST','Malformed JSON') from exc
