"""Assess/seal or read-only verify B2 development executions and artifact fault copies."""
import argparse
import copy
import json
from pathlib import Path
import re
import shutil

from b2_boundary_evidence import (BATCH, IMAGE, OLD, ROOT, SOURCES, assess_bundle, digest,
    fingerprint, inventory, load_old, read, require, verify_files, write_new)


def portable_assessment(value):
    """Normalize only embedded repository roots in historical diagnostics."""
    normalized=copy.deepcopy(value)
    for diagnostic in normalized.get('diagnostics',[]):
        message=diagnostic.get('message')
        if not isinstance(message,str):continue
        portable=re.sub(r'[\\/]+','/',message)
        marker='/discovery/t01-phase1-real/'
        if marker in portable:
            diagnostic['message']='<PROJECT_ROOT>'+marker+portable.split(marker,1)[1]
    return normalized


def verify_execution(batch, row):
    folder=batch/'runs'/row['id']
    execution=read(folder/'execution.json')
    command=read(folder/'command.json')
    inspected=read(folder/'container_inspect.json')[0]
    require(execution['command']==command['command'] and execution['sources']==command['sources'], 'Execution command/source binding differs')
    verify_files(ROOT,execution['sources'])
    require(execution['plan_sha256']==digest(batch/'plan.json') and execution['input_sha256']==digest(ROOT/row['input']['path'])
        and execution['input_sha256']==digest(folder/'input.fasta'), 'Plan/input binding differs')
    require(execution['assets_verified_before']==execution['assets_verified_after']==41,'Missing actual asset checks')
    require(execution['image_id']==inspected['Config']['Image']==IMAGE,'Wrong actual image')
    config=inspected['HostConfig']; state=inspected['State']
    require(config['NetworkMode']=='none' and config['ReadonlyRootfs'],'Offline/read-only isolation differs')
    require(config['Memory']==config['MemorySwap']==10*1024**3 and config['NanoCpus']==8*10**9
        and config['CpusetCpus']=='0-7' and config['PidsLimit']==512,'Actual resource limits differ')
    require(set(config['Tmpfs'])=={'/tmp'},'Unexpected writable temporary mount')
    mounts={m['Destination']:m for m in inspected['Mounts']}
    require(set(mounts)=={'/app','/input.fasta','/probe.py','/out'},'Unexpected bind mount')
    require(all(not mounts[p]['RW'] for p in ['/app','/input.fasta','/probe.py']) and mounts['/out']['RW'],'Writable source/input or unavailable output')
    require(not state['Running'] and execution['stopped_confirmed'] and state['Status']=='exited','Stop not confirmed')
    require(execution['container_exit_code']==state['ExitCode'] and execution['oom_killed']==state['OOMKilled'],'Wrong exit evidence')
    require(execution['remove_exit_code']==0 and execution['production_status']=='NOT_DEPLOYED','Cleanup or qualification differs')
    verify_files(folder/'output',execution['artifacts'],exact=True)
    runtime=read(folder/'output/runtime_started.json')
    require(runtime['network_interfaces']==[[1,'lo']] and not runtime['cuda_available'],'CPU/offline evidence differs')
    result=assess_bundle(folder,row['sequence'],row['internal_id'])
    expectation='MET'
    if row['outcome']=='EXPECT_COMPLETE_RAW':
        require(result['status']=='COMPLETE_RAW_ONLY','Expected complete safe-ID run: '+str(result['diagnostics']))
    if row['outcome']=='EXPECT_EXECUTION_FAILURE':
        if execution['container_exit_code']==0:
            # Preserve the original unmet expectation, not a new acceptance policy.
            events=[json.loads(line) for line in (folder/'output/token_trace.jsonl').read_text().splitlines()]
            require(row['id']=='invalid-symbol' and row['sequence']=='ACDEFGHIK*'
                and events[0]['token_ids'][-2]==3 and events[0]['decoded_tokens'][-2]=='<unk>'
                and result['status']=='REJECTED' and result['diagnostics'][0]['message']=='TOKEN_RECONSTRUCTION_MISMATCH',
                'Unexpected original process success or missing rejection')
            expectation='NOT_MET_ORIGINAL_TOOL_ACCEPTED_INVALID_SYMBOL'
        else:
            require(result['status']=='REJECTED','Failed process was accepted')
    if result['status']=='REJECTED':
        require(result['diagnostics'] and ((folder/'stdout.txt').stat().st_size or (folder/'stderr.txt').stat().st_size),'Failed run lacks diagnostics')
    require(result['usable_for_pipeline'] is False and result['topology'] is None,'Development result promoted to consumption')
    return dict(case=row['id'],input_kind=row['kind'],outcome=row['outcome'],expectation=expectation,result=result,
        execution=fingerprint(folder/'execution.json'),container_exit_code=execution['container_exit_code'],
        elapsed_seconds=execution['elapsed_seconds'],oom_killed=execution['oom_killed'],timed_out=execution['timed_out'])


def mutate(folder, kind, identifier):
    output=folder/'output'; result=output/'result'
    paths={'prediction':result/'predicted_topologies.3line','regions':result/'TMRs.gff3',
        'probability':result/'probabilities'/(identifier+'_probs.csv'),'plot':result/'plot.png',
        'report':result/'deeptmhmm_results.md','token-trace':output/'token_trace.jsonl'}
    if kind.startswith('missing-'):
        paths[kind[len('missing-'):]].unlink()
    elif kind in {'truncated-labels','wrong-sequence','wrong-id'}:
        lines=paths['prediction'].read_text().splitlines()
        if kind=='truncated-labels': lines[2]=lines[2][:-1]
        elif kind=='wrong-sequence': lines[1]='Z'+lines[1][1:]
        else: lines[0]=lines[0].replace(identifier,'wrong_id')
        paths['prediction'].write_text('\n'.join(lines)+'\n')
    elif kind=='wrong-region':
        lines=paths['regions'].read_text().splitlines()
        for index,line in enumerate(lines):
            if not line.startswith('#') and '\t' in line:
                cols=line.split('\t'); cols[2]='2'; lines[index]='\t'.join(cols); break
        paths['regions'].write_text('\n'.join(lines)+'\n')
    elif kind in {'nan-probability','wrong-probability-position'}:
        lines=paths['probability'].read_text().splitlines(); cols=lines[2].split(',')
        if kind=='nan-probability': cols[1]='nan'
        else: cols[0]='999 '+cols[0].split(' ')[1]
        lines[2]=','.join(cols); paths['probability'].write_text('\n'.join(lines)+'\n')
    elif kind=='hash-tamper':
        paths['prediction'].write_bytes(paths['prediction'].read_bytes()+b'\n')
    elif kind=='unexpected-artifact':
        (output/'unregistered.txt').write_text('injected unregistered artifact')
    elif kind=='invalid-plot':
        paths['plot'].write_bytes(b'broken png')
    elif kind=='wrong-report-id':
        paths['report'].write_text(paths['report'].read_text().replace(identifier,'wrong_id'))
    elif kind=='wrong-token':
        events=[json.loads(line) for line in paths['token-trace'].read_text().splitlines()]
        events[0]['decoded_tokens'][1]='Z'
        paths['token-trace'].write_text(''.join(json.dumps(e)+'\n' for e in events))
    else:
        raise ValueError('Unknown declared fault')
    if kind not in {'hash-tamper','unexpected-artifact'}:
        execution=read(folder/'execution.json')
        execution['artifacts']=inventory(output)
        (folder/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')


def assess(batch):
    require(not (batch/'assessment.json').exists(),'Preserve previous assessment')
    plan=read(batch/'plan.json')
    verify_files(ROOT,read(batch/'protected_before.json')['files'])
    rows=[verify_execution(batch,row) for row in plan['cases']]
    safe=next(row for row in plan['cases'] if row['id']=='safe-id')
    source=batch/'runs/safe-id'
    faults=[]
    for kind in plan['fault_cases']:
        target=batch/'runs'/('fault-'+kind)
        require(not target.exists(),'Preserve previous fault copy')
        target.mkdir(parents=True)
        for name in ['input.fasta','execution.json','stdout.txt','stderr.txt']:
            shutil.copyfile(source/name,target/name)
        shutil.copytree(source/'output',target/'output')
        mutate(target,kind,safe['internal_id'])
        write_new(target/'fault.json',dict(kind='POST_EXECUTION_ARTIFACT_FAULT_COPY',fault=kind,
            original_source_execution=fingerprint(source/'execution.json'),original_outputs=read(source/'execution.json')['artifacts'],
            model_execution_this_fault=False, semantic_fault_has_updated_copy_inventory=kind not in {'hash-tamper','unexpected-artifact'}))
        result=assess_bundle(target,safe['sequence'],safe['internal_id'])
        write_new(target/'assessment.json',result)
        require(result['status']=='REJECTED' and result['diagnostics'] and result['raw_record'] is None,'Artifact fault was accepted: '+kind)
        faults.append(dict(case=kind,assessment=fingerprint(target/'assessment.json'),diagnostics=result['diagnostics']))
    old=load_old('audit_raw').audit_case('short')
    original=next(iter(old['records'].values()))
    fresh=rows[0]['result']['raw_record']
    comparison=dict(labels_equal=fresh['labels']==original['labels'],type_equal=fresh['type']==original['type'],
        segments_equal=fresh['segments']==original['segments'],original_source=fingerprint(OLD/'runs/short/output/result/predicted_topologies.3line'),
        kind='DEVELOPMENT_ID_REGRESSION_NOT_SCIENTIFIC_ACCURACY')
    require(all(comparison[k] for k in ['labels_equal','type_equal','segments_equal']),'Safe ID changed observed labels/type/segments')
    result=dict(status='PASS_DEVELOPMENT_EVIDENCE_WITH_ORIGINAL_TOOL_FINDING',stage='W1-08B2',real_cases=rows,fault_cases=faults,
        original_tool_expectations_not_met=[r['case'] for r in rows if r['expectation']!='MET'],
        finding=dict(id='B2-E01',kind='ORIGINAL_TOKENIZER_SILENT_UNKNOWN_SUBSTITUTION',
            input='ACDEFGHIK*',original_exit_code=0,unknown_token_id=3,unknown_decoded_token='<unk>',
            impact='Original package does not enforce project input domain. Keep INVALID_SEQUENCE_SYMBOL preflight and exact token reconstruction guard.',
            production_input_domain_expanded=False),
        safe_id_comparison=comparison,model_invocations=len(rows),complete_raw_outputs=sum(r['result']['status']=='COMPLETE_RAW_ONLY' for r in rows),
        original_process_failures=sum(r['container_exit_code']!=0 for r in rows),artifact_faults_rejected=len(faults),
        independent_scientific_holdouts_accepted=0,scientific_signoff='NOT_GRANTED',formal_adapter_release='NOT_GRANTED',production_status='NOT_DEPLOYED')
    write_new(batch/'assessment.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['real_cases','fault_cases','safe_id_comparison']}))


def seal(batch):
    require(not (batch/'manifest.json').exists(),'Already sealed')
    require(read(batch/'assessment.json')['status']=='PASS_DEVELOPMENT_EVIDENCE_WITH_ORIGINAL_TOOL_FINDING','Cannot seal unsuccessful assessment')
    verify_files(ROOT,read(batch/'protected_before.json')['files'])
    for name in SOURCES:
        dest=batch/'code_snapshot'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f: f.write((ROOT/name).read_bytes())
    write_new(batch/'manifest.json',dict(files=inventory(batch),sources=[fingerprint(ROOT/name) for name in SOURCES],
        decision_source=fingerprint(ROOT/'docs/project/sources/PHASE1_W1_B2_BOUNDARY_EXECUTION_20260906.json'),
        scientific_signoff='NOT_GRANTED',production_status='NOT_DEPLOYED'))


def verify_historical_sources(batch, entries):
    """Verify execution-time bytes, allowing only explicitly archived evolving checkers.

    A live documentation checker is not part of the scientific execution. Its
    original snapshot, already protected by the old manifests, remains the source
    of truth for this historical run. Never rewrite a manifest to current hashes.
    """
    snapshots={
        'scripts/check_b2_boundaries.py':batch/'code_snapshot/scripts/check_b2_boundaries.py',
        'scripts/check_docs.py':ROOT/'discovery/t01-phase1-real/w1/b2-review-maintenance-20260906/doc-checker-fix/after/scripts/check_docs.py',
        'tests/test_docs.py':ROOT/'discovery/t01-phase1-real/w1/b2-review-maintenance-20260906/doc-checker-fix/after/tests/test_docs.py',
    }
    for entry in entries:
        if entry['path'] in snapshots:
            original=snapshots[entry['path']]
            require(original.is_file() and digest(original)==entry['sha256'] and original.stat().st_size==entry['size_bytes'],
                'HISTORICAL_CHECKER_SNAPSHOT_MISMATCH: '+entry['path'])
        else:verify_files(ROOT,[entry])


def verify(batch):
    manifest=read(batch/'manifest.json'); verify_files(batch,manifest['files'])
    require({e['path'] for e in inventory(batch)}=={e['path'] for e in manifest['files']}|{'manifest.json'},'Batch inventory drift')
    verify_historical_sources(batch,manifest['sources'])
    verify_historical_sources(batch,read(batch/'protected_before.json')['files'])
    verify_files(ROOT,[manifest['decision_source']])
    expected=read(batch/'assessment.json'); plan=read(batch/'plan.json')
    require([verify_execution(batch,row) for row in plan['cases']]==expected['real_cases'],'Real execution assessment drift')
    require(expected['original_tool_expectations_not_met']==['invalid-symbol']
        and expected['finding']['production_input_domain_expanded'] is False,'Original unexpected acceptance hidden')
    require(expected['complete_raw_outputs']==10 and expected['original_process_failures']==2
        and expected['model_invocations']==13,'Execution outcome summary differs')
    finding=read(batch/'source_finding.json')
    require(finding['expectation_status']=='NOT_MET' and finding['finding']==expected['finding'],'Original finding drift')
    verify_files(ROOT,[finding[k] for k in ['original_plan','original_execution','original_token_trace',
        'first_assessment_failure','initial_checker','existing_input_guard','current_post_execution_guard']])
    method=read(batch/'method_summary.executed.json')
    verify_files(ROOT,[method['base_declaration'],method['base_original_method']])
    require(method['image_id']==IMAGE and method['model_execution']=='EXECUTED_OFFLINE_CPU'
        and method['exit_zero']==11 and method['exit_one']==2 and method['complete_raw_outputs']==10,
        'Executed method summary differs')
    require([r['case'] for r in method['runs']]==[r['id'] for r in plan['cases']],'Executed method coverage differs')
    for observation,case in zip(method['runs'],plan['cases']):
        folder=batch/'runs'/case['id']; runtime=read(folder/'output/runtime.json')
        verify_files(ROOT,[observation['runtime'],observation['trace']])
        events=[json.loads(line) for line in (folder/'output/token_trace.jsonl').read_text().splitlines()]
        tokens=next((e for e in events if e['event']=='tokenized'),None)
        require(observation['amino_acids']==len(case['sequence'])
            and observation['token_count']==(tokens['token_count'] if tokens else None)
            and observation['chunk_token_counts']==[len(e['token_ids']) for e in events if e['event']=='chunk_completed']
            and observation['peak_rss_kib']==runtime['peak_rss_kib'],'Actual token/resource summary differs')
    safe=next(r for r in plan['cases'] if r['id']=='safe-id')
    require([r['case'] for r in expected['fault_cases']]==plan['fault_cases'],'Fault coverage drift')
    for row in expected['fault_cases']:
        folder=batch/'runs'/('fault-'+row['case'])
        result=assess_bundle(folder,safe['sequence'],safe['internal_id'])
        require(portable_assessment(result)==portable_assessment(read(folder/'assessment.json'))
            and result['status']=='REJECTED','Fault assessment drift')
    require(expected['scientific_signoff']=='NOT_GRANTED' and expected['formal_adapter_release']=='NOT_GRANTED'
        and expected['production_status']=='NOT_DEPLOYED','Unapproved qualification')
    return dict(status='PASS_DEVELOPMENT_EVIDENCE_WITH_ORIGINAL_TOOL_FINDING',real_invocations=len(plan['cases']),
        original_tool_expectations_not_met=['invalid-symbol'],
        complete_raw_outputs=expected['complete_raw_outputs'],original_process_failures=expected['original_process_failures'],
        artifact_faults_rejected=len(expected['fault_cases']),artifacts=len(manifest['files']),
        protected_files=len(read(batch/'protected_before.json')['files']),production_status='NOT_DEPLOYED')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['assess','seal','verify'])
    parser.add_argument('--batch',type=Path,default=BATCH)
    args=parser.parse_args(); batch=args.batch.resolve()
    require(batch.is_relative_to(ROOT),'Batch outside project')
    if args.mode=='assess': assess(batch)
    elif args.mode=='seal': seal(batch)
    else: print(json.dumps(verify(batch)))
