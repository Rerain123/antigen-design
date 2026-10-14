"""Validate B2 drafts and replay sealed facts, with explicit scientific release gaps."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from b2_review_contract import ROOT, CONTRACT, ACADEMIC, BATCH, read, sha, require, load_original, make_request, make_result, validate_request, validate_result, replay_case
from check_b1_engineering import fingerprint, safe_path
from probe_b1_input_facts import write_json

SOURCES = ['scripts/b2_review_contract.py','scripts/prepare_w1_b2_review.py','scripts/check_w1_b2_review.py','tests/test_w1_b2_review.py']


def check_sources():
    source=read(CONTRACT/'source_manifest.json')
    for row in source['sources']:
        require(fingerprint(safe_path(ROOT,row['path'])) == {k:row[k] for k in ('path','sha256','size_bytes')},'Source hash mismatch: '+row['path'])
    require(sum(r['kind']=='EXPERT_ORIGINAL' for r in source['sources'])==22,'Incomplete expert-source search')
    profile=read(CONTRACT/'profile.json');method=read(ACADEMIC/'method_summary.json')
    for field in ['tool_name','tool_version','image_id','archive_sha256','model_assets_sha256','runtime_packages','parameters']:
        require(profile[field]==method[field],'Profile differs from recorded Academic method')
    require(profile['production_enabled'] is False and profile['scientific_signoff'] is None,'Profile claims scientific approval')
    require(profile['input_policy']['approved_maximum_aa'] is None,'Invented scientific length limit')
    require(not any(t['production_enabled'] for t in read(CONTRACT.parent/'contract.json')['tools']),'Runtime scientific worker enabled')


def check_examples():
    plan=read(BATCH/'expected_cases.json');registry=read(CONTRACT/'example_pairs.json')
    require(plan['declared_before_execution'] is True and registry['identity_scope']=='HAND_AUTHORED_REVIEW_ONLY','Examples claim execution or have no predeclaration')
    require([c['id'] for c in plan['cases']]==[c['id'] for c in registry['pairs']],'Example case closure mismatch')
    observations=[]
    for case,pair in zip(plan['cases'],registry['pairs']):
        for field in ['request','result']:
            require(fingerprint(safe_path(ROOT,pair[field]['path']))==pair[field],'Example hash mismatch')
        request_bytes=safe_path(ROOT,pair['request']['path']).read_bytes();request=validate_request(json.loads(request_bytes))
        result=validate_result(read(safe_path(ROOT,pair['result']['path'])),request,request_bytes)
        require(request['protein_sequence']==case['sequence'],'Declared input mismatch')
        expected=case['expected'];require(result['null_reason']==expected['null_reason'],'Declared null reason mismatch')
        if case['labels'] is not None:
            require(result['raw_record']['labels']==case['labels'],'Raw labels truncated or replaced')
        else:
            require(result['raw_record'] is None,'Unexecuted failure contains raw labels')
        if expected['counts']:
            topology=result['topology'];wanted=expected['counts']
            require(all(topology[k]==wanted[k] for k in ['tm_count','outside_length','has_signal']),'Literal aggregate count mismatch')
            require(len(topology['segments'])==wanted['segments'],'Literal continuous segment count mismatch')
        else:
            require(result['topology'] is None,'Invalid/PB/failure has normal topology')
        observations.append(dict(id=case['id'],status='PASS',null_reason=result['null_reason'],evidence_kind='ENGINEERING_FIXTURE'))
    return observations


def source_artifacts(case):
    folder=ACADEMIC/'runs'/case
    return [dict(role=role,**fingerprint(path)) for role,path in [
        ('input_fasta',ACADEMIC/'inputs'/(case+'.fasta')),('prediction',folder/'output/result/predicted_topologies.3line'),
        ('regions',folder/'output/result/TMRs.gff3'),('execution',folder/'execution.json'),('method_summary',ACADEMIC/'method_summary.json')]]


def check_reference_inventory():
    inventory=read(BATCH/'reference_inventory.json')
    require(inventory['approved_independent_holdouts']==0,'Unapproved samples promoted to holdouts')
    for item in inventory['public_annotations']:
        for field in ['source','exact_block']:
            require(fingerprint(safe_path(ROOT,item[field]['path']))==item[field],'Reference bytes/hash changed')
        source=safe_path(ROOT,item['source']['path']).read_bytes().decode('utf-8').splitlines(keepends=True)
        block=''.join(source[item['source_line_1based']-1:item['source_line_1based']+2]).encode()
        require(block==safe_path(ROOT,item['exact_block']['path']).read_bytes(),'Reference block is not the exact source lines')
        header,seq,labels=block.decode().splitlines()
        require(header[1:].split('|')[0]==item['id'] and sha(seq.encode())==item['sequence_sha256']
            and sha(labels.encode())==item['labels_sha256'],'Reference sequence/labels binding differs')
        require(item['independent_of_new_parser'] is True and item['training_independence']=='NOT_ESTABLISHED'
            and item['accepted_scientific_holdout'] is False and item['scientific_signoff'] is None,'Reference invents independence/signoff')
    return inventory


def reference_comparison(results):
    inventory=check_reference_inventory();by_accession={r['raw_record']['record_id'].split('|')[0]:r['raw_record'] for r in results if r['raw_record']}
    compared=[]
    for reference in inventory['public_annotations']:
        raw=by_accession[reference['id']]
        _,seq,labels=safe_path(ROOT,reference['exact_block']['path']).read_text(encoding='utf-8').splitlines()
        require(raw['sequence']==seq,'Published reference sequence differs from replay')
        different=[i for i,(a,b) in enumerate(zip(labels,raw['labels']),1) if a!=b]
        compared.append(dict(id=reference['id'],sequence_sha256=sha(seq.encode()),annotation_labels_sha256=sha(labels.encode()),
            prediction_labels_sha256=sha(raw['labels'].encode()),different_positions_1based=different,
            comparison_kind='DIAGNOSTIC_AGREEMENT_ONLY',scientific_acceptance='NOT_EVALUATED',training_independence='NOT_ESTABLISHED'))
    return compared


def execute():
    target=BATCH/'execution'
    target.mkdir(exist_ok=False)
    write_json(target/'invocation.json',dict(started_at=datetime.now(timezone.utc).isoformat(),
        command='scripts/check_w1_b2_review.py execute',plan_sha256=sha((BATCH/'expected_cases.json').read_bytes()),
        method='READ_ONLY_REPLAY_AND_REVIEW_CONTRACT_CHECKS',model_executions_this_task=0))
    check_sources();examples=check_examples()
    prior=load_original('verify_evidence').verify()
    rows=[]
    for case in read(BATCH/'expected_cases.json')['replay_cases']:
        for index,raw in enumerate(replay_case(case),1):
            name=case+'-'+str(index)
            request=make_request(name,raw['sequence'],raw['record_id'])
            request_path=target/(name+'-request.json');write_json(request_path,request)
            result=make_result(request,request_path.read_bytes(),raw=raw,evidence_kind='G0_RAW_REPLAY',raw_artifacts=source_artifacts(case))
            validate_result(result,request,request_path.read_bytes())
            result_path=target/(name+'-result.json');write_json(result_path,result)
            rows.append(dict(id=name,source_case=case,request=fingerprint(request_path),result=fingerprint(result_path),null_reason=result['null_reason']))
    results=[read(safe_path(ROOT,row['result']['path'])) for row in rows]
    comparison=reference_comparison(results)
    counts=Counter('ordinary' if r['null_reason'] is None else 'pb' if r['null_reason']=='PB_OUT_OF_DOMAIN' else 'input_review' for r in results)
    require(dict(counts)==dict(ordinary=8,pb=2,input_review=1),'Unexpected prior replay disposition counts')
    empty=read(ACADEMIC/'runs/empty/execution.json')
    stdout=(ACADEMIC/'runs/empty/stdout.txt').read_text()
    require(empty['container_exit_code']==1 and 'No sequences found in FASTA input' in stdout and 'Step 1/4' not in stdout,'Wrong original empty-input failure')
    write_json(target/'assessment.json',dict(status='PASS_REVIEW_PREPARATION',declared_plan_sha256=sha((BATCH/'expected_cases.json').read_bytes()),
        synthetic_cases=examples,replay_cases=rows,replay_counts=dict(counts),reference_comparison=comparison,
        original_empty_input=dict(status='REJECTED_BEFORE_MODEL_LOADING',execution=fingerprint(ACADEMIC/'runs/empty/execution.json'),
            source_scope='ORIGINAL_G0_FAILURE; not a new adapter invocation'),prior_evidence_verification=prior,
        model_executions_this_task=0,scientific_signoff='NOT_GRANTED',production_enabled=False))
    print(json.dumps(dict(status='PASS_REVIEW_PREPARATION',synthetic_cases=len(examples),replayed_records=len(rows),counts=dict(counts),model_executions_this_task=0)))


def seal():
    require(not (BATCH/'manifest.json').exists(),'Evidence already sealed')
    require(read(BATCH/'execution/assessment.json')['status']=='PASS_REVIEW_PREPARATION','Cannot seal failed evidence')
    protected=read(BATCH/'protected_before.json')['files']
    require(all(fingerprint(safe_path(ROOT,p['path']))==p for p in protected),'Protected original changed')
    sources=[ROOT/name for name in SOURCES]+[p for p in CONTRACT.rglob('*') if p.is_file()]
    for path in sources:
        dest=BATCH/'after'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(path.read_bytes())
    files=[fingerprint(p,BATCH) for p in sorted(BATCH.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    write_json(BATCH/'manifest.json',dict(sources=[fingerprint(p) for p in sources],files=files,scientific_signoff='NOT_GRANTED',production_enabled=False))


def verify():
    manifest=read(BATCH/'manifest.json')
    for base,entries in [(ROOT,manifest['sources']),(BATCH,manifest['files'])]:
        for entry in entries:
            require(fingerprint(safe_path(base,entry['path']),base)==entry,'Evidence/source hash changed: '+entry['path'])
    protected=read(BATCH/'protected_before.json')['files']
    require(all(fingerprint(safe_path(ROOT,p['path']))==p for p in protected),'Protected original changed')
    check_sources();check_examples();check_reference_inventory()
    assessment=read(BATCH/'execution/assessment.json');plan=read(BATCH/'expected_cases.json')
    require(assessment['status']=='PASS_REVIEW_PREPARATION' and assessment['declared_plan_sha256']==sha((BATCH/'expected_cases.json').read_bytes()),'Assessment/plan mismatch')
    expected=[]
    for case in plan['replay_cases']:
        expected.extend((case,raw) for raw in replay_case(case))
    require(len(expected)==len(assessment['replay_cases']),'Replay coverage incomplete')
    results=[]
    for row,(case,raw) in zip(assessment['replay_cases'],expected):
        for key in ['request','result']:
            require(fingerprint(safe_path(ROOT,row[key]['path']))==row[key],'Replay pair hash mismatch')
        request_bytes=safe_path(ROOT,row['request']['path']).read_bytes();request=json.loads(request_bytes)
        result=validate_result(read(safe_path(ROOT,row['result']['path'])),request,request_bytes)
        require(row['source_case']==case and result['raw_record']==raw,'Replay changed from original output')
        results.append(result)
    require(reference_comparison(results)==assessment['reference_comparison'],'Reference diagnostic changed')
    review=read(ROOT/'docs/project/phase1/PHASE1_REAL_W1_B2_REVIEW.json')
    require(review['scientific_signoff']=='NOT_GRANTED' and not review['production_enabled'],'Review promotes science')
    require(assessment['model_executions_this_task']==0 and not assessment['production_enabled'],'Replay claimed new inference/production')
    return dict(status='PASS_REVIEW_PREPARATION',synthetic_cases=len(plan['cases']),replayed_records=len(results),
        published_annotation_references=4,accepted_independent_holdouts=0,protected_files=len(protected),artifacts=len(manifest['files']),
        model_executions_this_task=0,scientific_signoff='NOT_GRANTED',production_status='NOT_DEPLOYED')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['execute','seal','verify'],default='verify',nargs='?')
    args=parser.parse_args()
    if args.mode=='execute': execute()
    elif args.mode=='seal': seal()
    else: print(json.dumps(verify()))
