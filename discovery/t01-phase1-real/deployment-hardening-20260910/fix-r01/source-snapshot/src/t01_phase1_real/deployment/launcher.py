"""Bounded HTTPS Kubernetes Job client with immutable identity and UID deletion.

Transport is injectable for contract tests. No shell, Docker socket, kubeconfig
exec plugin, or implicit cluster selection is used. Scientific qualification is
not granted by a successful Kubernetes Job.
"""
import hashlib
import json
import ssl
from pathlib import Path
from urllib import request,error,parse
from .kubernetes import _name,scientific_network_policy,job_state

class ClusterError(RuntimeError):
    def __init__(self,code,message):super().__init__(message);self.code=code

class API:
    def __init__(self,server,token_file,ca_file):
        parsed=parse.urlsplit(server)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
            raise ValueError('Explicit HTTPS Kubernetes API origin required')
        self.server=server.rstrip('/');self.token_file=Path(token_file)
        if not self.token_file.is_absolute() or not Path(ca_file).is_absolute():raise ValueError('Absolute credential paths required')
        self.context=ssl.create_default_context(cafile=str(ca_file))
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):return None
        self.opener=request.build_opener(request.ProxyHandler({}),request.HTTPSHandler(context=self.context),NoRedirect())

    def __call__(self,method,path,body=None):
        if not path.startswith(('/apis/','/api/')):raise ValueError('Unsupported Kubernetes API path')
        token=self.token_file.read_text().strip()
        if not token or '\n' in token:raise ClusterError('CONFIGURATION_INVALID','Invalid API token file')
        raw=None if body is None else json.dumps(body,separators=(',',':'),allow_nan=False).encode()
        req=request.Request(self.server+path,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json'})
        try:
            with self.opener.open(req,timeout=15) as response:
                payload=response.read(8*1024*1024+1)
                if len(payload)>8*1024*1024:raise ClusterError('OUTPUT_INVALID','Kubernetes response exceeds bound')
                return response.status,json.loads(payload)
        except error.HTTPError as exc:
            # Do not return credential-bearing headers or unbounded server text.
            if exc.code in (404,409):return exc.code,{}
            raise ClusterError('KUBERNETES_API_ERROR',f'Kubernetes HTTP {exc.code}') from None
        except (error.URLError,TimeoutError,OSError,ValueError):
            raise ClusterError('KUBERNETES_UNAVAILABLE','Kubernetes response unavailable or invalid') from None

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def matches(expected,observed):
    """Allow API-defaulted object fields, but no altered values or extra list entries."""
    if isinstance(expected,dict):return isinstance(observed,dict) and all(k in observed and matches(v,observed[k]) for k,v in expected.items())
    if isinstance(expected,list):return isinstance(observed,list) and len(expected)==len(observed) and all(matches(a,b) for a,b in zip(expected,observed))
    return type(expected)==type(observed) and expected==observed

class Launcher:
    def __init__(self,api,namespace):
        self.api=api;self.namespace=_name(namespace,'namespace')
        self.jobs='/apis/batch/v1/namespaces/'+namespace+'/jobs'
        self.pods='/api/v1/namespaces/'+namespace+'/pods'

    def offline_policy(self):
        expected=scientific_network_policy(self.namespace)
        status,value=self.api('GET','/apis/networking.k8s.io/v1/namespaces/'+self.namespace+'/networkpolicies/'+expected['metadata']['name'])
        if status!=200 or value.get('spec')!=expected['spec']:
            raise ClusterError('NETWORK_ISOLATION_UNVERIFIED','Required offline NetworkPolicy missing or changed')
        # Presence is necessary, not proof that the site's CNI enforces it.
        return value.get('metadata',{}).get('uid')

    def submit(self,spec,binding,receipt=None):
        if spec['metadata']['namespace']!=self.namespace:raise ClusterError('FORBIDDEN','Job namespace differs')
        name=_name(spec['metadata']['name'],'job name')
        if not spec['spec'].get('activeDeadlineSeconds'):raise ClusterError('INVALID_REQUEST','Job deadline required')
        payload=json.loads(json.dumps(spec))
        owner=digest(binding);spec_hash=digest(spec)
        annotations=payload['metadata'].setdefault('annotations',{})
        annotations.update({'t01.openai/owner':owner,'t01.openai/spec-sha256':spec_hash})
        self.offline_policy()
        status,observed=self.api('GET',self.jobs+'/'+name)
        if status==404:
            if receipt is not None:raise ClusterError('EXECUTION_LOST','Recorded Job disappeared; refusing automatic reexecution')
            status,observed=self.api('POST',self.jobs,payload)
            if status==409:status,observed=self.api('GET',self.jobs+'/'+name)
        if status not in (200,201):raise ClusterError('KUBERNETES_API_ERROR','Job submission unconfirmed')
        meta=observed.get('metadata',{});ann=meta.get('annotations',{})
        if ann.get('t01.openai/owner')!=owner or ann.get('t01.openai/spec-sha256')!=spec_hash or not meta.get('uid'):
            raise ClusterError('FORBIDDEN','Job is not owned by this exact execution')
        if receipt and meta['uid']!=receipt['uid']:raise ClusterError('FORBIDDEN','Kubernetes Job UID changed')
        if not matches(spec['spec'],observed.get('spec')):raise ClusterError('FORBIDDEN','Observed Job specification changed')
        return dict(name=name,namespace=self.namespace,uid=meta['uid'],owner=owner,spec_sha256=spec_hash,spec=spec['spec'])

    def observe(self,receipt):
        if receipt['namespace']!=self.namespace:raise ClusterError('FORBIDDEN','Receipt namespace differs')
        name=_name(receipt['name'],'job name')
        status,job=self.api('GET',self.jobs+'/'+name)
        if status==404:return dict(state='reconciling',reason_code='EXECUTION_LOST',stopped_confirmed=False)
        meta=job.get('metadata',{});ann=meta.get('annotations',{})
        if meta.get('uid')!=receipt['uid'] or ann.get('t01.openai/owner')!=receipt['owner'] or ann.get('t01.openai/spec-sha256')!=receipt['spec_sha256']:
            raise ClusterError('FORBIDDEN','Kubernetes execution ownership changed')
        if not matches(receipt['spec'],job.get('spec')):raise ClusterError('FORBIDDEN','Observed Job specification changed')
        status,pods=self.api('GET',self.pods+'?labelSelector='+parse.quote('batch.kubernetes.io/controller-uid='+receipt['uid']))
        if status!=200:raise ClusterError('KUBERNETES_UNAVAILABLE','Pod stop state unavailable')
        owned=[]
        for pod in pods.get('items',[]):
            if not any(r.get('uid')==receipt['uid'] and r.get('kind')=='Job' for r in pod.get('metadata',{}).get('ownerReferences',[])):
                raise ClusterError('FORBIDDEN','Observed Pod has another owner')
            owned.append(pod)
        state=job_state(job)
        # Job status alone (including Failed) does not prove all Pods stopped.
        terminal_job=bool(meta.get('deletionTimestamp')) or any(
            row.get('type') in ('Complete','Failed') and row.get('status')=='True'
            for row in job.get('status',{}).get('conditions',[]))
        state.update(stopped_confirmed=terminal_job and bool(owned) and all(p.get('status',{}).get('phase') in ('Succeeded','Failed') for p in owned),job=job,pods=owned)
        return state

    def cancel(self,receipt):
        observed=self.observe(receipt)
        if observed['reason_code']=='EXECUTION_LOST':return observed
        status,_=self.api('DELETE',self.jobs+'/'+receipt['name'],
            {'apiVersion':'v1','kind':'DeleteOptions','propagationPolicy':'Foreground','gracePeriodSeconds':0,
             'preconditions':{'uid':receipt['uid']}})
        if status not in (200,202,404):raise ClusterError('KUBERNETES_API_ERROR','Deletion not confirmed')
        return dict(state='stop_requested',reason_code='KUBERNETES_JOB_DELETING',stopped_confirmed=False)

    def observe_stop(self,receipt):
        """Only call after a durable cancellation intent; absent Job alone is insufficient."""
        observed=self.observe(receipt)
        if observed['reason_code']!='EXECUTION_LOST':return observed
        status,pods=self.api('GET',self.pods+'?labelSelector='+parse.quote('batch.kubernetes.io/controller-uid='+receipt['uid']))
        if status!=200:raise ClusterError('KUBERNETES_UNAVAILABLE','Deletion Pod state unavailable')
        for pod in pods.get('items',[]):
            if not any(r.get('uid')==receipt['uid'] for r in pod.get('metadata',{}).get('ownerReferences',[])):
                raise ClusterError('FORBIDDEN','Unexpected deletion Pod identity')
        stopped=all(p.get('status',{}).get('phase') in ('Succeeded','Failed') for p in pods.get('items',[]))
        return dict(state='cancelled' if stopped else 'stop_requested',reason_code='KUBERNETES_JOB_DELETED',stopped_confirmed=stopped)
