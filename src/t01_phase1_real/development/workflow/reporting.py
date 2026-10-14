"""Execution facts are independent of scientific eligibility and release."""


def design_fact(nodes):
    revised=nodes.get('revision_design')
    if revised:
        formal=[r for k,r in nodes.items() if k in ('formal0','formal1','formal2') and r.get('job_id')]
        state=revised.get('state','not_executed')
        return dict(status='EXECUTED' if any(r.get('state')=='succeeded' for r in formal) else
                    'IN_PROGRESS' if formal and state!='succeeded' else 'NOT_EXECUTED',state=state,
                    reason_code=revised.get('reason_code'),detail='修订配置：预采样与正式候选分别记录',
                    job_id=None,confirmation=(nodes.get('design') or {}).get('confirmation'))
    row=nodes.get('design') or {}
    state=row.get('state','not_executed')
    reason=row.get('reason_code') or row.get('error_code')
    if not row:status='UNKNOWN'
    elif state=='succeeded' and (row.get('generation_status')=='not_generated_no_designable_positions'
                              or reason=='NO_DESIGNABLE_POSITIONS'):status='NOT_EXECUTED'
    elif state=='succeeded' and row.get('job_id'):status='EXECUTED'
    elif state=='awaiting_confirmation':status='AWAITING_CONFIRMATION'
    elif row.get('job_id') and state in ('failed','cancelled','timed_out'):status='FAILED_OR_STOPPED'
    elif row.get('job_id'):status='IN_PROGRESS'
    else:status='NOT_EXECUTED'
    return dict(status=status,state=state,reason_code=reason,detail=row.get('detail'),
                job_id=row.get('job_id'),confirmation=row.get('confirmation'))


def text(fact):
    label={'EXECUTED':'N11 候选设计已执行','AWAITING_CONFIRMATION':'N11 设计尚未执行，等待用户确认',
           'NOT_EXECUTED':'N11 候选设计未执行','FAILED_OR_STOPPED':'N11 已启动但失败或停止',
           'IN_PROGRESS':'N11 正在处理','UNKNOWN':'无法仅由本报告确认 N11 是否执行'}[fact['status']]
    reason=fact.get('reason_code')
    if reason:label+='；原因：'+reason
    if fact.get('detail'):label+='；详情：'+str(fact['detail'])
    return label+'。科学资格状态单独判断。'
