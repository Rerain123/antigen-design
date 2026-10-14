"""Deterministic S-12 scan and strict local observation validation."""
import re

import Bio
from Bio.Seq import Seq

from ...common import RuntimeFault, decode, encode, ensure, sha
from .policy import registered_rules

PATTERN=re.compile(r'(?=(N[^P][ST]))')


def scan(body):
    sequence=str(Seq(body['protein_sequence']))
    matches=[dict(position=m.start()+1,sequon=m.group(1)) for m in PATTERN.finditer(sequence)]
    sites=[row['position'] for row in matches]
    hotspot=body['hotspot_input'];annotations=[]
    if hotspot['state']=='available':
        for interval in hotspot['hotspots']:
            within=[position for position in sites if interval['start']<=position<=interval['end']]
            annotations.append(dict(start=interval['start'],end=interval['end'],site_positions=within,site_count=len(within),
                shielding_risk=len(within)>=2))
        assessment='EVALUATED';risk=any(row['shielding_risk'] for row in annotations)
    else:
        assessment='NOT_PERFORMED';risk=False
    return dict(
        glycosylation=dict(sites=sites,site_count=len(sites),shielding_risk=risk,
            expression_hint='真核表达优先' if len(sites)>=3 else None),
        sequons=matches,
        hotspot_assessment=dict(status=assessment,input_state=hotspot['state'],schema_value_when_not_performed=False,
            coordinate_rule='sequon N position within 1-based inclusive exact-20-aa window',windows=annotations,
            source=hotspot['source'],source_verification='DECLARED_IN_REQUEST_ONLY' if hotspot['state']!='not_provided' else 'NOT_APPLICABLE',
            upstream_reason_code=hotspot['reason_code']))


def _parse_observation(files,body):
    observed=decode(files['output/observation.json'])
    ensure(isinstance(observed,dict) and set(observed)=={'biopython_version','method','result'},
        'OUTPUT_INVALID','Unexpected local observation shape')
    ensure(observed['biopython_version']==Bio.__version__ and observed['method']=='overlap-aware-regex-lookahead',
        'OUTPUT_INVALID','Local method identity changed')
    expected=scan(body)
    ensure(observed['result']==expected,'OUTPUT_INVALID','Stored scan differs from deterministic S-12 calculation')
    return expected


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        hotspot_input_sha256=sha(encode(body['hotspot_input'])))
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='N07_S12_GLYCOSYLATION_SCAN',binding=binding,
        execution=execution,user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,status='unreliable',null_reason=execution.get('error_code'),
        glycosylation=None,sequons=None,hotspot_assessment=None,controlled_fault=fault,method_summary=dict(
            tool='C1/BioPython',biopython_version=Bio.__version__,operation='overlap-aware N-X-S/T (X != P) regex scan',
            site_coordinate='1-based sequon N position',rule_profile=registered_rules(),experimental_confirmation=False,
            hotspot_source_artifact_validated=False,hotspot_full_chain_validated=False),warnings=[])
    try:
        if execution.get('error_code'):
            raise RuntimeFault(execution['error_code'],execution.get('diagnostic') or 'Local scan unavailable')
        ensure(execution.get('stopped_confirmed') is True and execution.get('exit_code')==0
            and execution.get('backend')=='trusted-local-in-process' and execution.get('network_used') is False
            and execution.get('container_id') is None and execution.get('biopython_version')==Bio.__version__,
            'OUTPUT_INVALID','No clean registered local calculation')
        parsed_files=files
        if fault=='corrupt_output':
            parsed_files=dict(files);parsed_files['output/observation.json']=b'{"truncated":true}'
        parsed=_parse_observation(parsed_files,body)
        verification=execution.get('hotspot_source_verification',{})
        verification_status=verification.get('status','NOT_APPLICABLE')
        parsed['hotspot_assessment']['source_verification']=verification_status
        artifact_validated=verification_status=='VERIFIED_N06_ARTIFACT_REF'
        value['method_summary']['hotspot_source_artifact_validated']=artifact_validated
        value['method_summary']['hotspot_full_chain_validated']=artifact_validated and parsed['hotspot_assessment']['status']=='EVALUATED'
        warnings=[dict(code='SEQUON_NOT_EXPERIMENTAL_EVIDENCE',level='quality',severity='WARNING',
            message='命中仅表示序列 sequon，不代表实验确认的糖基化。')]
        if parsed['hotspot_assessment']['status']=='NOT_PERFORMED':
            warnings.append(dict(code='HOTSPOT_SHIELDING_NOT_PERFORMED',level='quality',severity='WARNING',
                message='热点未提供或上游不可用；按 S-12 输出 shielding_risk=false，同时明确未执行遮蔽判定。'))
        if verification_status=='CONTRACT_FIXTURE_NOT_ARTIFACT_VERIFIED':
            warnings.append(dict(code='HOTSPOT_SOURCE_DECLARED_ONLY',level='quality',severity='WARNING',
                message='热点来源是合同夹具，不是已登记的 N06 真实产物。'))
        elif artifact_validated:
            warnings.append(dict(code='N06_SOURCE_ARTIFACT_VERIFIED',level='quality',severity='WARNING',
                message='已校验 N06 任务身份、结果 ArtifactRef、哈希和序列绑定；热点是否可用仍按 N06 当前结果判定。'))
        value.update(parsed,status='completed_empty' if parsed['glycosylation']['site_count']==0 else 'completed',
            null_reason=None,warnings=warnings)
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        error=execution.get('error_code') or 'OUTPUT_INVALID';execution.update(error_code=error,diagnostic=str(exc))
        value.update(status='unreliable',null_reason=error,glycosylation=None,sequons=None,hotspot_assessment=None,
            warnings=[dict(code=error,level='failure',severity='WARNING',message='N07 计算或产物校验失败，结果不可消费：'+str(exc))])
    return value
