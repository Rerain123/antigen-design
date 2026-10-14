"""N16 explicit expression-host branch for each N15 engineering selection."""
from ...common import ensure

ORDER=('codon',)+tuple('codon'+str(n) for n in range(2,21))


def candidate(rt,rows,name):
    if rows.get('variant_report',{}).get('state')!='succeeded':return None,'N15_NOT_COMPLETE'
    report=rt.result(rows['variant_report']['job_id'])['report']
    selection=report.get('engineering_selection') or {}
    if selection.get('sc10',{}).get('overall_pass') is not True:return None,'NO_QUALIFIED_CANDIDATE'
    ids=selection.get('top20',[]);slot=1 if name=='codon' else int(name[5:])
    ensure(len(ids)<=20 and len(ids)==len(set(ids)),'OUTPUT_INVALID','Invalid N15 candidate selection')
    if slot>len(ids):return None,'NO_CANDIDATE_IN_SLOT'
    matches=[r for r in report['records'] if r['id']==ids[slot-1]]
    ensure(len(matches)==1,'OUTPUT_INVALID','Selected N15 candidate missing')
    return matches[0],None


def request(rt,body,rows,name):
    from ..codon import policy
    from .service import source
    if body['expression_host'] is None:return None,'EXPRESSION_HOST_NOT_PROVIDED'
    row,reason=candidate(rt,rows,name)
    if reason:return None,reason
    return dict(protein_sequence=row['sequence'],user_sequence_id=body['user_sequence_id'],
        expression_host=body['expression_host'],host_profile=policy.PROFILE if body['expression_host']=='E.coli' else None,
        coding_policy=policy.CODING,input_kind='VERIFIED_N15_ENGINEERING_CANDIDATE',timeout_seconds=60,
        candidate_source=dict(source=source(rt,rows['variant_report']),candidate_id=row['id'])),None


def bindings(rt,body,rows):
    from .service import source,verified,recoverable_child_failure
    result=[]
    for name in ORDER:
        row=rows.get(name,{})
        if not row.get('job_id'):continue
        j=rt.get(row['job_id']);verified(rt,body,name,j['job_id'],rt.get(rows['variant_report']['job_id'])['run_id'],rows)
        ensure(j['state']=='succeeded' or recoverable_child_failure(body,name,j),'OUTPUT_INVALID','N16 branch not terminal')
        if j.get('attempt_id'):ensure(rt.execution(j['job_id']).get('tree_stopped') is True,'INVALID_STATE','DNA process not stopped')
        selected,reason=candidate(rt,rows,name)
        ensure(reason is None,'OUTPUT_INVALID','DNA source lost its candidate')
        result.append(dict(subject=selected['id'],source=source(rt,row)))
    return result
