"""Single-host transactional runtime. Scientific tools are refused before launch."""
from contextlib import contextmanager
from datetime import datetime
import copy
import os
from pathlib import Path
import sqlite3
import sys
import time

from .common import (REPO, TOOL, TERMINAL, TRANSITIONS, RuntimeFault, decode, encode,
                     ensure, identifier, new_id, now, profile, sha, validate)
from .files import no_links, publish, read_locked, read_verified, runtime_root, within


class Runtime:
    def __init__(self, root, scope='local-owner'):
        ensure(os.name=='nt','PROFILE_NOT_APPROVED','This local executor is qualified on Windows only')
        self.root=runtime_root(root)
        self.scope=identifier(scope)
        self._fault=None
        self._supervisor_fault=None  # Internal bounded crash injection; not a request/profile field.
        from .winprocess import initialization_lock
        with initialization_lock('Local\\T01-init-'+sha(str(self.root).casefold().encode())):
            self._initialize()

    def _initialize(self):
        marker=self.root/'runtime.json'
        if not marker.exists():
            ensure(not list(self.root.iterdir()),'FORBIDDEN','Existing directory is not a registered runtime')
            try: publish(self.root,'runtime.json',encode({'namespace':'t01_phase1_real','mode':'engineering_only','version':1}))
            except FileExistsError: pass
        ensure(decode(read_locked(marker))=={'namespace':'t01_phase1_real','mode':'engineering_only','version':1},
               'FORBIDDEN','Runtime marker mismatch')
        with self._db() as db:
            version=db.execute('PRAGMA user_version').fetchone()[0]
            ensure(version in (0,1),'UNSUPPORTED_VERSION','Unsupported runtime database version')
            if version==0:
                db.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, scope TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), scope TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), relative_path TEXT UNIQUE NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(job_id TEXT NOT NULL REFERENCES jobs(id), revision INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(job_id,revision));
CREATE TABLE IF NOT EXISTS idempotency(scope TEXT NOT NULL, operation TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(scope,operation,key));
CREATE TABLE IF NOT EXISTS executions(job_id TEXT PRIMARY KEY REFERENCES jobs(id), data TEXT NOT NULL);
PRAGMA user_version=1;
COMMIT;''')

    @contextmanager
    def _db(self):
        for name in ['state.sqlite3','state.sqlite3-wal','state.sqlite3-shm']:
            no_links(self.root/name)
        db=sqlite3.connect(self.root/'state.sqlite3',timeout=15,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        try: yield db
        finally: db.close()

    @contextmanager
    def _tx(self):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback();raise

    def _checkpoint(self,name):
        if self._fault: self._fault(name)

    def _run(self,db,run_id):
        identifier(run_id,'run')
        row=db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
        ensure(row is not None and row['scope']==self.scope,'FORBIDDEN','Run is not accessible')
        return decode(row['data'])

    def _job(self,db,job_id,authorize=True):
        identifier(job_id,'job')
        row=db.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
        ensure(row is not None and (not authorize or row['scope']==self.scope),'JOB_NOT_FOUND','Job is not accessible')
        return decode(row['data'])

    def get(self,job_id):
        with self._db() as db: return self._job(db,job_id)

    def events(self,job_id):
        with self._db() as db:
            self._job(db,job_id)
            return [decode(r[0]) for r in db.execute('SELECT data FROM events WHERE job_id=? ORDER BY revision',(job_id,))]

    def _store(self,db,value,before=None,event='state'):
        validate(value,'job')
        if before is not None:
            ensure(before['state'] not in TERMINAL,'INVALID_STATE','Terminal job is immutable')
            ensure(value['state']==before['state'] or value['state'] in TRANSITIONS[before['state']],
                   'INVALID_STATE','Illegal lifecycle transition')
            value['revision']=before['revision']+1
            value['updated_at']=now()
            db.execute('UPDATE jobs SET data=? WHERE id=?',(encode(value).decode(),value['job_id']))
        else:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(value['job_id'],value['run_id'],self.scope,encode(value).decode()))
        db.execute('INSERT INTO events VALUES(?,?,?)',(value['job_id'],value['revision'],
            encode({'event':event,'snapshot':value}).decode()))

    def _idempotent(self,db,operation,key,raw,action):
        identifier(key)
        row=db.execute('SELECT * FROM idempotency WHERE scope=? AND operation=? AND key=?',(self.scope,operation,key)).fetchone()
        if row:
            ensure(row['fingerprint']==sha(raw),'IDEMPOTENCY_CONFLICT','Idempotency key has different bytes')
            response=decode(row['response'])
            return self._job(db,response['job_id']) if 'job_id' in response else response
        response=action()
        stored={'job_id':response['job_id']} if 'job_id' in response else response
        db.execute('INSERT INTO idempotency VALUES(?,?,?,?,?)',(self.scope,operation,key,sha(raw),encode(stored).decode()))
        self._checkpoint('admission_before_commit')
        return response

    def create_run(self,key):
        body={'contract_version':'0.1.0','operation':'create_run','idempotency_key':key}
        return self.control(encode(body))

    def control(self,raw):
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded UTF-8 bytes required')
        body=decode(raw);validate(body,'control')
        op=body['operation']
        if op=='get': return self.get(body['job_id'])
        with self._tx() as db:
            def action():
                if op=='create_run':
                    value={'contract_version':'0.1.0','run_id':new_id('run'),'created_at':now()}
                    db.execute('INSERT INTO runs VALUES(?,?,?)',(value['run_id'],self.scope,encode(value).decode()))
                    return value
                before=self._job(db,body['job_id'])
                if op=='cancel': return self._stop(db,before,'cancel')
                ensure(before['state'] in ('failed','cancelled','timed_out'),'INVALID_STATE','Retry requires confirmed terminal failure')
                if before['attempt_id']:
                    execution=self._execution(db,before['job_id'])
                    ensure(execution.get('tree_stopped') is True,'INVALID_STATE','Execution termination is unconfirmed')
                request={k:copy.deepcopy(before[k]) for k in ('contract_version','run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile')}
                request['idempotency_key']=body['idempotency_key']
                self._admit(db,request)
                return self._new_job(db,request,raw,retry_of=before['job_id'])
            return self._idempotent(db,op,body['idempotency_key'],raw,action)

    def stage_request(self,run_id,raw):
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded request bytes required')
        self._engineering_request(raw)
        with self._tx() as db:
            self._run(db,run_id)
            aid=new_id('artifact')
            relative=f'runs/{run_id}/inputs/{aid}.json'
            ref=self._artifact(aid,run_id,None,None,'request',raw)
            publish(self.root,relative,raw)
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,run_id,relative,encode(ref).decode()))
            return ref

    @staticmethod
    def _engineering_request(raw):
        value=decode(raw)
        ensure(isinstance(value,dict) and set(value)=={'mode','payload','delay_seconds'},'INVALID_REQUEST','Invalid engineering request fields')
        ensure(value['mode'] in ['echo','fail','sleep','tree','partial','wrong_identity'], 'INVALID_REQUEST','Unregistered engineering behavior')
        ensure(isinstance(value['payload'],str) and len(value['payload'])<=4096,'INVALID_REQUEST','Bounded engineering payload required')
        delay=value['delay_seconds']
        ensure(type(delay) in (int,float) and 0<=delay<=10,'INVALID_REQUEST','Engineering delay is outside bounded range')
        return value

    @staticmethod
    def _artifact(aid,run_id,job_id,attempt_id,role,raw):
        return dict(artifact_id=aid,run_id=run_id,job_id=job_id,attempt_id=attempt_id,role=role,
            media_type='application/json',sha256=sha(raw),size_bytes=len(raw),evidence_kind='ENGINEERING_FIXTURE')

    def _input(self,db,ref,run_id):
        self._run(db,run_id)
        row=db.execute('SELECT * FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
        ensure(row is not None and row['run_id']==run_id and decode(row['data'])==ref,
               'FORBIDDEN','Artifact is not registered to this run')
        return read_verified(self.root,row['relative_path'],ref['sha256'],ref['size_bytes'],65536)

    def _admit(self,db,request):
        validate(request,'submit')
        ensure(request['tool_id']==TOOL,'PROFILE_NOT_APPROVED','Scientific or unknown Worker is not enabled')
        ensure(request['node_id'] is None and request['run_mode']=='engineering_example'
               and request['rule_profile'] is None,'PROFILE_NOT_APPROVED','Only engineering mode is enabled')
        ensure(request['execution_profile']==profile(),'PROFILE_NOT_APPROVED','Execution profile does not match the registered code')
        ref=request['request_artifact']
        identifier(request['request_id'])
        ensure(not request['request_id'].startswith(('t01p1m-', 't01-phase1-mock-', 't01-mock-')),
               'FORBIDDEN','Foreign request namespace')
        ensure(ref['role']=='request' and ref['job_id'] is None and ref['attempt_id'] is None
               and ref['evidence_kind']=='ENGINEERING_FIXTURE','FORBIDDEN','Invalid request artifact identity')
        self._engineering_request(self._input(db,ref,request['run_id']))

    def submit(self,raw):
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded UTF-8 bytes required')
        body=decode(raw);validate(body,'submit')
        with self._tx() as db:
            def action():
                self._admit(db,body)
                return self._new_job(db,body,raw)
            return self._idempotent(db,'submit',body['idempotency_key'],raw,action)

    def _new_job(self,db,request,raw,retry_of=None):
        value={k:copy.deepcopy(request[k]) for k in ('contract_version','run_id','request_id','tool_id','node_id','run_mode','request_artifact','execution_profile','rule_profile')}
        stamp=now()
        value.update(job_id=new_id('job'),submission_sha256=sha(raw),retry_of_job_id=retry_of,state='queued',revision=0,
            attempt_id=None,lease_epoch=0,execution_identity=None,created_at=stamp,updated_at=stamp,started_at=None,
            finished_at=None,stop_reason=None,stop_confirmed=False,exit_code=None,error_code=None,
            scientific_disposition='pending',usable_for_pipeline=False,review_required=False,
            evidence_kind='ENGINEERING_FIXTURE',artifacts=[])
        publish(self.root,f'runs/{value["run_id"]}/jobs/{value["job_id"]}/submission.json',raw)
        self._store(db,value,event='submitted')
        return value

    def _stop(self,db,before,reason):
        if before['state'] in TERMINAL or before['stop_reason'] is not None: return before
        value=copy.deepcopy(before);value['stop_reason']=reason
        if before['state']=='queued':
            value.update(state='cancelled',finished_at=now(),stop_confirmed=True,error_code='CANCELLED',scientific_disposition='not_evaluated')
        else: value['state']='stop_requested'
        self._store(db,value,before,'stop_intent')
        return value

    @staticmethod
    def _execution(db,job_id):
        row=db.execute('SELECT data FROM executions WHERE job_id=?',(job_id,)).fetchone()
        return decode(row[0]) if row else {}

    @staticmethod
    def _execution_store(db,job_id,data):
        db.execute('INSERT INTO executions VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET data=excluded.data',
                   (job_id,encode(data).decode()))

    def execution(self,job_id):
        with self._db() as db:
            self._job(db,job_id)
            return self._execution(db,job_id)

    def attempt_path(self,value):
        return f'runs/{value["run_id"]}/jobs/{value["job_id"]}/attempts/{value["attempt_id"]}'

    def dispatch(self,job_id):
        from .winprocess import Process,current_identity
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state']!='queued': return before
            try:
                ensure(before['execution_profile']==profile(),'PROFILE_NOT_APPROVED','Worker source changed since submission')
                raw=self._input(db,before['request_artifact'],before['run_id'])
            except RuntimeFault as exc:
                value=copy.deepcopy(before)
                value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='not_evaluated')
                self._store(db,value,before,'preflight_failed');return value
            value=copy.deepcopy(before)
            value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                lease_epoch=1,started_at=now())
            path=self.attempt_path(value)
            publish(self.root,path+'/input.json',raw)
            execution=dict(phase='reserved',dispatcher=current_identity(),supervisor=None,tree_stopped=False,
                job_object='Local\\T01-'+value['execution_identity'],worker=None,dispatch_profile=profile())
            self._execution_store(db,job_id,execution)
            self._store(db,value,before,'claimed')
        self._checkpoint('after_claim')
        with self._tx() as db:
            current=self._job(db,job_id)
            ex=self._execution(db,job_id)
            if current['state'] in TERMINAL or current['lease_epoch']!=1 or ex['phase']!='reserved': return current
            ex['phase']='spawn_intent';self._execution_store(db,job_id,ex)
        self._checkpoint('before_spawn')
        # The supervisor self-registers before starting any Worker. A spawn-intent gap is never guessed safe.
        argv=[sys.executable,'-X','utf8',str(REPO/'scripts/w1_runtime_supervisor.py'),
              '--root',str(self.root),'--scope',self.scope,'--job-id',job_id]
        if self._supervisor_fault:
            ensure(self._supervisor_fault in ('after_registration','after_receipt'),'INVALID_REQUEST','Unknown internal fault')
            argv.extend(['--test-fault',self._supervisor_fault])
        child=Process(argv,REPO)
        child.resume();child.close()
        self._checkpoint('after_spawn')
        return self.get(job_id)

    def reconcile(self,job_id):
        from .winprocess import alive,inspect_job
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state'] in TERMINAL or before['state']=='queued': return before
            ex=self._execution(db,job_id)
            supervisor_live=alive(ex.get('supervisor'))
            if ex.get('phase')=='reserved':
                # No launch intent exists, so fencing this claim proves no process was started.
                ex.update(phase='finished',tree_stopped=True)
                self._execution_store(db,job_id,ex)
                return self._finish(db,before,ex,error='INTERRUPTED')
            if supervisor_live is True:
                if before['state']=='reconciling':
                    value=copy.deepcopy(before)
                    value['state']='stop_requested' if value['stop_reason'] else 'running'
                    value['lease_epoch']+=1
                    self._store(db,value,before,'reattached')
                    return value
                return before
            if ex.get('phase')=='finished' or supervisor_live is False:
                active=inspect_job(ex['job_object'],stop=bool(before['stop_reason']))
                if active==0:
                    ex['tree_stopped']=True
                    self._execution_store(db,job_id,ex)
                    if before['stop_reason']: return self._finish(db,before,ex,error='INTERRUPTED')
                    return self._collect(db,before,ex,recovered=True)
            value=copy.deepcopy(before)
            if value['state']!='reconciling':
                value['state']='reconciling';value['lease_epoch']+=1
                self._store(db,value,before,'execution_unknown')
            return value

    def recover(self,job_id):
        """Explicit controller restart: fence old callbacks before reconciling the same execution."""
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state'] in TERMINAL or before['state']=='queued': return before
            if before['state']!='reconciling':
                value=copy.deepcopy(before)
                value.update(state='reconciling',lease_epoch=before['lease_epoch']+1)
                self._store(db,value,before,'controller_recovery')
        return self.reconcile(job_id)

    def _finish(self,db,before,ex,error=None,result=None,exit_code=None):
        ensure(ex.get('tree_stopped') is True,'INVALID_STATE','Process tree termination is not confirmed')
        value=copy.deepcopy(before)
        if value['stop_reason']:
            value.update(state='cancelled' if value['stop_reason']=='cancel' else 'timed_out',stop_confirmed=True,
                         error_code='CANCELLED' if value['stop_reason']=='cancel' else 'TIMEOUT')
        else: value.update(state='succeeded' if result is not None and error is None else 'failed',error_code=error)
        value.update(finished_at=now(),exit_code=exit_code,scientific_disposition='not_evaluated')
        if result is not None:
            aid=new_id('artifact')
            role='result' if value['state']=='succeeded' else 'diagnostic'
            relative=self.attempt_path(value)+f'/published/{aid}.json'
            publish(self.root,relative,result)
            ref=self._artifact(aid,value['run_id'],value['job_id'],value['attempt_id'],role,result)
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,value['run_id'],relative,encode(ref).decode()))
            value['artifacts'].append(ref)
        if value['state']=='failed' and value['error_code'] is None: value['error_code']='OUTPUT_INVALID'
        ex['phase']='finished';self._execution_store(db,value['job_id'],ex)
        self._store(db,value,before,'completed')
        return value

    def _collect(self,db,before,ex,recovered=False):
        path=self.attempt_path(before)
        try:
            receipt=decode(read_locked(within(self.root,path+'/receipt.json')))
            ensure(receipt['job_id']==before['job_id'] and receipt['attempt_id']==before['attempt_id']
                and receipt['execution_identity']==before['execution_identity'],'OUTPUT_INVALID','Receipt identity mismatch')
            code=receipt['exit_code']
            ensure(type(code) is int,'OUTPUT_INVALID','Missing process exit code')
            if code!=0: return self._finish(db,before,ex,error='TOOL_FAILED',exit_code=code)
            raw=read_verified(self.root,path+'/output.json',receipt['sha256'],receipt['size_bytes'])
            result=decode(raw)
            ensure(set(result)=={'job_id','attempt_id','execution_identity','input_sha256','payload_sha256','evidence_kind'},'OUTPUT_INVALID','Output fields invalid')
            ensure(all(result[k]==before[k] for k in ['job_id','attempt_id','execution_identity'])
                and result['input_sha256']==before['request_artifact']['sha256']
                and result['evidence_kind']=='ENGINEERING_FIXTURE','OUTPUT_INVALID','Output is not bound to this execution')
            request=self._engineering_request(self._input(db,before['request_artifact'],before['run_id']))
            ensure(result['payload_sha256']==sha(request['payload'].encode()),'OUTPUT_INVALID','Engineering output does not match input')
            return self._finish(db,before,ex,result=raw,exit_code=code)
        except (RuntimeFault,KeyError,TypeError,ValueError) as exc:
            error='INTERRUPTED' if recovered and isinstance(exc,RuntimeFault) and exc.code=='ASSET_MISSING' else 'OUTPUT_INVALID'
            return self._finish(db,before,ex,error=error)

    def accept_callback(self,job_id,attempt_id,epoch):
        """Internal Worker control check; callers cannot submit arbitrary result payloads."""
        with self._tx() as db:
            value=self._job(db,job_id)
            ensure(value['attempt_id']==attempt_id and value['lease_epoch']==epoch,'STALE_LEASE','Worker generation is stale')
            ensure(value['state'] not in TERMINAL,'INVALID_STATE','Job already finished')
            return value

    def wait(self,job_id,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            value=self.reconcile(job_id)
            if value['state'] in TERMINAL: return value
            time.sleep(.03)
        return self.get(job_id)

    def artifact_bytes(self,job_id,artifact_id):
        with self._db() as db:
            job=self._job(db,job_id)
            ref=next((r for r in job['artifacts'] if r['artifact_id']==artifact_id),None)
            ensure(ref is not None,'FORBIDDEN','Artifact is not part of this job')
            row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(artifact_id,)).fetchone()
            ensure(row is not None and decode(row['data'])==ref,'FORBIDDEN','Artifact registration mismatch')
            return read_verified(self.root,row['relative_path'],ref['sha256'],ref['size_bytes'])
