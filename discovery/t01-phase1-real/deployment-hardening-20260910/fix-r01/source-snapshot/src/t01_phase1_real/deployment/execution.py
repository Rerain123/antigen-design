"""Kubernetes scheduling bridge for already staged Runtime attempts.

Raw target output is collected with a review diagnostic. Existing Docker result
validators must not be bypassed or given fabricated loopback/CPU observations.
"""
import copy
import os
from pathlib import Path
from ..common import RuntimeFault,TERMINAL,decode,encode,ensure,sha,now
from ..files import read_locked,within
from .launcher import API,Launcher,ClusterError
from .kubernetes import scientific_job_spec

def enabled():return os.name=='posix' and bool(os.environ.get('T01_KUBERNETES_CONFIG_FILE'))

def configuration():
    path=Path(os.environ['T01_KUBERNETES_CONFIG_FILE'])
    ensure(path.is_absolute(),'INVALID_REQUEST','Absolute Kubernetes configuration file required')
    raw=read_locked(path,65536);value=decode(raw)
    fields={'server','token_file','ca_file','namespace','runtime_claim','runtime_volume_root','control_image','tools'}
    ensure(isinstance(value,dict) and set(value)==fields and isinstance(value['tools'],dict),
           'INVALID_REQUEST','Exact trusted Kubernetes configuration required')
    ensure(Path(value['runtime_volume_root']).is_absolute(),'INVALID_REQUEST','Absolute mounted runtime volume root required')
    return value,sha(raw)

def reconcile(rt,job_id,*,client=None):
    from ..development.registry import spec,result as build_result
    from ..winprocess import initialization_lock
    from ..development.supervisor import output_files
    with initialization_lock('t01-kubernetes-'+sha((str(rt.root)+':'+job_id).encode())):
        job=rt.get(job_id);ex=rt.execution(job_id)
        if job['state'] in TERMINAL:return job
        worker=spec(job['tool_id']);body=worker.request(rt._request_bytes(job));path=rt.attempt_path(job)
        try:
            config,fingerprint=configuration()
            ensure(ex.get('kubernetes_config_sha256',fingerprint)==fingerprint,'PROFILE_NOT_APPROVED','Kubernetes configuration changed')
            launcher=Launcher(client or API(config['server'],config['token_file'],config['ca_file']),config['namespace'])
            if 'kubernetes_spec' not in ex:
                # Validate local source/model inventories before any remote submit.
                worker.verify_assets()
                tool='structure' if job['tool_id']=='t01.real.ingest_structure' else job['tool_id'].rsplit('.',1)[1].replace('_','-')
                entry=config['tools'].get(tool)
                ensure(isinstance(entry,dict) and set(entry)=={'image','asset_claim','gpu_resource_key'},'ASSET_MISSING','Explicit target tool image/assets mapping required')
                volume_root=Path(config['runtime_volume_root']).resolve()
                staged=within(rt.root,path).resolve()
                ensure(staged.is_relative_to(volume_root),'FORBIDDEN','Attempt is outside the shared runtime volume')
                manifest=scientific_job_spec(tool,job['attempt_id'].split('-')[-1][:24],scientific_image=entry['image'],
                    control_image=config['control_image'],runtime_claim=config['runtime_claim'],asset_claim=entry['asset_claim'],
                    namespace=config['namespace'],gpu_resource_key=entry['gpu_resource_key'],timeout_seconds=body['timeout_seconds'],
                    attempt_path=staged.relative_to(volume_root).as_posix(),runtime_job_id=job_id)
                manifest['metadata']['annotations']['t01.openai/not-submitted']='false'
                manifest['spec']['template']['metadata']['annotations']['t01.openai/not-submitted']='false'
                ex.update(backend='kubernetes',phase='kubernetes_submit_intent',kubernetes_spec=manifest,
                          kubernetes_config_sha256=fingerprint)
                with rt._tx() as db:rt._execution_store(db,job_id,ex)
            binding={k:job[k] for k in ('job_id','attempt_id','execution_identity','request_artifact','execution_profile')}
            # Cancellation prior to submission must not launch a Job.
            job=rt.get(job_id)
            if job['stop_reason'] and not ex.get('kubernetes_receipt'):
                # A previous submission response might have been lost; resolve
                # exact deterministic Job name before deciding that none exists.
                status,observed=launcher.api('GET',launcher.jobs+'/'+ex['kubernetes_spec']['metadata']['name'])
                if status==404:return finish(rt,job,ex,{},'CANCELLED')
            if job['stop_reason'] and ex.get('kubernetes_receipt'):
                receipt=ex['kubernetes_receipt']
            else:
                receipt=launcher.submit(ex['kubernetes_spec'],binding,ex.get('kubernetes_receipt'))
            ex.update(kubernetes_receipt=receipt,phase='kubernetes_observing')
            with rt._tx() as db:rt._execution_store(db,job_id,ex)
            job=rt.get(job_id)
            if job['stop_reason']:
                if not ex.get('kubernetes_cancel_intent'):
                    ex['kubernetes_cancel_intent']=True
                    with rt._tx() as db:rt._execution_store(db,job_id,ex)
                launcher.cancel(receipt)
                observation=launcher.observe_stop(receipt)
            else:observation=launcher.observe(receipt)
            ex['kubernetes_observation']=observation
            with rt._tx() as db:rt._execution_store(db,job_id,ex)
            if not observation['stopped_confirmed']:return rt.get(job_id)
            error='PROFILE_NOT_APPROVED' if observation['state']=='succeeded' else 'TOOL_FAILED'
            if observation['reason_code']=='DeadlineExceeded':
                with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
                job=rt.get(job_id);error='TIMEOUT'
            files=output_files(rt,job)
            files['kubernetes-observation.json']=encode(observation)
            return finish(rt,job,ex,files,error)
        except ClusterError as exc:
            ex['kubernetes_diagnostic']={'code':exc.code,'message':str(exc)}
            with rt._tx() as db:rt._execution_store(db,job_id,ex)
            # API absence, foreign UID, lost response: no stop confirmation.
            if ex.get('kubernetes_spec'):return rt.get(job_id)
            return finish(rt,job,ex,{},'ASSET_MISSING')
        except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
            ex['kubernetes_diagnostic']={'code':getattr(exc,'code','ASSET_MISSING'),'message':str(exc)}
            with rt._tx() as db:rt._execution_store(db,job_id,ex)
            if ex.get('kubernetes_spec'):return rt.get(job_id)
            return finish(rt,job,ex,{},getattr(exc,'code','ASSET_MISSING'))

def finish(rt,job,ex,files,error):
    from ..development.registry import spec,result as build_result
    body=spec(job['tool_id']).request(rt._request_bytes(job))
    files=dict(files)
    files['kubernetes-execution.json']=encode(ex)
    actual=dict(job_id=job['job_id'],attempt_id=job['attempt_id'],execution_identity=job['execution_identity'],
        backend='kubernetes',exit_code=None,error_code=error,stopped_confirmed=True,
        diagnostic='Target Kubernetes execution recorded; Docker-qualified scientific result profile is not transferable',
        kubernetes_receipt=ex.get('kubernetes_receipt'))
    result=build_result(job,body,files,actual)
    ex.update(tree_stopped=True,phase='collected')
    return rt._finish_development(job['job_id'],ex,files,result)
