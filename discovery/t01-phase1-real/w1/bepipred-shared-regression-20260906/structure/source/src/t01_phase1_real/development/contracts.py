"""Narrow additive N04/tool registration over the preserved W1 schema version.

All fields, artifact rules and lifecycle shapes retain the existing contract.
The old on-disk schemas and their historical hashes are never rewritten.
"""
import copy
from jsonschema import Draft202012Validator, FormatChecker
from ..common import SCHEMAS, decode, ensure, validate as original_validate

BEPIPRED='t01.real.bepipred'
_validators={}


def validate(value,name):
    if not isinstance(value,dict) or value.get('tool_id')!=BEPIPRED or name not in ('submit','job'):
        return original_validate(value,name)
    ensure(value.get('contract_version')=='0.1.0','UNSUPPORTED_VERSION','Unsupported contract version')
    if name not in _validators:
        schema=copy.deepcopy(decode((SCHEMAS/(name+'.schema.json')).read_bytes()))
        schema['properties']['tool_id']={'const':BEPIPRED}
        schema['properties']['node_id']={'const':'N04'}
        Draft202012Validator.check_schema(schema)
        _validators[name]=Draft202012Validator(schema,format_checker=FormatChecker())
    ensure(_validators[name].is_valid(value),'INVALID_REQUEST','Request or snapshot violates BepiPred '+name+' schema')
