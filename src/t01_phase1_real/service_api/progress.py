"""Read-only projection of internal steps onto the 18 Phase 1 business nodes."""
from collections import Counter

from ..common import RuntimeFault, decode, sha

BUSINESS_NODES = tuple(f'N{i:02d}' for i in range(1, 19))
ACTIVE = ('stop_requested', 'awaiting_confirmation', 'ready', 'running', 'reconciling', 'queued')
FAILURES = ('failed', 'timed_out', 'cancelled')
GAPS = ('blocked', 'unavailable')
SETTLED = frozenset((*FAILURES, *GAPS, 'succeeded', 'skipped'))


def execution_status(rt, job_id, run_id):
    """Observe this child's bound worker receipt without dispatching or repairing it."""
    from pathlib import Path
    from ..files import no_links, read_locked
    from ..resident_execution import configuration, key
    try:
        job=rt.get(job_id)
        if job['run_id']!=run_id:raise ValueError('Foreign child run')
        if job['state'] not in ACTIVE:return dict(phase='finished',state=job['state'])
        if job.get('stop_reason') or job['state']=='stop_requested':return dict(phase='stopping')
        ex=rt.execution(job_id)
        if ex.get('backend')!='resident-process':
            return dict(phase='queued' if job['state']=='queued' else 'controller_active')
        if not ex.get('resident_target'):return dict(phase='preparing')
        config,_=configuration()
        root=Path(config['tools'][key(job['tool_id'])]['root'])
        target=no_links(Path(ex['resident_target']))
        if not target.is_absolute() or target.parent!=root:raise ValueError('Foreign worker path')
        request_path=target/'request.json'
        if not request_path.exists():return dict(phase='preparing')
        raw=read_locked(request_path,1024**2);request=decode(raw)
        binding={n:job[n] for n in ('job_id','attempt_id','execution_identity')}
        if request['binding']!=binding or request['execution_id']!=target.name:
            raise ValueError('Worker request binding differs')
        if ex.get('resident_request_sha256',sha(raw))!=sha(raw):raise ValueError('Worker request changed')
        path=target/'execution.json'
        if not path.exists():return dict(phase='waiting_worker',observation='request_committed_worker_receipt_absent')
        receipt=decode(read_locked(path,1024**2))
        if (receipt['binding']!=binding or receipt['execution_id']!=target.name
                or receipt['request_sha256']!=sha(raw) or receipt['backend']!='resident-process'):
            raise ValueError('Worker receipt binding differs')
        state=receipt['state']
        if receipt['stopped_confirmed'] is True:
            return dict(phase='finalizing',worker_state=state,stopped_confirmed=True)
        if state not in ('starting','running'):raise ValueError('Unknown worker state')
        return dict(phase='worker_starting' if state=='starting' else 'executing',worker_state=state,
                    stopped_confirmed=False,observation='bound_worker_receipt; not a live CPU sample')
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError):
        return dict(phase='unknown',reason_code='EXECUTION_OBSERVATION_UNAVAILABLE')


def project(nodes):
    groups = {node: [] for node in BUSINESS_NODES}
    for name, row in nodes.items():
        if row['node_id'] in groups:
            groups[row['node_id']].append((name, row['state']))
    progress = {}
    current = []
    for node, steps in groups.items():
        states = Counter(state for _, state in steps)
        complete = bool(steps) and all(state in SETTLED for _, state in steps)
        active = [dict(step=name, state=state, **({'execution':nodes[name]['execution']}
                  if 'execution' in nodes[name] else {})) for name, state in steps if state in ACTIVE]
        if active:
            current.append(node)
        state = next((s for s in ACTIVE if states[s]), None)
        if state is None:
            state = next((s for s in (*FAILURES, *GAPS) if states[s]), None)
        if state is None:
            if not complete:
                state = 'waiting' if any(s in SETTLED for _, s in steps) else 'not_executed'
            elif states['succeeded'] and states['skipped']:
                state = 'completed_with_skips'
            else:
                state = 'succeeded' if states['succeeded'] else 'skipped'
        progress[node] = dict(state=state, completed=complete, internal_steps=len(steps),
                              step_states=dict(states), active_steps=active)
    return dict(progress_unit='business_nodes', total_nodes=len(BUSINESS_NODES),
                completed_nodes=sum(row['completed'] for row in progress.values()),
                current_nodes=current, node_counts=dict(Counter(row['state'] for row in progress.values())),
                node_progress=progress,
                internal_step_counts=dict(total=len(nodes),
                    finished=sum(row['state'] in SETTLED for row in nodes.values()),
                    states=dict(Counter(row['state'] for row in nodes.values()))),
                progress_note='按 N01–N18 统计；已结束节点包含跳过或失败，不等于成功。内部步骤单列，节点数不是耗时百分比。reconciling 是控制器状态；waiting_worker 表示请求已提交但尚无 Worker 执行回执，executing 表示绑定的 Worker 回执记录执行中，finalizing 表示原生进程已确认停止、后端正在收集结果。unknown 不推定正在计算；回执不等于实时 CPU 采样。')
