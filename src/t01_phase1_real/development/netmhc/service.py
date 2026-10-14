"""Resumable N05 pan controller over the existing same-run native jobs."""
import copy
import shutil
from datetime import datetime, timezone

from ...common import TERMINAL, RuntimeFault, decode, encode, ensure, new_id, now, sha
from ...winprocess import alive, current_identity
from . import policy
from .pan import MODE, aggregate, batches, manifest
from . import host_panel

BACKEND = 'netmhc-pan-controller'


def selected(rt, job):
    return job['tool_id'] == policy.TOOL and decode(rt._request_bytes(job)).get('panel_mode') in (MODE,host_panel.MODE)


def selected_manifest(body):
    return host_panel.manifest(body['host_species']) if body.get('panel_mode')==host_panel.MODE else manifest()


def stop_children(rt, jid):
    for child_id in rt.execution(jid).get('batches', []):
        child = rt.get(child_id)
        if child['state'] not in TERMINAL:
            rt.control(encode(dict(contract_version='0.1.0', operation='cancel', job_id=child_id,
                                  idempotency_key=jid+'-stop-'+child_id)))
            rt.reconcile(child_id)
    return all(rt.get(child_id)['state'] in TERMINAL for child_id in rt.execution(jid).get('batches', []))


def verified_batches(rt, parent, body, child_ids):
    """Stream one child result at a time; never merge millions of peptide rows."""
    for child_id in child_ids:
        job = rt.get(child_id)
        ensure(job['run_id'] == parent['run_id'] and job['tool_id'] == policy.TOOL,
               'FORBIDDEN', 'Pan child belongs to another run or tool')
        request = policy.request(rt._request_bytes(job))
        ensure(request.get('panel_mode') is None and request['host_species'] == body['host_species']
               and request['user_sequence_id'] == body['user_sequence_id'], 'OUTPUT_INVALID', 'Pan child binding differs')
        ref = next((r for r in job['artifacts'] if r['role'] in ('result','diagnostic')), None)
        ensure(ref is not None, 'OUTPUT_INVALID', 'Pan child has no terminal evidence')
        with rt._db() as db:
            _, _, result = rt._registered_result_artifact(db, ref, policy.TOOL)
        yield request, result, ref


def verify_sources(rt, parent, result):
    body = policy.request(rt._request_bytes(parent))
    panel = selected_manifest(body)
    refs = result.get('batch_sources', [])
    ensure([r['index'] for r in refs] == list(range(len(batches(body['protein_sequence'],panel)))),
           'OUTPUT_INVALID', 'Pan source batch indices differ')
    ids = [row['artifact']['job_id'] for row in refs]
    ensure(len(set(ids)) == len(ids), 'OUTPUT_INVALID', 'Pan source jobs are duplicated')
    channels, observed = aggregate(body['protein_sequence'], panel, verified_batches(rt,parent,body,ids))
    ensure(observed == refs and channels == result['channels'], 'OUTPUT_INVALID', 'Pan aggregate differs from its source artifacts')


def finish(rt, jid, body, panel, error=None):
    job = rt.get(jid); ex = rt.execution(jid)
    if not stop_children(rt,jid): return rt.get(jid)
    channels = dict(mhc_i=None, mhc_ii=None); refs = []
    if error is None and not job['stop_reason']:
        channels, refs = aggregate(body['protein_sequence'],panel,
                                  verified_batches(rt,job,body,ex['batches']))
    available = sum(c is not None and c['status'] != 'unavailable' for c in channels.values())
    binding = {k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'], sequence_sha256=sha(body['protein_sequence'].encode()))
    value = dict(contract_version='0.2.0', tool_id=policy.TOOL, scope='N05_NETMHC_PACKAGE_PAN' if body['panel_mode']==MODE else 'N05_NETMHC_HOST_PANEL', binding=binding,
        user_sequence_id=body['user_sequence_id'], host_species=body['host_species'],
        qualification='DEVELOPMENT_UNREVIEWED', evidence_kind='G0_REAL_OUTPUT', usable_for_pipeline=False,
        automatic_handoff=False, scientific_signoff=None, production_status='NOT_DEPLOYED', requires_review=True,
        status='raw_predictions_unreviewed' if available == 2 else 'partial_unreliable' if available else 'unreliable',
        null_reason=error or (None if available else 'ALL_CHANNELS_UNAVAILABLE'), channels=channels, batch_sources=refs,
        panel_selection=dict(mode=MODE, mhc_tier='pan_allele', pan_allele_warning=True, near_species_warning=False,
            pig_mhc_ii_degraded=None, host_mapping_applied=False, open_item='OI-003',
            panel_manifest_sha256=panel['sha256'], requested_counts={k:c['count'] for k,c in panel['channels'].items()},
            completed_batches=len(refs), required_batches=len(batches(body['protein_sequence'],panel))),
        method_summary=dict(classification_source='native BindLevel; never recomputed',
            peptide_rows='All rows retained in same-run child artifacts', scientific_rules_approved=False),
        execution=dict(error_code=error,exit_code=1 if error else 0,stopped_confirmed=True,network_used=False,backend=BACKEND),
        warnings=[dict(code='PAN_ALLELE_FALLBACK',severity='WARNING',level='quality',
            message='宿主专用面板未交付；按 A1 §7 使用固定工具包完整 pan-allele 清单，不代表目标宿主覆盖。')])
    if available != 2:
        value['warnings'].append(dict(code='PAN_CHANNEL_INCOMPLETE',severity='WARNING',level='failure',
            message='至少一个通道未完整覆盖计划清单；该通道不可用，不将部分批次解释为完整面板结果。'))
    if body['panel_mode']==host_panel.MODE:
        value['panel_selection'].update(mode=host_panel.MODE,mhc_tier=None,pan_allele_warning=False,
            host_mapping_applied=True,provisional=True,panel_id=panel['panel_document']['panel_id'],
            project_spec_annex_provided=False,population_coverage_validated=False,
            unavailable_reasons=panel['panel_document']['unavailable_reasons'],
            panel_document=panel['panel_document'])
        if not panel['channels']['mhc_ii']['count']:
            from ..expert_feedback import authority
            value['panel_selection'].update(pig_mhc_ii_degraded=False,pig_mhc_ii_assessment='NOT_ASSESSED',
                degradation_factor_applied=False,breed_coverage='NOT_ASSESSED',expert_authority=authority())
        value['warnings']=[w for w in value['warnings'] if w['code']!='PAN_ALLELE_FALLBACK']
        value['warnings'].append(dict(code='PROVISIONAL_HOST_PANEL',severity='WARNING',level='quality',
            message='探索性SLA-I面板，品种覆盖未评估。猪MHC-II一期未评估；面板缺失不启用0.85降级系数。'))
    value['panel_selection']['package_availability']={k:c.get('availability') for k,c in panel['channels'].items()}
    if any((c.get('availability') or {}).get('excluded_alleles') for c in panel['channels'].values()):
        value['warnings'].append(dict(code='PACKAGE_DECLARED_ALLELES_WITHOUT_NATIVE_MODEL',severity='WARNING',level='quality',
            message='原工具声明清单含缺少模型伪序列的名称；完整执行可用清单，逐项披露无法执行的原名及工具包哈希，不替换为其他 allele。'))
    ensure(len(encode(value)) <= 32*1024**2, 'OUTPUT_INVALID', 'Pan summary exceeds the result envelope')
    return rt._finish_development(jid,dict(ex,dispatcher=None,tree_stopped=True),
        {'input.json':rt._request_bytes(job),'output/pan-manifest.json':encode(panel)},value)


def dispatch(rt, jid):
    with rt._tx() as db:
        before = rt._job(db,jid)
        if before['state'] in TERMINAL: return before
        body = policy.request(rt._input(db,before['request_artifact'],before['run_id']))
        ex = rt._execution(db,jid)
        if ex.get('dispatcher') and alive(ex['dispatcher']): return before
        if before['state'] == 'queued':
            job = copy.deepcopy(before)
            job.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                       lease_epoch=1,started_at=now())
            ex = dict(backend=BACKEND,batches=[],phase='scheduling',tree_stopped=False,started_at=job['started_at'])
            rt._store(db,job,before,'pan_controller_claimed')
        ex['dispatcher'] = current_identity(); rt._execution_store(db,jid,ex)
    panel = selected_manifest(body)
    try:
        ensure(before['execution_profile'] == policy.registered_profile(), 'PROFILE_NOT_APPROVED', 'Pan controller profile changed')
        plan = batches(body['protein_sequence'],panel)
        if not ex['batches']:
            predicted_rows=sum(panel['channels'][k]['count']*sum(max(0,len(body['protein_sequence'])-n+1)
                for n in lengths) for k,lengths in [('mhc_i',policy.MHC_I_LENGTHS),('mhc_ii',policy.MHC_II_LENGTHS)])
            # Budget includes native tables, parsed rows and immutable published
            # copies. This is an execution guard, never a smaller allele panel.
            required=predicted_rows*1400+256*1024**2
            free=shutil.disk_usage(rt.root).free
            with rt._tx() as db:
                current=rt._execution(db,jid);current['storage_preflight']=dict(
                    predicted_native_rows=predicted_rows,required_bytes=required,free_bytes=free)
                rt._execution_store(db,jid,current)
            ensure(free>=required,'ASSET_MISSING','Insufficient storage for the complete pan panel; no allele subset was executed')
        if ex.get('fatal_error'): return finish(rt,jid,body,panel,ex['fatal_error'])
        for part in plan:
            job = rt.get(jid); ex = rt.execution(jid)
            elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(ex['started_at'].replace('Z','+00:00'))).total_seconds()
            if elapsed >= body['timeout_seconds'] and not job['stop_reason']:
                with rt._tx() as db: rt._stop(db,rt._job(db,jid),'timeout')
                job = rt.get(jid)
            if job['stop_reason']: return finish(rt,jid,body,panel)
            if part['index'] < len(ex['batches']):
                child_id = ex['batches'][part['index']]
                child = rt.get(child_id)
                if child['state'] in TERMINAL: continue
            else:
                request = {k:body[k] for k in ('protein_sequence','host_species','user_sequence_id')}
                request.update(mhc_i_alleles=part['mhc_i_alleles'],mhc_ii_alleles=part['mhc_ii_alleles'],
                               timeout_seconds=min(900,max(1,int(body['timeout_seconds']-elapsed))))
                if body['panel_mode']==host_panel.MODE:request['host_panel_sha256']=panel['sha256']
                with rt._tx() as db:
                    parent=rt._job(db,jid); current=rt._execution(db,jid)
                    if parent['stop_reason']: return parent
                    ensure(len(current['batches']) == part['index'], 'INVALID_STATE', 'Pan batch schedule changed')
                    ref=rt._stage(db,parent['run_id'],encode(request),policy.TOOL)
                    from ..workflow.service import envelope
                    req=envelope(parent['run_id'],ref,policy,jid+'-batch-'+str(part['index']))
                    rt._admit(db,req); child=rt._new_job(db,req,encode(req)); child_id=child['job_id']
                    current['batches'].append(child_id); rt._execution_store(db,jid,current)
                    rt._store(db,copy.deepcopy(parent),parent,'pan_batch_submitted')
            if rt.get(child_id)['state']=='queued': rt.dispatch(child_id)
            else: rt.recover(child_id)
            if rt.get(child_id)['state'] not in TERMINAL: return rt.get(jid)
        return finish(rt,jid,body,panel)
    except (RuntimeFault,ValueError,KeyError,TypeError) as exc:
        code=getattr(exc,'code','OUTPUT_INVALID')
        with rt._tx() as db:
            ex=rt._execution(db,jid); ex.update(fatal_error=code,diagnostic=str(exc)); rt._execution_store(db,jid,ex)
        return finish(rt,jid,body,panel,code)
    finally:
        with rt._tx() as db:
            ex=rt._execution(db,jid); ex['dispatcher']=None; rt._execution_store(db,jid,ex)
