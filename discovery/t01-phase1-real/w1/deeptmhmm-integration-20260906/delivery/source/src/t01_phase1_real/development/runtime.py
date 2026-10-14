"""Development Worker registry over the existing transactional task store and lifecycle."""
import copy
from datetime import datetime, timezone
import sys
import subprocess

from ..common import (REPO, TOOL as ENGINEERING, TERMINAL, RuntimeFault, decode, encode,
    ensure, identifier, new_id, now, sha, validate)
from ..files import publish, read_locked, read_verified, within
from ..runtime import Runtime as StoreRuntime
from . import docker
from .policy import TOOL, request, registered_profile, sequence_id


class Runtime(StoreRuntime):
    """Same SQLite/schema/IDs/transactions; adds one fixed development-only Worker."""

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self._development_fault=None  # Internal acceptance harness only; never a request parameter.

    def _store(self,db,value,before=None,event='state'):
        if value['tool_id']==TOOL:
            value.update(evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,review_required=True)
            ensure(value['run_mode']=='g0_probe','PROFILE_NOT_APPROVED','Scientific pipeline consumption is closed')
        return super()._store(db,value,before,event)

    def _stage(self,db,run_id,raw):
        self._run(db,run_id);request(raw)
        aid=new_id('artifact'); relative=f'runs/{run_id}/inputs/{aid}.json'
        ref=self._artifact(aid,run_id,None,None,'request',raw);ref['evidence_kind']='LOCAL_INPUT'
        publish(self.root,relative,raw)
        db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,run_id,relative,encode(ref).decode()))
        return ref

    def stage_request(self,run_id,raw,tool_id=ENGINEERING):
        if tool_id==ENGINEERING:return super().stage_request(run_id,raw)
        ensure(tool_id==TOOL,'PROFILE_NOT_APPROVED','Worker not registered')
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded request bytes required')
        with self._tx() as db: return self._stage(db,run_id,raw)

    def _request_bytes(self,job):
        with self._db() as db:return self._input(db,job['request_artifact'],job['run_id'])

    def submit_sequence(self,raw,key):
        """Atomic convenience operation; duplicates retain the exact same run/job/artifact."""
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded request bytes required')
        request(raw)
        with self._tx() as db:
            def action():
                run=dict(contract_version='0.1.0',run_id=new_id('run'),created_at=now())
                db.execute('INSERT INTO runs VALUES(?,?,?)',(run['run_id'],self.scope,encode(run).decode()))
                ref=self._stage(db,run['run_id'],raw)
                body=dict(contract_version='0.1.0',run_id=run['run_id'],request_id=new_id('request'),idempotency_key=key,
                    tool_id=TOOL,node_id='N02',run_mode='g0_probe',request_artifact=ref,execution_profile=registered_profile(),rule_profile=None)
                self._admit(db,body)
                return self._new_job(db,body,encode(body))
            return self._idempotent(db,'deeptmhmm',key,raw,action)

    def _admit(self,db,body):
        if body.get('tool_id')!=TOOL:return super()._admit(db,body)
        validate(body,'submit')
        ensure(body['node_id']=='N02' and body['run_mode']=='g0_probe' and body['rule_profile'] is None,
            'PROFILE_NOT_APPROVED','DeepTMHMM accepts N02 development mode only')
        ensure(body['execution_profile']==registered_profile(),'PROFILE_NOT_APPROVED','Unregistered or changed development profile')
        identifier(body['request_id'])
        ensure(not body['request_id'].startswith(('t01p1m-','t01-phase1-mock-','t01-mock-')),'FORBIDDEN','Foreign request namespace')
        ref=body['request_artifact']
        ensure(ref['evidence_kind']=='LOCAL_INPUT' and ref['role']=='request' and ref['job_id'] is None
            and ref['attempt_id'] is None,'FORBIDDEN','Invalid development input artifact')
        request(self._input(db,ref,body['run_id']))

    def dispatch(self,job_id):
        if self.get(job_id)['tool_id']!=TOOL:return super().dispatch(job_id)
        from ..winprocess import current_identity
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state']!='queued':return before
            try:
                ensure(before['execution_profile']==registered_profile(),'PROFILE_NOT_APPROVED','Development code changed since admission')
                raw=self._input(db,before['request_artifact'],before['run_id']);body=request(raw)
            except RuntimeFault as exc:
                value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
                self._store(db,value,before,'preflight_failed');return value
            ensure(self._development_fault in (None,'tool_failure','corrupt_output','crash_after_start','crash_after_receipt'),
                'INVALID_REQUEST','Unknown internal development fault')
            value=copy.deepcopy(before)
            value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                lease_epoch=1,started_at=now())
            path=self.attempt_path(value)
            publish(self.root,path+'/input.json',raw)
            publish(self.root,path+'/input.fasta',('>'+sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode())
            within(self.root,path+'/output').mkdir()
            ex=dict(phase='reserved',dispatcher=current_identity(),supervisor=None,tree_stopped=False,
                container_name=docker.SLOT,container_id=None,timeout_seconds=body['timeout_seconds'],fault=self._development_fault,
                deadline=None,container_started=False)
            self._execution_store(db,job_id,ex);self._store(db,value,before,'claimed')
        with self._tx() as db:
            current=self._job(db,job_id);ex=self._execution(db,job_id)
            if current['state'] in TERMINAL or ex['phase']!='reserved':return current
            ex['phase']='spawn_intent';self._execution_store(db,job_id,ex)
        # The child registers under the attempt mutex before any Docker operation.
        # No suspended process can be orphaned by a dispatcher crash.
        try:
            subprocess.Popen([sys.executable,'-X','utf8',str(REPO/'scripts/t01_development_supervisor.py'),
                '--root',str(self.root),'--scope',self.scope,'--job-id',job_id],cwd=REPO,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:return self._unknown(job_id,'Supervisor launch failed: '+str(exc))
        return self.get(job_id)

    def reconcile(self,job_id):
        before=self.get(job_id)
        if before['tool_id']!=TOOL:return super().reconcile(job_id)
        if before['state'] in TERMINAL or before['state']=='queued':return before
        from ..winprocess import alive, initialization_lock
        ex=self.execution(job_id)
        if not ex.get('supervisor') and before['state']!='reconciling' and alive(ex.get('dispatcher')) is True:
            return before  # Registration in flight; explicit recover fences a launch gap.
        if alive(ex.get('supervisor')) is True:
            if before['state']=='reconciling':
                with self._tx() as db:
                    current=self._job(db,job_id)
                    if current['state']=='reconciling':
                        value=copy.deepcopy(current);value['state']='stop_requested' if value['stop_reason'] else 'running'
                        value['lease_epoch']+=1;self._store(db,value,current,'reattached')
            return self.get(job_id)
        try:
            with initialization_lock('Local\\T01-development-'+job_id):
                current=self.get(job_id)
                if current['state'] in TERMINAL:return current
                ex=self.execution(job_id)
                if ex.get('supervisor') and alive(ex.get('supervisor')) is None:
                    return self._unknown(job_id,'Supervisor identity unavailable')
                from .supervisor import collect_stopped
                info=docker.inspect(self.root,ex.get('container_id'))
                if docker.owned(self.root,current,info):
                    info=docker.stop(self.root,current,info)
                    # A dead supervisor never silently restarts/reuses an in-flight inference.
                    return collect_stopped(self,current,info,recovered=True)
                if info is not None and ex.get('container_id')==info['Id']:
                    return self._unknown(job_id,'Container ownership changed')
                # Name is absent or belongs to another attempt; ours cannot still occupy it.
                return collect_stopped(self,current,None,recovered=True)
        except (RuntimeFault,OSError) as exc:
            return self._unknown(job_id,str(exc))

    def _unknown(self,job_id,diagnostic):
        with self._tx() as db:
            current=self._job(db,job_id)
            if current['state'] in TERMINAL:return current
            ex=self._execution(db,job_id);ex['recovery_diagnostic']=diagnostic;self._execution_store(db,job_id,ex)
            if current['state']!='reconciling':
                value=copy.deepcopy(current);value.update(state='reconciling',lease_epoch=current['lease_epoch']+1)
                self._store(db,value,current,'execution_unknown');return value
            return current

    def _finish_development(self,job_id,ex,files,result):
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state'] in TERMINAL:return before
            ensure(ex.get('tree_stopped'),'INVALID_STATE','Container stop must be confirmed before terminal publication')
            value=copy.deepcopy(before)
            error=result['execution'].get('error_code')
            if before['stop_reason']:
                error='CANCELLED' if before['stop_reason']=='cancel' else 'TIMEOUT'
                value.update(state='cancelled' if error=='CANCELLED' else 'timed_out',stop_confirmed=True)
                result.update(topology=None,raw_record=None,status='unreliable',null_reason=error)
                result['execution']['error_code']=error
                result['warnings']=[dict(level='failure',severity='WARNING',code=error,message='执行已停止，结果不供消费')]
            else:value['state']='failed' if error else 'succeeded'
            value.update(finished_at=now(),error_code=error,exit_code=result['execution'].get('exit_code'),
                scientific_disposition='review_required' if value['state']=='succeeded' else 'rejected')
            refs=[]
            for name,raw in sorted(files.items()):
                role='log' if name in ('stdout.txt','stderr.txt') else 'raw'
                ref=self._publish_development(db,value,role,raw,'application/octet-stream')
                value['artifacts'].append(ref);refs.append(dict(path=name,artifact=ref))
            result['raw_artifacts']=refs
            ref=self._publish_development(db,value,'result' if value['state']=='succeeded' else 'diagnostic',encode(result),'application/json')
            value['artifacts'].append(ref)
            ex.update(phase='finished',tree_stopped=True)
            self._execution_store(db,job_id,ex);self._store(db,value,before,'completed')
            return value

    def _publish_development(self,db,job,role,raw,media):
        aid=new_id('artifact');relative=self.attempt_path(job)+'/published/'+aid+'.bin'
        publish(self.root,relative,raw)
        ref=self._artifact(aid,job['run_id'],job['job_id'],job['attempt_id'],role,raw)
        ref.update(evidence_kind='G0_REAL_OUTPUT',media_type=media)
        db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,job['run_id'],relative,encode(ref).decode()))
        return ref

    def artifact_bytes(self,job_id,artifact_id):
        if self.get(job_id)['tool_id']!=TOOL:return super().artifact_bytes(job_id,artifact_id)
        with self._db() as db:
            job=self._job(db,job_id)
            ref=next((r for r in job['artifacts'] if r['artifact_id']==artifact_id),None)
            ensure(ref is not None,'FORBIDDEN','Artifact does not belong to job')
            row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(artifact_id,)).fetchone()
            ensure(row and decode(row['data'])==ref,'FORBIDDEN','Artifact registration mismatch')
            return read_verified(self.root,row['relative_path'],ref['sha256'],ref['size_bytes'],32*1024**2)

    def result(self,job_id):
        job=self.get(job_id)
        ref=next((r for r in job['artifacts'] if r['role'] in ('result','diagnostic')),None)
        ensure(ref is not None,'INVALID_STATE','No terminal result/diagnostic artifact')
        return decode(self.artifact_bytes(job_id,ref['artifact_id']))
