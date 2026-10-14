"""Build NEW B2 review contracts/cases/reference receipts from sealed local evidence."""
import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

from b2_review_contract import ROOT, CONTRACT, ACADEMIC, BATCH, LABELS, read, sha, make_request, make_result, raw_record, replay_case
from check_b1_engineering import fingerprint
from probe_b1_input_facts import write_json

PUBLIC = ROOT / 'discovery/t01-phase1-real/w1/deeptmhmm-20260905'
HASH = dict(type='string', pattern='^[0-9a-f]{64}$')
STRING = dict(type='string')
BOOL = dict(type='boolean')
NULL = dict(type='null')


def obj(fields):
    return dict(type='object', properties=fields, required=list(fields), additionalProperties=False)


def nullable(value):
    return dict(anyOf=[value, NULL])


def array(value):
    return dict(type='array', items=value)


def const(value):
    return dict(const=value)


def schemas():
    run_id = dict(type='string', pattern='^t01p1r-run-[A-Za-z0-9._-]+$')
    request_id = dict(type='string', pattern='^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
    common = dict(contract_version=const('0.1.0'), contract_status=const('DRAFT_REVIEW_ONLY'), tool_id=const('t01.real.deeptmhmm'))
    request = obj(dict(common, run_id=run_id, request_id=request_id, protein_sequence=STRING,
        protein_sequence_sha256=HASH, user_sequence_id=STRING,
        internal_sequence_id=dict(type='string', pattern='^t01seq_[0-9a-f]{64}$'),
        profile_id=const('t01.deeptmhmm.academic1.cpu.review.v0.1'), profile_sha256=HASH))
    segment = obj(dict(type=dict(enum=['inside', 'outside', 'TMhelix', 'signal']), start=dict(type='integer',minimum=1), end=dict(type='integer',minimum=1)))
    raw_segment = obj(dict(segment['properties'], type=dict(enum=list(LABELS.values())), label=dict(enum=list(LABELS))))
    topology = obj(dict(labels=array(dict(enum=['inside', 'outside', 'TMhelix', 'signal'])), segments=array(segment),
        has_signal=BOOL, tm_count=dict(type='integer',minimum=0), outside_length=dict(type='integer',minimum=0)))
    raw = obj(dict(record_id=STRING, sequence=STRING, labels=dict(type='string',pattern='^[IOMSPB]+$'),
        type=dict(enum=['TM','SP+TM','SP','GLOB','BETA']), segments=array(raw_segment), raw_tmr_count=dict(type='integer',minimum=0), coordinate_base=const(1)))
    result = obj(dict(common, identity_scope=const('LOCAL_REVIEW_NOT_RUNTIME_ISSUED'),
        evidence_kind=dict(enum=['ENGINEERING_FIXTURE','G0_RAW_REPLAY']),
        binding=obj(dict(run_id=run_id,request_id=request_id,job_id=dict(type='string',pattern='^t01p1r-job-[A-Za-z0-9._-]+$'),
            attempt_id=dict(type='string',pattern='^t01p1r-attempt-[A-Za-z0-9._-]+$'),request_sha256=HASH,sequence_sha256=HASH,profile_sha256=HASH)),
        execution_observation=dict(enum=['completed','not_started','failed','timed_out','cancelled']),
        failure_reason=dict(enum=[None,'TOOL_UNAVAILABLE','INVALID_OUTPUT','TOOL_FAILED','TIMED_OUT','CANCELLED']),
        raw_record=nullable(raw), raw_artifacts=array(obj(dict(role=dict(enum=['input_fasta','prediction','regions','execution','method_summary']),
            path=STRING,sha256=HASH,size_bytes=dict(type='integer',minimum=0)))),
        id_pairing=dict(enum=['SAFE_INTERNAL_ID','HISTORICAL_ORIGINAL_ID']),scientific_signoff=NULL,production_status=const('NOT_DEPLOYED'),
        topology=nullable(topology),null_reason=dict(enum=[None,'INVALID_INPUT','INPUT_REVIEW_REQUIRED','PB_OUT_OF_DOMAIN','TOOL_UNAVAILABLE','INVALID_OUTPUT','TOOL_FAILED','TIMED_OUT','CANCELLED']),
        input_findings=array(dict(enum=['EMPTY_SEQUENCE','SEQUENCE_NOT_NORMALIZED','INVALID_SEQUENCE_SYMBOL','UPSTREAM_DEFAULT_LENGTH_GUARD','NON_AA20_REQUIRES_REVIEW','LENGTH_BEYOND_RECORDED_SAMPLES'])),
        interpretation_status=dict(enum=['parsed_unverified','unreliable']),requires_review=const(True),automatic_handoff=const(False),usable_for_pipeline=const(False),
        warnings=array(obj(dict(level=const('failure'),severity=const('WARNING'),code=STRING,message=dict(type='string',minLength=1))))))
    for name, schema in [('request',request),('result',result)]:
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
        write_json(CONTRACT/(name+'.schema.json'),schema)


def contract_assets():
    CONTRACT.mkdir(exist_ok=False)
    method = read(ACADEMIC/'method_summary.json')
    profile = dict(profile_id='t01.deeptmhmm.academic1.cpu.review.v0.1',version='0.1.0',status='DEVELOPMENT_CANDIDATE_REVIEW_ONLY',
        tool_name=method['tool_name'],tool_version=method['tool_version'],image_id=method['image_id'],archive_sha256=method['archive_sha256'],
        model_assets_sha256=method['model_assets_sha256'],runtime_packages=method['runtime_packages'],parameters=method['parameters'],
        method_source=fingerprint(ACADEMIC/'method_summary.json'),
        input_policy=dict(request_records=1,request_normalization='Caller supplies exact uppercase sequence without whitespace; checker never repairs it',
            candidate_alphabet='ACDEFGHIKLMNPQRSTVWY',non_aa20='Review required; the single X probe is not an approved alphabet',
            upstream_default_minimum_aa=9,approved_minimum_aa=None,approved_maximum_aa=None,
            observed_aa20_lengths=[50,51,96,97,173,307,375,471,991],
            observed_span_is_continuous_approval=False,largest_observed_aa=991,
            long_sequence='1022 is a token-slice constant in utils.py, not a verified amino-acid limit. Token count/termini and 1020/1021/1022/1023 aa cases need measurement.',
            safe_id='t01seq_ + full normalized-sequence SHA-256; one record per isolated attempt; user ID remains metadata'),
        runtime_policy=dict(device='CPU',network='none',cpus=8,memory_gib=10,timeout_seconds=900,
            source='Recorded development command only; target resource/performance acceptance pending',model_invocation_enabled=False),
        scientific_signoff=None,production_enabled=False)
    write_json(CONTRACT/'profile.json',profile)
    schemas()
    expert = ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'
    sources=[dict(fingerprint(p),kind='EXPERT_ORIGINAL') for p in sorted(expert.iterdir()) if p.is_file()]
    for name in ['docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json',
        'docs/project/sources/PHASE1_W1_DEEPTMHMM_USAGE_20260905.json','docs/project/sources/PHASE1_W1_MODULAR_DEVELOPMENT_20260905.json',
        'docs/project/sources/PHASE1_W1_B2_PRIORITY_20260906.json','工作流设计/02-数据契约/phase1-real-v0.1/contract.json']:
        sources.append(dict(fingerprint(ROOT/name),kind='USER_DECISION_OR_EXISTING_CONTRACT'))
    for path in [ACADEMIC/'manifest.json',ACADEMIC/'method_summary.json',ACADEMIC/'raw_audit.json',ACADEMIC/'package_sources/predict.py',
                 ACADEMIC/'package_sources/utils.py',ACADEMIC/'package_sources/experiments/tmhmm3/tm_util.py',PUBLIC/'manifest.json',PUBLIC/'public_sources/retrieval.json']:
        sources.append(dict(fingerprint(path),kind='SEALED_PRIOR_FACT'))
    write_json(CONTRACT/'source_manifest.json',dict(sources=sources,scientific_signoff='NOT_GRANTED'))


def examples_and_plan():
    # Literal scenarios are declared before any replay/validation campaign is executed.
    cases=[]
    def add(name, sequence, labels=None, kind='GLOB', failure=None, null_reason=None, counts=None):
        cases.append(dict(id=name,sequence=sequence,labels=labels,type=kind,failure=failure,
            expected=dict(null_reason=null_reason,counts=counts)))
    add('normal-four-labels','A'*12,'IIIMMOOOOSSS','SP+TM',counts=dict(tm_count=1,outside_length=4,has_signal=True,segments=4))
    add('multiple-m-segments','A'*12,'MMIIMMIIOOOO','TM',counts=dict(tm_count=2,outside_length=4,has_signal=False,segments=5))
    add('all-inside','A'*9,'I'*9,counts=dict(tm_count=0,outside_length=0,has_signal=False,segments=1))
    add('signal','A'*9,'SSSOOOOOO','SP',counts=dict(tm_count=0,outside_length=6,has_signal=True,segments=2))
    add('p-only-glob','A'*9,'PPPOOOOOO','GLOB',null_reason='PB_OUT_OF_DOMAIN')
    add('b-only','A'*9,'BBBOOOOOO','BETA',null_reason='PB_OUT_OF_DOMAIN')
    add('pb-full','A'*12,'SSPPBBBOOPPP','BETA',null_reason='PB_OUT_OF_DOMAIN')
    add('empty','',null_reason='INVALID_INPUT')
    add('upstream-eight','A'*8,null_reason='INVALID_INPUT')
    add('lowercase','acdefghik',null_reason='INVALID_INPUT')
    add('whitespace','ACD EFGHIK',null_reason='INVALID_INPUT')
    add('stop','ACDEFGHI*',null_reason='INVALID_INPUT')
    add('unicode','ACDEFGHIＡ',null_reason='INVALID_INPUT')
    add('non-aa20','ACDEFGHIX',null_reason='INPUT_REVIEW_REQUIRED')
    add('above-observed-range','A'*992,null_reason='INPUT_REVIEW_REQUIRED')
    for reason in ['TOOL_UNAVAILABLE','TOOL_FAILED','INVALID_OUTPUT','TIMED_OUT','CANCELLED']:
        add(reason.lower(),'ACDEFGHIK',failure=reason,null_reason=reason)
    write_json(BATCH/'expected_cases.json',dict(declared_before_execution=True,prepared_at=datetime.now(timezone.utc).isoformat(),
        oracle='Literal label blocks/counts plus A5/S04/R48; synthetic cases are not model predictions or biological references',cases=cases,
        replay_cases=['short','coverage','x-residue'],expected_replay=dict(records=11,ordinary=8,pb=2,input_review=1),
        raw_failure_cases=['empty'],raw_model_executions_this_task=0))
    (CONTRACT/'examples').mkdir()
    registry=[]
    for case in cases:
        name=case['id'];request=make_request(name,case['sequence'],user_sequence_id='user label | ../not-a-path')
        path=CONTRACT/'examples'/(name+'-request.json');write_json(path,request)
        raw=raw_record(request['internal_sequence_id'],case['sequence'],case['labels'],case['type']) if case['labels'] else None
        result=make_result(request,path.read_bytes(),raw=raw,failure=case['failure'])
        result_path=CONTRACT/'examples'/(name+'-result.json');write_json(result_path,result)
        registry.append(dict(id=name,request=fingerprint(path),result=fingerprint(result_path)))
    write_json(CONTRACT/'example_pairs.json',dict(identity_scope='HAND_AUTHORED_REVIEW_ONLY',pairs=registry))


def reference_inventory():
    audit=read(PUBLIC/'source-audit/audit.json')
    selections=audit.get('selected_cases') or audit.get('selected_annotation_cases')
    if selections is None:
        selections=next(value for value in audit.values() if isinstance(value,list) and value and isinstance(value[0],dict) and 'source_line' in value[0])
    source=PUBLIC/'public_sources/DeepTMHMM.3line'
    text=source.read_text(encoding='utf-8');lines=text.splitlines(keepends=True)
    reference=[]
    (BATCH/'references').mkdir()
    for item in selections:
        line=item['source_line'];block=''.join(lines[line-1:line+2]);header,seq,labels=block.splitlines()
        output=BATCH/'references'/(item['id']+'.3line');output.write_bytes(block.encode())
        reference.append(dict(id=item['id'],sequence_sha256=sha(seq.encode()),labels_sha256=sha(labels.encode()),
            source=fingerprint(source),source_line_1based=line,exact_block=fingerprint(output),
            role='PUBLISHED_ANNOTATION_INDEPENDENT_OF_NEW_PARSER',independent_of_new_parser=True,
            training_independence='NOT_ESTABLISHED',accepted_scientific_holdout=False,
            known_coverage=item['inspection'],scientific_signoff=None))
    write_json(BATCH/'reference_inventory.json',dict(public_annotations=reference,
        other_inputs=dict(dtu_official_examples='4 real input examples; no independently supplied expected topology',
            package_sample='Bundled example; tool output is a regression baseline only',
            x_residue='Synthetic one-position substitution; input-domain probe only',
            crossval='Historical 4-line rows; exact row roles and relation to this model not confirmed; not a 3-line runtime oracle'),
        approved_independent_holdouts=0,
        receipt_required=['source/permission and exact sequence hash','experimental/curated annotation source and residue coordinates',
            'annotation version/date and evidence provenance','training/validation overlap or leakage assessment',
            'predeclared expected labels/regions and task-specific metrics with scientific thresholds',
            'signed scientific reviewer and accepted input domain'],
        required_coverage=['globular','signal','single alpha TM with >50 outside residues and S16 cross-check',
            'multiple alpha TMs','P-only/B-only/BETA','9/29/30 aa and length/token boundaries',
            'non-AA20 review cases','independent real holdouts distinct from official training/crossval'],
        acceptance='Engineering exact consistency can pass now; scientific thresholds and independent holdouts remain unapproved'))
    write_json(CONTRACT/'reference_receipt.template.json',dict(template_only=True,reference_id=None,sequence_artifact=None,
        labels_artifact=None,source_citation=None,source_version=None,annotation_evidence=None,
        training_overlap_assessment=None,independent_holdout_accepted=False,metrics_and_thresholds=None,
        reviewer_name=None,signed_at=None,scientific_signoff=None))


def acceptance():
    write_json(CONTRACT/'acceptance.json',dict(scope='W1-08B2_REVIEW_PREPARATION',required_engineering_checks=[
        'Exact input/request/profile/source binding and safe single-record ID',
        'Six raw labels preserved, full length, only four labels in non-null project topology',
        'Academic three-line and 8-column region table agreement; 1-based inclusive contiguous regions',
        'tm_count counts M segments, outside_length counts O residues, has_signal matches S',
        'P or B forces null/unreliable/failure WARNING/no automatic handoff independently of raw type',
        'Unavailable/invalid/partial/timeout/cancel never produces invented ordinary labels',
        'Exact raw corpus/empty-run replay; public annotation lineage separate from model regression',
        'Original academic asset/output integrity and all scientific profiles remain disabled'],
        release_requirements=[
            dict(id='B2-G1-INPUT',owner='algorithm + engineering',required='Approve normalized alphabet, biological domain and length/resource support using named cases',status='PENDING'),
            dict(id='B2-G1-REFERENCE',owner='algorithm acceptance',required='Accept independently sourced reference labels and training-leakage assessment; sign metrics and thresholds before evaluation',status='PENDING'),
            dict(id='B2-G1-RUNTIME',owner='deployment',required='Named target CPU/GPU profile, actual package/license receipt, offline asset hashes and target reproduction',status='PENDING'),
            dict(id='B2-G1-CONTRACT',owner='engineering + algorithm',required='Sign request/result, P/B/null/partial failures, method_summary and downstream handoff contracts',status='PENDING'),
            dict(id='B2-G2-ADAPTER',owner='engineering',required='After applicable B2 review, implement official adapter: safe ID process execution, output checks, resource stop/recovery and immutable publication',status='NOT_STARTED'),
            dict(id='B2-G3-G6',owner='deployment + test + scientific reviewer',required='Clean offline packaging, actual N02 integration, wave acceptance and frozen release',status='NOT_STARTED')],
        independent_of=['B1 structure scientific mapping','AF3/ESMFold2 assets','FoldX/ProteinMPNN future-wave validation'],
        downstream=[
            dict(consumer='S-16 / W3',normal='Reuse TMhelix/signal domains; single-TM large outside requires cross-validation',null='Use approved local UniProt annotations and regex plus WARNING; no fabricated topology domains'),
            dict(consumer='S-19 / W2',normal='Any hotspot residue outside/signal means in_outside_region=true',null='Pass no topology_labels; in_outside_region is unknown/null per nullable Schema, not false evidence'),
            dict(consumer='S-27 / W5',normal='Follow existing topology_allowed expression',null='No restriction solely due to missing topology; unreliable/no-auto-handoff state still propagates'),
            dict(consumer='membrane gate / W4 and scan / W7',normal='Consume tm_count/outside_length with S16 cross-check; >50 is existing strict boundary',null='Do not dereference null or treat missing topology as biological absence; preserve review state'),
            dict(consumer='S-05',normal='T02-only, outside current T01 wave',null='Reference-only default retain/topology_exempted; do not add S05 to W1')],
        scientific_signoff=None,production_enabled=False))


def main():
    require_new = not (BATCH/'expected_cases.json').exists() and not CONTRACT.exists()
    if not require_new:
        raise FileExistsError('B2 material already exists; preserve it and use a separately versioned task')
    contract_assets();examples_and_plan();reference_inventory();acceptance()
    print('B2 contracts, 20 declared synthetic cases and reference inventory prepared; no model execution')


if __name__=='__main__':
    main()
