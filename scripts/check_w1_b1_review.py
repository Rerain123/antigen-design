"""Validate B1 draft bindings and recorded parser evidence; never grants scientific qualification."""
import argparse
import copy
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator, FormatChecker
from check_w1_contract import strict_json
from prepare_w1_b1_review import ROOT, CONTRACT, fingerprint, read, sha, assert_observed

BATCH=ROOT/'discovery/t01-phase1-real/w1/b1-review-20260905'


def require(value,message):
    if not value: raise ValueError(message)


def local_path(base,relative):
    require(isinstance(relative,str) and relative and ':' not in relative and '\\' not in relative
            and not relative.startswith('/') and all(p not in ('','.','..') for p in relative.split('/')),'Unsafe evidence path')
    result=(base/relative).resolve()
    require(result.is_relative_to(base.resolve()),'Evidence escaped root')
    return result


def schema(value,name):
    validator=Draft202012Validator(read(CONTRACT/(name+'.schema.json')),format_checker=FormatChecker())
    errors=list(validator.iter_errors(value))
    require(not errors,'B1 draft schema: '+('; '.join(e.message for e in errors[:2])))


def identity(ref,run_id):
    require(ref['run_id']==run_id and ref['artifact_id'].startswith('t01p1r-artifact-'),'Cross-run or foreign artifact')
    for field,prefix in [('job_id','t01p1r-job-'),('attempt_id','t01p1r-attempt-')]:
        require(ref[field] is None or ref[field].startswith(prefix),'Foreign execution identity')
    require((ref['job_id'] is None)==(ref['attempt_id'] is None),'Partial execution identity')


def validate_request(value):
    schema(value,'request')
    require(value['run_id'].startswith('t01p1r-run-'),'Foreign run namespace')
    require(value['host_species'].strip(),'Empty host species')
    require(value['protein_sequence_sha256']==sha(value['protein_sequence'].encode()),'Sequence fingerprint mismatch')
    structure=value['structure_artifact'];identity(structure,value['run_id'])
    require(structure['role']=='input' and structure['job_id'] is None,'Structure must be a staged run input')
    inventory=value['inventory_artifact']
    if value['tool_id']=='t01.real.ingest_structure': require(inventory is None,'Ingest does not take an invented inventory')
    else:
        require(inventory is not None,'Mapping needs the bound ingest inventory')
        identity(inventory,value['run_id'])
        require(inventory['role']=='result' and inventory['job_id'] is not None
                and inventory['media_type']=='application/json','Inventory producer identity missing')
        require(inventory['artifact_id']!=structure['artifact_id'],'Structure and inventory identities overlap')
    return value


def validate_result(value,request,request_bytes):
    schema(value,'result');validate_request(request)
    require(value['tool_id']==request['tool_id'],'Result tool mismatch')
    binding=value['binding']
    require(binding['run_id']==request['run_id'] and binding['request_id']==request['request_id'],'Result request binding mismatch')
    require(binding['request_sha256']==sha(request_bytes),'Original request byte mismatch')
    require(binding['sequence_sha256']==request['protein_sequence_sha256']
            and binding['structure_sha256']==request['structure_artifact']['sha256'],'Result input hash mismatch')
    require(binding['job_id'].startswith('t01p1r-job-') and binding['attempt_id'].startswith('t01p1r-attempt-'),'Foreign result identity')
    if value['outcome']=='rejected':
        require(value['output_artifact'] is None and value['error_code'] is not None
                and value['mapping_status'] is None and value['ingestion_observation'] is None,'Rejected result contains normal output')
        return value
    require(value['error_code'] is None and value['output_artifact'] is not None,'Result/output mismatch')
    ref=value['output_artifact'];identity(ref,request['run_id'])
    require(ref['job_id']==binding['job_id'] and ref['attempt_id']==binding['attempt_id'],'Output belongs to another execution')
    require(ref['role']=='result' and ref['media_type']=='application/json'
            and ref['evidence_kind']=='ENGINEERING_FIXTURE','Draft example is not an engineering result')
    require(ref['artifact_id'] not in {request['structure_artifact']['artifact_id'],
            (request['inventory_artifact'] or {}).get('artifact_id')},'Output overwrites an input artifact identity')
    if value['tool_id']=='t01.real.ingest_structure':
        require(value['outcome']=='parsed' and value['mapping_status'] is None
                and value['ingestion_observation'] is not None,'Ingest must not claim a design mapping')
        observation=value['ingestion_observation']
        require(observation['auto_selected']==(request['selection']['chain_selector']=='AUTO'),'AUTO observation mismatch')
        require(request['selection']['model_index'] is None or observation['model_index']==request['selection']['model_index'],'Model selection mismatch')
        if not observation['auto_selected']:
            require(observation['chain_used']==request['selection']['chain_selector'],'Requested chain mismatch')
    else:
        require(value['outcome']=='candidate' and value['mapping_status'] in ('unverified','unreliable')
                and value['ingestion_observation'] is None,'Mapping must remain an unapproved candidate')
    return value


def verify(batch=BATCH,reparse=False):
    from probe_structure_mapping import mapping_validator
    from t01_structure_mapping.probe import parse_local,propose
    manifest=read(batch/'manifest.json')
    for base,rows in [(ROOT,manifest['sources']),(batch,manifest['outputs'])]:
        for row in rows:
            path=local_path(base,row['path'])
            require(fingerprint(path,base)==row,'Manifest hash mismatch: '+row['path'])
    source_manifest=read(CONTRACT/'source_manifest.json')
    for row in source_manifest['sources']:
        require(fingerprint(local_path(ROOT,row['path']))=={k:row[k] for k in ['path','sha256','size_bytes']},'Original source hash mismatch')
    require(sum(r['kind']=='EXPERT_ORIGINAL' for r in source_manifest['sources'])==22,'Incomplete expert search sources')
    planned=read(batch/'expected_cases.json');actual=read(batch/'assessment.json')
    require(planned['declared_before_execution'] is True,'Cases not predeclared')
    require(actual['declared_cases_sha256']==sha((batch/'expected_cases.json').read_bytes()),'Case plan drift')
    require(actual['scientific_mapping_approval']=='NOT_GRANTED' and actual['production_status']=='NOT_DEPLOYED','False qualification')
    require([c['id'] for c in planned['cases']]==[r['id'] for r in actual['cases']],'Case closure mismatch')
    for case in planned['cases']:
        input_path=local_path(batch,case['structure'])
        require(sha(input_path.read_bytes())==case['structure_sha256'],'Input changed')
        folder=batch/'results'/case['id']
        inventory=read(folder/'inventory.json') if (folder/'inventory.json').exists() else None
        mapping=read(folder/'mapping.json') if (folder/'mapping.json').exists() else None
        error=read(folder/'parse-error.json')['error'] if (folder/'parse-error.json').exists() else None
        assert_observed(case,inventory,mapping,error)
        if mapping:
            require(mapping_validator().validate_mapping(mapping)==[],'Mapping format mismatch')
            if reparse:
                fresh=parse_local(input_path)
                require(fresh==inventory,'Inventory reparse mismatch')
                require(propose(case['sequence'],fresh,evidence_kind=case['evidence_kind'],model_index=case['model_index'],
                                requested_chain=case['requested_chain'])==mapping,'Candidate reparse mismatch')
        elif reparse:
            try: parse_local(input_path)
            except (ValueError,KeyError) as exc: require(case['expected']['error_contains'] in str(exc),'Rejection reason drift')
            else: raise ValueError('Rejected file now parsed without review')
    registry=read(CONTRACT/'example_artifacts.json')
    require(registry['scope'].startswith('HAND_AUTHORED_'),'Example identities promoted to runtime-issued evidence')
    refs={}
    for row in registry['artifacts']:
        ref=row['ref'];data=local_path(ROOT,row['path']).read_bytes()
        require(sha(data)==ref['sha256'] and len(data)==ref['size_bytes'],'Example artifact hash mismatch')
        require(ref['artifact_id'] not in refs,'Duplicate example artifact')
        refs[ref['artifact_id']]=(ref,data)
    def artifact(ref):
        require(ref['artifact_id'] in refs and refs[ref['artifact_id']][0]==ref,'Unregistered example artifact')
        return refs[ref['artifact_id']][1]
    for name in ['ingest','map']:
        data=(CONTRACT/'examples'/(name+'-request.json')).read_bytes()
        request=validate_request(strict_json(data))
        result=validate_result(read(CONTRACT/'examples'/(name+'-result.json')),request,data)
        artifact(request['structure_artifact'])
        output=strict_json(artifact(result['output_artifact']))
        require(output['structure_sha256']==request['structure_artifact']['sha256'],'Output structure drift')
        detected=output['format']
        require(detected==('pdb' if request['declared_format']=='PDB' else 'mmcif'),'Declared format differs from detected content')
        if name=='map':
            inventory=strict_json(artifact(request['inventory_artifact']))
            require(inventory['structure_sha256']==output['structure_sha256'],'Inventory from different structure')
            require(output['sequence']==request['protein_sequence'] and output['mapping_status']==result['mapping_status'],'Mapping result mismatch')
            require(output['selection']==dict(requested_model_index=request['selection']['model_index'],
                    requested_chain_id=None if request['selection']['chain_selector']=='AUTO' else request['selection']['chain_selector']),
                    'Mapping belongs to another selection request')
            require(output['model_index'] is None or any(m['model_index']==output['model_index'] for m in inventory['models']),
                    'Mapping refers to a missing inventory model')
            require(output['review'] is None and not output['usable_for_pipeline'],'Mapping example approved itself')
        else:
            obs=result['ingestion_observation']
            model=next(m for m in output['models'] if m['model_index']==obs['model_index'])
            chain=next(c for c in model['chains'] if c['chain_id']==obs['chain_used'])
            require(''.join(r['one_letter'] or 'X' for r in chain['residues'] if r['residue_class']!='nonprotein')==obs['seq_extracted'],'Observed chain sequence drift')
    review=read(ROOT/'docs/project/phase1/PHASE1_REAL_W1_B1_REVIEW.json')
    require(review['production_enabled'] is False and review['scientific_signoff']=='NOT_GRANTED','Review falsely releases science')
    require(all(not m['production_enabled'] for m in review['modules']),'A module is incorrectly enabled')
    require(not any(t['production_enabled'] for t in read(CONTRACT.parent/'contract.json')['tools']),'Existing runtime qualification drift')
    return dict(status='PASS_REVIEW_PREPARATION',case_count=len(planned['cases']),expert_sources=22,
        request_result_pairs=2,reparsed=reparse,scientific_approval='NOT_GRANTED',production_status='NOT_DEPLOYED')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reparse',action='store_true');parser.add_argument('--batch',type=Path,default=BATCH)
    args=parser.parse_args()
    print(json.dumps(verify(args.batch,args.reparse),ensure_ascii=False))
