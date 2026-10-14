"""One persisted WT alignment preparation shared by all S28 AF3 rounds."""
from ...common import TERMINAL, RuntimeFault, ensure


def ready(rt, jid, body):
    from .service import _create_child, _record, source, verified
    from ..af3.msa import sources
    job=rt.get(jid); rows=rt.execution(jid)['nodes']
    initial=rows.get('prediction',{})
    if initial.get('state')=='succeeded':
        original=rt.get(initial['job_id'])
        if original['tool_id']=='t01.real.af3':
            verified(rt,body,'prediction',original['job_id'],job['run_id'],rows)
            ref=source(rt,initial)
            value=rt.result(original['job_id'])
            if any(r['path'].startswith('output/raw/app-output/') and r['path'].endswith('_data.json')
                   for r in value['raw_artifacts']):
                with rt._db() as db:sources(rt,db,dict(body,msa_source=ref),job['run_id'])
                return ref,None
    row=rows.get('wt_msa',{})
    if row.get('state')=='skipped':return None,row['reason_code']
    if not row.get('job_id'):
        req=dict(protein_sequence=body['protein_sequence'],user_sequence_id=body['user_sequence_id'],
                 host_species=body['host_species'],seed=1,timeout_seconds=7200,mode='msa_only')
        try: child=_create_child(rt,jid,'wt_msa',req)
        except RuntimeFault as exc:
            if exc.code!='ASSET_MISSING':raise
            _record(rt,jid,'wt_msa',dict(job_id=None,state='skipped',origin=None,reason_code='WT_MSA_ASSET_UNAVAILABLE'))
            return None,'WT_MSA_ASSET_UNAVAILABLE'
        if child is None:return None,'WAITING'
    else:child=row['job_id']
    state=rt.get(child)
    if state['state'] not in TERMINAL:
        if state['state']=='queued':rt.dispatch(child)
        else:rt.recover(child)
        state=rt.get(child)
    _record(rt,jid,'wt_msa',dict(rt.execution(jid)['nodes']['wt_msa'],state=state['state'],reason_code=state['error_code']))
    if state['state'] not in TERMINAL:return None,'WAITING'
    ensure(rt.execution(child).get('tree_stopped') is True, 'INVALID_STATE', 'WT MSA process stop not confirmed')
    if state['state']!='succeeded':
        ensure(state['error_code'] in ('TOOL_FAILED','TIMEOUT','ASSET_MISSING'),
               state['error_code'] or 'OUTPUT_INVALID','WT MSA integrity/cancellation failure')
        return None,'WT_MSA_'+state['error_code']
    verified(rt,body,'wt_msa',child,job['run_id'],rt.execution(jid)['nodes'])
    ref=source(rt,rt.execution(jid)['nodes']['wt_msa'])
    with rt._db() as db:sources(rt,db,dict(body,msa_source=ref),job['run_id'])
    return ref,None
