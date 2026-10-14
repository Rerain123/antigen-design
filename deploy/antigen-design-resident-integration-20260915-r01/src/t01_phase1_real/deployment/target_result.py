"""Target structure execution qualification; never invent Docker observations.

The operator-owned qualification binds independently recorded site evidence.
Its presence is an attestation, not an automatic scientific signoff.
"""
from pathlib import Path

from ..common import decode, ensure, sha
from ..files import read_locked
from .launcher import digest, matches


def qualification(config):
    registration=config.get('qualification')
    ensure(isinstance(registration,dict) and set(registration)=={'path','sha256'},
           'PROFILE_NOT_APPROVED','Target qualification receipt not registered')
    path=Path(registration['path'])
    ensure(path.is_absolute(),'PROFILE_NOT_APPROVED','Absolute target qualification path required')
    raw=read_locked(path,1024*1024)
    ensure(sha(raw)==registration['sha256'],'PROFILE_NOT_APPROVED','Target qualification changed')
    value=decode(raw)
    fields={'schema_version','server','namespace','control_image','network_policy_uid','node_names',
            'tools','approved_by','approved_at','evidence'}
    ensure(isinstance(value,dict) and set(value)==fields and value['schema_version']=='0.1.0',
           'PROFILE_NOT_APPROVED','Exact target qualification v0.1.0 required')
    ensure(all(value[k]==config[k] for k in ('server','namespace','control_image')),
           'PROFILE_NOT_APPROVED','Qualification is for another target')
    ensure(all(isinstance(value[k],str) and value[k].strip() for k in ('approved_by','approved_at','network_policy_uid')),
           'PROFILE_NOT_APPROVED','Site approval identity and policy UID required')
    ensure(isinstance(value['node_names'],list) and value['node_names'] and
           all(isinstance(n,str) and n for n in value['node_names']), 'PROFILE_NOT_APPROVED','Qualified node list required')
    required={'cni_dns_denied','cni_tcp_denied','effective_network_policies','image_provenance','storage','cancel_recovery'}
    ensure(isinstance(value['evidence'],dict) and set(value['evidence'])==required,
           'PROFILE_NOT_APPROVED','Independent site evidence set required')
    for name,ref in value['evidence'].items():
        ensure(isinstance(ref,dict) and set(ref)=={'path','sha256'} and isinstance(ref['path'],str),
               'PROFILE_NOT_APPROVED','Invalid site evidence reference')
        evidence=Path(ref['path'])
        ensure(not evidence.is_absolute() and evidence.parts and all(p not in ('.','..') for p in evidence.parts),
               'PROFILE_NOT_APPROVED','Site evidence must remain within receipt directory')
        data=read_locked(path.parent/evidence,8*1024**2)
        ensure(sha(data)==ref['sha256'],'PROFILE_NOT_APPROVED','Site evidence changed: '+name)
    return value


def validate_structure_execution(job,execution,runtime):
    from .execution import configuration
    from .kubernetes import SCIENTIFIC_SOURCE_IMAGE_IDS
    config,fingerprint=configuration();receipt=execution['kubernetes_receipt'];observation=execution['kubernetes_observation']
    ensure(execution.get('kubernetes_config_sha256')==fingerprint,'PROFILE_NOT_APPROVED','Target config changed')
    approved=qualification(config)
    entry=config['tools']['structure'];accepted=approved['tools']['structure']
    ensure(accepted=={'image':entry['image'],'source_image_id':SCIENTIFIC_SOURCE_IMAGE_IDS['structure']},
           'PROFILE_NOT_APPROVED','Structure image provenance is not qualified')
    ensure(receipt.get('network_policy_uid')==approved['network_policy_uid'],
           'PROFILE_NOT_APPROVED','Offline policy identity differs from qualification')
    expected_owner=digest({k:job[k] for k in ('job_id','attempt_id','execution_identity','request_artifact','execution_profile')})
    ensure(receipt['owner']==expected_owner and receipt['namespace']==config['namespace'],
           'OUTPUT_INVALID','Target receipt belongs to another execution')
    observed_job=observation['job'];meta=observed_job['metadata'];annotations=meta['annotations']
    ensure(meta['uid']==receipt['uid'] and annotations['t01.openai/owner']==receipt['owner'] and
           annotations['t01.openai/spec-sha256']==receipt['spec_sha256'] and matches(receipt['spec'],observed_job['spec']),
           'OUTPUT_INVALID','Target Job identity/specification differs')
    ensure(any(c.get('type')=='Complete' and c.get('status')=='True' for c in observed_job['status'].get('conditions',[]))
           and observation.get('stopped_confirmed') is True,'OUTPUT_INVALID','Target Job is not completely stopped')
    pods=observation['pods']
    ensure(len(pods)==1,'OUTPUT_INVALID','Expected exactly one zero-retry target Pod')
    pod=pods[0];spec=pod['spec'];status=pod['status']
    ensure(spec['nodeName'] in approved['node_names'] and status['phase']=='Succeeded' and
           any(r.get('uid')==receipt['uid'] and r.get('kind')=='Job' for r in pod['metadata']['ownerReferences']),
           'OUTPUT_INVALID','Pod node, owner or terminal phase differs')
    expected=receipt['spec']['template']['spec']
    ensure(matches(expected,spec),'OUTPUT_INVALID','Observed Pod configuration differs')
    for field,status_field,image in [('containers','containerStatuses',entry['image']),
                                    ('initContainers','initContainerStatuses',config['control_image'])]:
        ensure(len(spec[field])==1 and spec[field][0]['image']==image,'OUTPUT_INVALID','Unexpected target container')
        states=status[status_field]
        ensure(len(states)==1 and states[0]['name']==spec[field][0]['name'] and states[0]['restartCount']==0,
               'OUTPUT_INVALID','Unexpected container attempts')
        state=states[0];terminated=state['state']['terminated']
        ensure(terminated.get('exitCode')==0 and terminated.get('reason')=='Completed' and
               state['imageID'].split('@')[-1]==image.split('@')[-1],
               'OUTPUT_INVALID','Container exit/image digest differs')
    ensure(runtime['python_exit_code']==0 and runtime.get('source_modules_modified') is False,
           'OUTPUT_INVALID','Target worker did not finish with original sources')
    ensure(isinstance(runtime['network_interfaces'],list) and runtime['network_interfaces'] and
           isinstance(runtime['cpu_affinity'],list) and runtime['cpu_affinity'] and
           all(type(cpu) is int and cpu>=0 for cpu in runtime['cpu_affinity']),
           'OUTPUT_INVALID','Actual target runtime observations missing')
    ensure(execution.get('exit_code')==0 and execution.get('stopped_confirmed') is True,
           'OUTPUT_INVALID','Target exit/stop missing')
