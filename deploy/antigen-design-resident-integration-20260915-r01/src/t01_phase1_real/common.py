"""Shared engineering primitives; no Mock imports or scientific calculations."""
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
SCHEMAS = REPO/'工作流设计/02-数据契约/phase1-real-v0.1'
TOOL = 't01.real.engineering_probe'
TERMINAL = frozenset(('succeeded','failed','cancelled','timed_out'))


class RuntimeFault(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)

    def envelope(self):
        return {'contract_version':'0.1.0','error':{'code':self.code,'message':self.message,'job_id':None}}


def ensure(value, code, message):
    if not value:
        raise RuntimeFault(code,message)


def decode(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            ensure(key not in result,'INVALID_REQUEST','Duplicate JSON key')
            result[key] = value
        return result
    def number(value):
        result = float(value)
        ensure(math.isfinite(result),'INVALID_REQUEST','Nonfinite JSON number')
        return result
    def invalid(_):
        raise RuntimeFault('INVALID_REQUEST','Nonfinite JSON number')
    try:
        if isinstance(raw, bytes): raw = raw.decode('utf-8')
        return json.loads(raw,object_pairs_hook=pairs,parse_float=number,parse_constant=invalid)
    except (ValueError,UnicodeError,TypeError) as exc:
        raise RuntimeFault('INVALID_REQUEST','Malformed UTF-8 JSON') from exc


def encode(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')


def new_id(kind):
    return f't01p1r-{kind}-{uuid4().hex}'


def identifier(value, prefix=None):
    ensure(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',value),
           'INVALID_REQUEST','Invalid identity')
    if prefix:
        ensure(value.startswith('t01p1r-'+prefix+'-'),'INVALID_REQUEST','Foreign identity namespace')
    return value


_validators = {}


def validate(value, name):
    if isinstance(value,dict) and 'contract_version' in value:
        ensure(value['contract_version']=='0.1.0','UNSUPPORTED_VERSION','Unsupported contract version')
    if name not in _validators:
        schema = decode((SCHEMAS/(name+'.schema.json')).read_bytes())
        Draft202012Validator.check_schema(schema)
        _validators[name] = Draft202012Validator(schema,format_checker=FormatChecker())
    ensure(_validators[name].is_valid(value),'INVALID_REQUEST','Request or snapshot violates '+name+' schema')


TRANSITIONS = decode((SCHEMAS/'contract.json').read_bytes())['transitions']


def profile():
    """Exact allowlisted implementation and resource policy, bound to code hashes."""
    sources = {p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    sources.update({p.name:sha(p.read_bytes()) for p in sorted((REPO/'scripts').glob('w1_runtime*.py'))})
    sources.update({p.name:sha(p.read_bytes()) for p in sorted(SCHEMAS.glob('*.schema.json'))})
    sources['contract.json'] = sha((SCHEMAS/'contract.json').read_bytes())
    policy = dict(worker=TOOL,version='0.1.0',platform='windows',scientific_compute=False,
                  max_input_bytes=65536,memory_bytes=256*1024**2,max_processes=4,wall_seconds=2.0,
                  code_sha256=sources)
    policy['python_version']=sys.version
    policy['python_executable_sha256']=sha(Path(sys.executable).read_bytes())
    return dict(id='w1-engineering-windows',version='0.1.0',sha256=sha(encode(policy)))
