"""Verified first-version scan terminals; assembly success never implies scan success."""
from ...common import decode, encode, ensure, sha
from ..workflow import service as workflow, engineering


def facts(rt, parent, request, rows, files, values):
    if not engineering.enabled(request):return None
    ensure(not parent.get('stop_reason') and parent['state'] in ('running','succeeded'),
           'INVALID_STATE','Stopped workflow cannot deliver partial scans')
    reference=values.get('wt_reference',{}).get('reference')
    ensure(reference is not None,'OUTPUT_INVALID','Verified WT reference required')
    ref_request=decode(files['input/wt_reference-request.json'])
    reference_job=workflow.verified(rt,request,'wt_reference',rows['wt_reference']['job_id'],parent['run_id'],rows)
    ensure(reference_job['state']=='succeeded','OUTPUT_INVALID','WT assembly must succeed')
    engines={}
    for engine in ('foldx','thermompnn'):
        name='wt_'+engine;row=rows.get(name,{})
        src=workflow.source(rt,row)
        ensure(src==ref_request['upstream'][engine],'FORBIDDEN','WT reference scan differs from workflow')
        expected,reason=workflow.request_for(rt,request,rows,name)
        item=reference['engines'][engine]
        if src is None:
            ensure(row.get('state')=='skipped','OUTPUT_INVALID','Missing scan is not an explicit skip')
            reserve=row.get('reason_code')=='N17_DOWNSTREAM_TIME_RESERVE'
            if reserve:
                ensure(expected is not None and row.get('reserve_seconds')==60 and
                       isinstance(row.get('remaining_seconds'),(int,float)) and 0<row['remaining_seconds']<=60,
                       'OUTPUT_INVALID','Invalid scan budget skip')
            else:
                ensure(expected is None and reason and reason==row.get('reason_code'),
                       'OUTPUT_INVALID','Scan skip differs from current verified inputs')
            ensure(item['state']=='missing' and not item['records'], 'OUTPUT_INVALID','Skipped scan has results')
            engines[engine]=dict(state='skipped',reason_code=row['reason_code'],source=None,
                actual_calculation='NOT_EXECUTED',requested_positions=None,displayed_positions=[],
                native_prediction_count=0,displayed_prediction_count=0,raw_artifacts=[],coverage=item.get('coverage'))
            continue
        job=workflow.verified(rt,request,name,src['job_id'],parent['run_id'],rows)
        actual=decode(rt._request_bytes(job))
        ensure(expected is not None and {k:v for k,v in actual.items() if k!='timeout_seconds'}==
               {k:v for k,v in expected.items() if k!='timeout_seconds'},
               'OUTPUT_INVALID','Scan request differs from workflow scope')
        ensure(0<actual['timeout_seconds']<=expected['timeout_seconds'],
               'OUTPUT_INVALID','Scan timeout exceeds its declared budget')
        scope=row.get('scan_scope')
        if scope is not None:
            ensure(sha(encode({k:v for k,v in scope.items() if k!='scope_sha256'}))==scope['scope_sha256'] and
                   actual['scope_source']['source_id'].endswith('scope_sha256='+scope['scope_sha256']),
                   'OUTPUT_INVALID','Persisted scan scope differs')
        succeeded=job['state']=='succeeded'
        ensure(succeeded or workflow.recoverable_child_failure(request,name,job),
               'OUTPUT_INVALID','Scan failure cannot be delivered as a recoverable gap')
        if job.get('attempt_id'):
            ensure(rt.execution(job['job_id']).get('tree_stopped') is True,
                   'INVALID_STATE','Scan process stop is not confirmed')
        ensure(item['state']==('available' if succeeded else 'failed'), 'OUTPUT_INVALID','Scan state differs')
        ensure(succeeded or not item['records'],'OUTPUT_INVALID','Failed scan cannot supply predictions')
        engines[engine]=dict(state=job['state'],reason_code=job['error_code'],source=src,request=actual,
            scan_scope=scope,actual_calculation='COMPLETED' if succeeded else 'FAILED_OR_TIMED_OUT',
            requested_positions=actual['scan_positions'],displayed_positions=item['effective_positions'],
            displayed_prediction_count=len(item['records']),native_prediction_count=None,
            raw_artifacts=[],coverage=item.get('coverage'))
    return dict(workflow_job_id=parent['job_id'],run_id=parent['run_id'],engines=engines,
        assembly_scan_invocations=0,full_scientific_scan=False,combined_ddg=None,consensus_ranking=reference.get('consensus_ranking'),
        scientific_permissions_inferred=False,authority='SOP v10.5 S-31 R39; first-version operational failure disclosure')
