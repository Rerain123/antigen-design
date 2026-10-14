"""Narrow additive N03-N10 registrations over the preserved W1 schema version.

All fields, artifact rules and lifecycle shapes retain the existing contract.
The old on-disk schemas and their historical hashes are never rewritten.
"""
import copy
from jsonschema import Draft202012Validator, FormatChecker
from ..common import SCHEMAS, decode, ensure, validate as original_validate

BEPIPRED='t01.real.bepipred'
NETMHC='t01.real.netmhc'
BLAST='t01.real.blast'
GLYCOSYLATION='t01.real.glycosylation'
EPITOPE_MAP='t01.real.epitope_map'
ADDITIVE={BLAST:'N03',BEPIPRED:'N04',NETMHC:'N05',EPITOPE_MAP:'N06',GLYCOSYLATION:'N07','t01.real.homology':'N08',
    't01.real.domains':'N09','t01.real.developability':'N10','t01.real.wt_draft':'N18'}
_validators={}


def validate(value,name):
    if not isinstance(value,dict) or value.get('tool_id') not in ADDITIVE or name not in ('submit','job'):
        return original_validate(value,name)
    ensure(value.get('contract_version')=='0.1.0','UNSUPPORTED_VERSION','Unsupported contract version')
    key=(value['tool_id'],name)
    if key not in _validators:
        schema=copy.deepcopy(decode((SCHEMAS/(name+'.schema.json')).read_bytes()))
        schema['properties']['tool_id']={'const':value['tool_id']}
        schema['properties']['node_id']={'const':ADDITIVE[value['tool_id']]}
        Draft202012Validator.check_schema(schema)
        _validators[key]=Draft202012Validator(schema,format_checker=FormatChecker())
    ensure(_validators[key].is_valid(value),'INVALID_REQUEST','Request or snapshot violates additive development '+name+' schema')
