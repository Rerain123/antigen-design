"""Actual JSON Schema for the revision envelope and shared evidence types.

Used at the runtime boundary. Producer-specific legacy schemas remain unchanged.
"""
from jsonschema import Draft202012Validator
from ...common import ensure
from .revision_contract import VERSION, CHECKS, EXECUTIONS, IDENTITY, SCOPE

ID=dict(type='string',minLength=1,maxLength=512)
HASH=dict(type='string',pattern='^[a-f0-9]{64}$')
NULL_NUMBER=dict(type=['number','null'])


def obj(properties,required=None,extra=True):
    return dict(type='object',properties=properties,required=list(properties) if required is None else required,
                additionalProperties=extra)


DEFS={
    'artifact_ref':obj(dict(artifact_id=ID,content_hash=HASH),extra=False),
    'diagnostic':obj(dict(error_category=dict(enum=['CONFIGURATION','CONTRACT','ASSOCIATION','OTHER',None]),
        reason_codes=dict(type='array',items=ID),reason_details=dict(type='array',items=dict(type='string')))),
    'check':obj(dict(check_status=dict(enum=list(CHECKS)),passed=dict(type=['boolean','null']),
        execution_status=dict(enum=list(EXECUTIONS)),reason_codes=dict(type='array',items=ID))),
    'scope':obj({k:HASH if k=='content_hash' else ID for k in SCOPE},extra=False),
    'budget':obj(dict(L=dict(type='integer',minimum=1),K=dict(type='integer',minimum=0),
        B=dict(type='integer',minimum=0),max_mutation_fraction=dict(type='number',minimum=0,maximum=1),
        design_site_fraction=dict(type='number',minimum=0,maximum=1),
        max_mutations_abs=dict(type=['integer','null'],minimum=0),config_id=ID)),
    'candidate':obj({**{k:HASH if k=='content_hash' else ID for k in IDENTITY},
        'sequence':dict(type='string',pattern='^[ACDEFGHIKLMNPQRSTVWY]+$'),
        'stage':dict(const='formal'),'constraint_check':{'$ref':'#/$defs/check'},
        'validation':{'$ref':'#/$defs/check'},'acceptance_status':dict(enum=list(CHECKS)),
        'provisional_acceptance_status':dict(enum=list(CHECKS)),
        'description_score':NULL_NUMBER,'comparison_score':NULL_NUMBER,'acceptance_score':NULL_NUMBER,
        'mutations':dict(type='array',items=obj(dict(position=dict(type='integer',minimum=1),
            wt=dict(type='string',pattern='^[ACDEFGHIKLMNPQRSTVWY]$'),mut=dict(type='string',pattern='^[ACDEFGHIKLMNPQRSTVWY]$')),extra=False))}),
    'summary':obj({**{k:HASH if k=='content_hash' else ID for k in SCOPE},
        'summary_id':ID,'check_id':ID,'check_status':dict(enum=list(CHECKS)),
        'selected_attempt_ids':dict(type='array',items=ID,uniqueItems=True),
        'selected_artifact_refs':dict(type='array',items={'$ref':'#/$defs/artifact_ref'})}),
}
SCHEMA={'$schema':'https://json-schema.org/draft/2020-12/schema','$defs':DEFS,
    **obj(dict(shared_contract_version=dict(const=VERSION),calculation_config=dict(type='object'),
        permission_snapshot=obj(dict(mutation_budget={'$ref':'#/$defs/budget'})),proposal_summary=dict(type='object'),
        formal_records=dict(type='array',items={'$ref':'#/$defs/candidate'}),run_audit=dict(type='object'),
        acceptance_status=dict(enum=list(CHECKS)),provisional_acceptance_status=dict(enum=list(CHECKS))))}


def validate(value,kind=None):
    schema=SCHEMA if kind is None else {'$defs':DEFS,'$ref':'#/$defs/'+kind}
    errors=list(Draft202012Validator(schema).iter_errors(value))
    ensure(not errors,'OUTPUT_INVALID','Revision schema: '+('; '.join(e.message for e in errors[:3])))
    def walk(v):
        if isinstance(v,dict):
            if 'check_status' in v and 'passed' in v:
                ensure(v['passed'] is {'PASS':True,'FAIL':False}.get(v['check_status']),
                       'OUTPUT_INVALID','passed must derive only from check_status')
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(value)
    return value
