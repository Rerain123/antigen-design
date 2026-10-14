"""Durable nested A3D Job; interruption cleanup must precede parent termination."""
import time
from types import SimpleNamespace
from pathlib import Path

from ..common import ensure,RuntimeFault
from ..files import read_locked,within
from .execution import configuration
from .kubernetes import scientific_job_spec,SCIENTIFIC_SOURCE_IMAGE_IDS
from .launcher import API,Launcher,ClusterError,matches
from .target_result import qualification


class Pending(Exception):
    """Remote process stop is not confirmed; parent must stay nonterminal."""


def pending(rt,job_id,reason):
    with rt._tx() as db:
        ex=rt._execution(db,job_id)
        ex.update(phase='a3d_target_pending',dispatcher=None,a3d_target_diagnostic=reason)
        rt._execution_store(db,job_id,ex)
    raise Pending(reason)


def run(rt,job,body,execution):
    job_id=job['job_id'];config,fingerprint=configuration();entry=config['tools'].get('aggrescan3d')
    ensure(isinstance(entry,dict),'ASSET_MISSING','Explicit A3D target mapping required')
    launcher=Launcher(API(config['server'],config['token_file'],config['ca_file']),config['namespace'])
    path=within(rt.root,rt.attempt_path(job));volume=Path(config['runtime_volume_root']).resolve()
    ensure(path.resolve().is_relative_to(volume),'FORBIDDEN','A3D attempt outside shared volume')
    manifest=scientific_job_spec('aggrescan3d',job['attempt_id'].split('-')[-1][:24],scientific_image=entry['image'],
        control_image=config['control_image'],runtime_claim=config['runtime_claim'],asset_claim=entry['asset_claim'],
        namespace=config['namespace'],timeout_seconds=body['timeout_seconds'],attempt_path=path.relative_to(volume).as_posix(),
        image_pull_secrets=config.get('image_pull_secrets',[]))
    for meta in (manifest['metadata'],manifest['spec']['template']['metadata']):meta['annotations']['t01.openai/not-submitted']='false'
    with rt._tx() as db:
        ex=rt._execution(db,job_id)
        ex.update(a3d_kubernetes_spec=manifest,a3d_config_sha256=fingerprint,a3d_input_sha256=execution['command']['input_sha256'])
        rt._execution_store(db,job_id,ex)
    binding=dict(job_id=job_id,attempt_id=job['attempt_id'],execution_identity=job['execution_identity'],
                 input_sha256=execution['command']['input_sha256'])
    try:
        receipt=launcher.submit(manifest,binding)
        with rt._tx() as db:
            ex=rt._execution(db,job_id);ex['a3d_kubernetes_receipt']=receipt;rt._execution_store(db,job_id,ex)
        started=time.monotonic();cancelling=False
        while True:
            current=rt.get(job_id)
            if current['stop_reason'] or time.monotonic()-started>body['timeout_seconds']:
                if not current['stop_reason']:
                    with rt._tx() as db:rt._stop(db,rt._job(db,job_id),'timeout')
                if not cancelling:
                    launcher.cancel(receipt);cancelling=True
                observation=launcher.observe_stop(receipt)
            else:observation=launcher.observe(receipt)
            if observation['stopped_confirmed']:break
            if cancelling and time.monotonic()-started>body['timeout_seconds']+20:
                pending(rt,job_id,'A3D deletion requires reconciliation')
            time.sleep(.25)
        with rt._tx() as db:
            ex=rt._execution(db,job_id);ex.update(a3d_kubernetes_observation=observation,a3d_stop_confirmed=True)
            rt._execution_store(db,job_id,ex)
        execution['kubernetes_receipt']=receipt;execution['kubernetes_observation']=observation
        execution['command'].update(runtime='kubernetes',image=entry['image'],network='site-networkpolicy')
        if cancelling:return SimpleNamespace(returncode=124,stdout=b'',stderr=b'')
        if observation['state']!='succeeded':return SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
        approved=qualification(config)
        ensure(approved['tools'].get('aggrescan3d')=={'image':entry['image'],'source_image_id':SCIENTIFIC_SOURCE_IMAGE_IDS['aggrescan3d']}
               and receipt['network_policy_uid']==approved['network_policy_uid'],'PROFILE_NOT_APPROVED','A3D target is not qualified')
        pods=observation['pods']
        ensure(len(pods)==1 and pods[0]['spec']['nodeName'] in approved['node_names'],'OUTPUT_INVALID','A3D node differs')
        pod=pods[0]
        ensure(matches(receipt['spec']['template']['spec'],pod['spec']),'OUTPUT_INVALID','A3D actual Pod differs')
        for status_field,name,image in [('containerStatuses','worker',entry['image']),('initContainerStatuses','stage-launcher',config['control_image'])]:
            states=pod['status'][status_field]
            ensure(len(states)==1 and states[0]['name']==name and states[0]['restartCount']==0 and
                   states[0]['state']['terminated']['exitCode']==0 and states[0]['imageID'].split('@')[-1]==image.split('@')[-1],
                   'OUTPUT_INVALID','A3D target container identity or exit differs')
        native=path/'output/a3d-native'
        from ..common import decode
        worker=decode(read_locked(native/'execution.json'))
        ensure(worker['exit_code']==0 and worker['input_sha256']==execution['command']['input_sha256'] and worker['python']=='2.7.15',
               'OUTPUT_INVALID','A3D worker input/runtime differs')
        execution['target_profile']='kubernetes-a3d-0.1.0'
        return SimpleNamespace(returncode=0,stdout=read_locked(native/'stdout.txt'),stderr=read_locked(native/'stderr.txt'))
    except ClusterError as exc:pending(rt,job_id,exc.code)
    except (RuntimeFault,OSError,ValueError,KeyError,TypeError) as exc:
        if not rt.execution(job_id).get('a3d_stop_confirmed'):pending(rt,job_id,getattr(exc,'code','A3D_TARGET_UNCONFIRMED'))
        raise


def cleanup_interrupted(rt,job,ex):
    """Do not rerun interrupted A3D. Stop the owned Job before parent recovery fails."""
    if ex.get('a3d_stop_confirmed'):return True
    try:
        config,fingerprint=configuration()
        ensure(fingerprint==ex['a3d_config_sha256'],'PROFILE_NOT_APPROVED','A3D target config changed')
        launcher=Launcher(API(config['server'],config['token_file'],config['ca_file']),config['namespace'])
        receipt=ex.get('a3d_kubernetes_receipt')
        if receipt is None:
            manifest=ex['a3d_kubernetes_spec']
            status,observed=launcher.api('GET',launcher.jobs+'/'+manifest['metadata']['name'])
            if status==404:return True
            # Observe an existing owned Job only; never POST during recovery.
            from .launcher import digest,matches
            binding=dict(job_id=job['job_id'],attempt_id=job['attempt_id'],execution_identity=job['execution_identity'],input_sha256=ex['a3d_input_sha256'])
            meta=observed['metadata'];ann=meta['annotations']
            ensure(status==200 and ann['t01.openai/owner']==digest(binding) and ann['t01.openai/spec-sha256']==digest(manifest)
                   and matches(manifest['spec'],observed['spec']),'FORBIDDEN','Unconfirmed A3D Job ownership')
            receipt=dict(name=meta['name'],namespace=config['namespace'],uid=meta['uid'],owner=digest(binding),spec_sha256=digest(manifest),spec=manifest['spec'])
        launcher.cancel(receipt)
        observation=launcher.observe_stop(receipt)
        if not observation['stopped_confirmed']:return False
        with rt._tx() as db:
            saved=rt._execution(db,job['job_id']);saved.update(a3d_stop_confirmed=True,a3d_kubernetes_observation=observation)
            rt._execution_store(db,job['job_id'],saved)
        return True
    except (ClusterError,RuntimeFault,OSError,ValueError,KeyError,TypeError):return False
