"""Development Worker registry over the existing transactional task store and lifecycle."""
import copy
from datetime import datetime, timezone
import sys
import subprocess
import time

from ..common import (REPO, TOOL as ENGINEERING, TERMINAL, RuntimeFault, decode, encode,
    ensure, identifier, new_id, now, sha, TRANSITIONS)
from ..files import publish, read_locked, read_verified, within
from ..runtime import Runtime as StoreRuntime
from . import docker
from .policy import TOOL, request, registered_profile, sequence_id
from .registry import TOOLS, spec
from .structure import policy as structure
from .bepipred import policy as bepipred
from .netmhc import policy as netmhc
from .blast import policy as blast
from .epitope_map import policy as epitope_map
from .glycosylation import policy as glycosylation
from .homology import policy as homology
from .domains import policy as domains
from .developability import policy as developability
from .wt_draft import policy as wt_draft
from .proteinmpnn import policy as proteinmpnn
from .esm_if1 import policy as esm_if1
from .design_backend import policy as design_backend
from .thermompnn import policy as thermompnn
from .foldx import policy as foldx
from .variant_report import policy as variant_report
from .epitope_protection import policy as epitope_protection
from .codon import policy as codon
from .contracts import validate


class Runtime(StoreRuntime):
    """Same SQLite/schema/IDs/transactions; fixed development Worker registrations."""

    def __init__(self,*args,blast_database_root=None,homology_database_root=None,domains_database_root=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.blast_database_root=blast_database_root
        self.homology_database_root=homology_database_root
        self.domains_database_root=domains_database_root
        self._development_fault=None  # Internal acceptance harness only; never a request parameter.

    def _store(self,db,value,before=None,event='state'):
        if value['tool_id'] in TOOLS:
            value.update(evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,review_required=True)
            ensure(value['run_mode']=='g0_probe','PROFILE_NOT_APPROVED','Scientific pipeline consumption is closed')
        if value['tool_id'] in (blast.TOOL,bepipred.TOOL,netmhc.TOOL,epitope_map.TOOL,glycosylation.TOOL,homology.TOOL,
            domains.TOOL,developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL,thermompnn.TOOL,foldx.TOOL):
            # Same tables, transactions and transition rules; only the additive
            # N04/tool schema differs from the preserved W1 store implementation.
            validate(value,'job')
            if before is not None:
                ensure(before['state'] not in TERMINAL,'INVALID_STATE','Terminal job is immutable')
                ensure(value['state']==before['state'] or value['state'] in TRANSITIONS[before['state']],'INVALID_STATE','Illegal lifecycle transition')
                value['revision']=before['revision']+1;value['updated_at']=now()
                db.execute('UPDATE jobs SET data=? WHERE id=?',(encode(value).decode(),value['job_id']))
            else:db.execute('INSERT INTO jobs VALUES(?,?,?,?)',(value['job_id'],value['run_id'],self.scope,encode(value).decode()))
            db.execute('INSERT INTO events VALUES(?,?,?)',(value['job_id'],value['revision'],encode(dict(event=event,snapshot=value)).decode()))
            return
        return super()._store(db,value,before,event)

    def submit(self,raw):
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded UTF-8 bytes required')
        body=decode(raw)
        if not isinstance(body,dict) or body.get('tool_id') not in (blast.TOOL,bepipred.TOOL,netmhc.TOOL,epitope_map.TOOL,
            glycosylation.TOOL,homology.TOOL,domains.TOOL,developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL,
            thermompnn.TOOL,foldx.TOOL):return super().submit(raw)
        validate(body,'submit')
        with self._tx() as db:
            def action():
                self._admit(db,body)
                return self._new_job(db,body,raw)
            return self._idempotent(db,'submit',body['idempotency_key'],raw,action)

    def _stage(self,db,run_id,raw,tool_id=TOOL):
        self._run(db,run_id);spec(tool_id).request(raw)
        aid=new_id('artifact'); relative=f'runs/{run_id}/inputs/{aid}.json'
        ref=self._artifact(aid,run_id,None,None,'request',raw);ref['evidence_kind']='LOCAL_INPUT'
        publish(self.root,relative,raw)
        db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,run_id,relative,encode(ref).decode()))
        return ref

    def stage_request(self,run_id,raw,tool_id=ENGINEERING):
        if tool_id==ENGINEERING:return super().stage_request(run_id,raw)
        ensure(tool_id in TOOLS,'PROFILE_NOT_APPROVED','Worker not registered')
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded request bytes required')
        with self._tx() as db: return self._stage(db,run_id,raw,tool_id)

    def _structure_bytes(self,db,body,run_id):
        ref=body['structure_artifact']
        ensure(ref['run_id']==run_id,'FORBIDDEN','Structure belongs to another run')
        self._run(db,run_id)
        row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
        ensure(row and decode(row['data'])==ref,'FORBIDDEN','Unregistered structure input')
        return read_verified(self.root,row['relative_path'],ref['sha256'],ref['size_bytes'],structure.MAX_STRUCTURE_BYTES)

    def submit_structure(self,raw,key,data):
        ensure(isinstance(raw,bytes) and len(raw)<=32768,'INVALID_REQUEST','Bounded metadata bytes required')
        metadata=structure.metadata(raw)
        ensure(isinstance(data,bytes) and 0<len(data)<=structure.MAX_STRUCTURE_BYTES,'INVALID_REQUEST','Structure must be nonempty and at most 4 MiB')
        # Both original metadata bytes and file bytes define duplicate submission.
        fingerprint=encode(dict(metadata_sha256=sha(raw),structure_sha256=sha(data)))
        with self._tx() as db:
            def action():
                run=dict(contract_version='0.1.0',run_id=new_id('run'),created_at=now())
                db.execute('INSERT INTO runs VALUES(?,?,?)',(run['run_id'],self.scope,encode(run).decode()))
                aid=new_id('artifact');relative=f'runs/{run["run_id"]}/inputs/{aid}.structure'
                ref=self._artifact(aid,run['run_id'],None,None,'input',data)
                ref.update(evidence_kind='LOCAL_INPUT',media_type='chemical/x-pdb' if metadata['declared_format']=='PDB' else 'chemical/x-cif')
                publish(self.root,relative,data)
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(aid,run['run_id'],relative,encode(ref).decode()))
                ref=self._stage(db,run['run_id'],encode(dict(metadata,structure_artifact=ref)),structure.TOOL)
                body=dict(contract_version='0.1.0',run_id=run['run_id'],request_id=new_id('request'),idempotency_key=key,
                    tool_id=structure.TOOL,node_id=structure.NODE,run_mode='g0_probe',request_artifact=ref,execution_profile=structure.registered_profile(),rule_profile=None)
                self._admit(db,body)
                return self._new_job(db,body,encode(body))
            return self._idempotent(db,'local_structure',key,fingerprint,action)

    def _request_bytes(self,job):
        with self._db() as db:return self._input(db,job['request_artifact'],job['run_id'])

    def _registered_result_artifact(self,db,ref,expected_tool):
        """Resolve an exact same-scope terminal ArtifactRef and bind its result identity."""
        job=self._job(db,ref['job_id'])
        ensure(job['tool_id']==expected_tool and job['run_id']==ref['run_id'] and job['attempt_id']==ref['attempt_id']
            and job['state'] in TERMINAL and ref in job['artifacts'],'FORBIDDEN','Upstream ArtifactRef/job identity differs')
        row=db.execute('SELECT relative_path,data FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()
        ensure(row and decode(row['data'])==ref,'FORBIDDEN','Upstream artifact registration differs')
        raw=read_verified(self.root,row['relative_path'],ref['sha256'],ref['size_bytes'],32*1024**2)
        value=decode(raw)
        binding=value.get('binding') if isinstance(value,dict) else None
        ensure(isinstance(binding,dict) and value.get('tool_id')==expected_tool and binding.get('job_id')==job['job_id']
            and binding.get('run_id')==job['run_id'] and binding.get('attempt_id')==job['attempt_id']
            and value.get('usable_for_pipeline') is False and value.get('automatic_handoff') is False,
            'OUTPUT_INVALID','Upstream result binding/qualification differs')
        return job,raw,value

    def source_input(self,job_id,expected_tool):
        """Build a request source from a registered N03/N04/N05 terminal task."""
        ensure(expected_tool in (blast.TOOL,bepipred.TOOL,netmhc.TOOL),'INVALID_REQUEST','Unsupported N06 upstream tool')
        with self._db() as db:
            job=self._job(db,job_id);ensure(job['tool_id']==expected_tool and job['state'] in TERMINAL,
                'INVALID_STATE','Upstream task must be terminal and match the requested tool')
            role='result' if job['state']=='succeeded' else 'diagnostic'
            ref=next((item for item in job['artifacts'] if item['role']==role),None)
            ensure(ref is not None,'INVALID_STATE','Upstream terminal task has no result/diagnostic ArtifactRef')
            self._registered_result_artifact(db,ref,expected_tool)
            return dict(state='available' if role=='result' else 'upstream_unavailable',artifact=ref,
                reason_code=None if role=='result' else job['error_code'])

    def _epitope_sources(self,db,body):
        sequence_sha=sha(body['protein_sequence'].encode());sources={};receipts={}
        for name,tool in (('bepipred',bepipred.TOOL),('netmhc',netmhc.TOOL),('blast',blast.TOOL)):
            item=body[name+'_input'];state=item['state']
            if state in ('not_provided','not_executed'):
                receipts[name]=dict(state=state,artifact=None,verified=True);continue
            job,raw,value=self._registered_result_artifact(db,item['artifact'],tool)
            ensure(value['binding'].get('sequence_sha256')==sequence_sha,'OUTPUT_INVALID','Upstream sequence SHA-256 differs from N06')
            if state=='available':
                ensure(job['state']=='succeeded' and item['artifact']['role']=='result','OUTPUT_INVALID','Available upstream task is not a success result')
                sources[name]=(raw,value)
            else:
                ensure(job['state']!='succeeded' and item['artifact']['role']=='diagnostic'
                    and item['reason_code']==job['error_code'],'OUTPUT_INVALID','Unavailable upstream diagnostic/reason differs')
            receipts[name]=dict(state=state,artifact=item['artifact'],verified=True,upstream_state=job['state'],
                upstream_error=job['error_code'])
            if name=='blast' and value.get('binding'):
                receipts[name].update(database_id=value['binding'].get('database_id'),
                    database_manifest_sha256=value['binding'].get('database_manifest_sha256'))
        return sources,receipts

    @staticmethod
    def _n06_hotspot_derivation(value):
        """Classify the N06 hotspot payload without inventing unresolved window conversion."""
        ensure(value.get('status') in ('maps_unreviewed','partial_maps_unreviewed')
            and isinstance(value.get('epitopes'),dict),'OUTPUT_INVALID','N06 result is not a usable development map artifact')
        hotspot_map=value['epitopes'].get('b_cell_antigenic_hotspot_map')
        ensure(isinstance(hotspot_map,dict),'OUTPUT_INVALID','N06 hotspot map is absent')
        hotspots=hotspot_map.get('hotspots')
        if hotspots is None:return None,'N06_HOTSPOTS_REVIEW_REQUIRED'
        ensure(isinstance(hotspots,list),'OUTPUT_INVALID','N06 hotspots must be a list or null')
        exact=[]
        for row in hotspots:
            ensure(isinstance(row,dict) and set(row)>={'start','end'} and type(row['start']) is int
                and type(row['end']) is int and 1<=row['start']<=row['end'],
                'OUTPUT_INVALID','N06 hotspot coordinates are malformed')
            exact.append(dict(start=row['start'],end=row['end']))
        if any(row['end']-row['start']+1!=20 for row in exact):
            return None,'OI_029_WINDOW_CONVERSION_REQUIRED'
        return exact,None

    def _n06_hotspot_source(self,db,body):
        """Validate N07 context against a registered N06 artifact, or label a legacy fixture."""
        item=body['hotspot_input'];source=item['source']
        if item['state']=='not_provided':return dict(status='NOT_APPLICABLE',verified=True,artifact=None)
        if set(source)=={'node_id','source_id','sha256'}:
            return dict(status='CONTRACT_FIXTURE_NOT_ARTIFACT_VERIFIED',verified=False,artifact=None,
                source_id=source['source_id'])
        ref=source['artifact'];job,_,value=self._registered_result_artifact(db,ref,epitope_map.TOOL)
        ensure(job['state']=='succeeded' and ref['role']=='result','OUTPUT_INVALID','N07 requires a successful N06 result artifact')
        ensure(value['binding'].get('sequence_sha256')==sha(body['protein_sequence'].encode()),
            'OUTPUT_INVALID','N06 sequence SHA-256 differs from N07')
        hotspots,reason=self._n06_hotspot_derivation(value)
        if item['state']=='available':
            ensure(reason is None and item['hotspots']==hotspots and item['reason_code'] is None,
                'OUTPUT_INVALID','N07 hotspot windows differ from the verified N06 result')
        else:
            ensure(item['hotspots'] is None and item['reason_code']==reason,
                'OUTPUT_INVALID','N07 unavailable reason differs from the verified N06 result')
        return dict(status='VERIFIED_N06_ARTIFACT_REF',verified=True,artifact=ref,
            upstream_job_id=job['job_id'],upstream_status=value['status'],derived_reason_code=reason)

    def n06_hotspot_input(self,job_id,sequence):
        """Build exact N07 hotspot context from a registered terminal N06 result."""
        with self._db() as db:
            job=self._job(db,job_id)
            ensure(job['tool_id']==epitope_map.TOOL and job['state']=='succeeded',
                'INVALID_STATE','N07 source must be a successful N06 task')
            ref=next((row for row in job['artifacts'] if row['role']=='result'),None)
            ensure(ref is not None,'INVALID_STATE','N06 task has no result ArtifactRef')
            _,_,value=self._registered_result_artifact(db,ref,epitope_map.TOOL)
            ensure(value['binding'].get('sequence_sha256')==sha(sequence.encode()),
                'OUTPUT_INVALID','N06 sequence SHA-256 differs from requested N07 sequence')
            hotspots,reason=self._n06_hotspot_derivation(value)
            source=dict(kind='artifact_ref',node_id='N06',artifact=ref)
            return dict(state='available' if reason is None else 'upstream_unavailable',hotspots=hotspots,
                source=source,reason_code=reason)

    def submit_sequence(self,raw,key,tool_id=TOOL):
        """Atomic convenience operation; duplicates retain the exact same run/job/artifact."""
        ensure(isinstance(raw,bytes) and len(raw)<=65536,'INVALID_REQUEST','Bounded request bytes required')
        ensure(tool_id in (TOOL,blast.TOOL,bepipred.TOOL,netmhc.TOOL,epitope_map.TOOL,glycosylation.TOOL,homology.TOOL,
            domains.TOOL,developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL,thermompnn.TOOL,foldx.TOOL),
            'PROFILE_NOT_APPROVED','Sequence Worker not registered')
        worker=spec(tool_id);worker.request(raw)
        with self._tx() as db:
            def action():
                run=dict(contract_version='0.1.0',run_id=new_id('run'),created_at=now())
                db.execute('INSERT INTO runs VALUES(?,?,?)',(run['run_id'],self.scope,encode(run).decode()))
                ref=self._stage(db,run['run_id'],raw,tool_id)
                body=dict(contract_version='0.1.0',run_id=run['run_id'],request_id=new_id('request'),idempotency_key=key,
                    tool_id=tool_id,node_id=worker.NODE,run_mode='g0_probe',request_artifact=ref,execution_profile=worker.registered_profile(),
                    rule_profile=worker.registered_rules() if worker.TOOL in (epitope_map.TOOL,glycosylation.TOOL,homology.TOOL,domains.TOOL,
                        developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL,thermompnn.TOOL,foldx.TOOL) else None)
                self._admit(db,body)
                return self._new_job(db,body,encode(body))
            domain={TOOL:'deeptmhmm',blast.TOOL:'blast',bepipred.TOOL:'bepipred',netmhc.TOOL:'netmhc',epitope_map.TOOL:'epitope_map',
                glycosylation.TOOL:'glycosylation',homology.TOOL:'homology',domains.TOOL:'domains',
                developability.TOOL:'developability',wt_draft.TOOL:'wt_draft',proteinmpnn.TOOL:'proteinmpnn',esm_if1.TOOL:'esm_if1',design_backend.TOOL:'design_backend',variant_report.TOOL:'variant_report',epitope_protection.TOOL:'epitope_protection',codon.TOOL:'codon',
                thermompnn.TOOL:'thermompnn',foldx.TOOL:'foldx'}[tool_id]
            return self._idempotent(db,domain,key,raw,action)

    def _admit(self,db,body):
        if body.get('tool_id') not in TOOLS:return super()._admit(db,body)
        worker=spec(body['tool_id'])
        validate(body,'submit')
        expected_rules=worker.registered_rules() if worker.TOOL in (epitope_map.TOOL,glycosylation.TOOL,homology.TOOL,domains.TOOL,
            developability.TOOL,wt_draft.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL,thermompnn.TOOL,foldx.TOOL) else None
        ensure(body['node_id']==worker.NODE and body['run_mode']=='g0_probe' and body['rule_profile']==expected_rules,
            'PROFILE_NOT_APPROVED','Worker accepts its registered node in development mode only')
        ensure(body['execution_profile']==worker.registered_profile(),'PROFILE_NOT_APPROVED','Unregistered or changed development profile')
        identifier(body['request_id'])
        ensure(not body['request_id'].startswith(('t01p1m-','t01-phase1-mock-','t01-mock-')),'FORBIDDEN','Foreign request namespace')
        ref=body['request_artifact']
        ensure(ref['evidence_kind']=='LOCAL_INPUT' and ref['role']=='request' and ref['job_id'] is None
            and ref['attempt_id'] is None,'FORBIDDEN','Invalid development input artifact')
        content=worker.request(self._input(db,ref,body['run_id']))
        if worker.TOOL==structure.TOOL:self._structure_bytes(db,content,body['run_id'])
        elif worker.TOOL==epitope_map.TOOL:self._epitope_sources(db,content)
        elif worker.TOOL==glycosylation.TOOL:self._n06_hotspot_source(db,content)
        elif worker.TOOL==domains.TOOL:
            from .domains.service import sources
            sources(self,db,content)
        elif worker.TOOL==developability.TOOL:
            from .developability.service import sources
            sources(self,db,content)
        elif worker.TOOL==epitope_protection.TOOL:
            from .epitope_protection.source import sources
            sources(self,db,content)
        elif worker.TOOL==variant_report.TOOL:
            from .variant_report.source import sources
            sources(self,db,content)
        elif worker.TOOL==design_backend.TOOL:
            from .design_backend.source import sources
            sources(self,db,content)
        elif worker.TOOL==wt_draft.TOOL:
            from .wt_draft.service import sources
            sources(self,db,content)
        elif worker.TOOL in (proteinmpnn.TOOL,esm_if1.TOOL,thermompnn.TOOL,foldx.TOOL):
            from .proteinmpnn.source import sources
            if body['tool_id']==esm_if1.TOOL:
                from .esm_if1.source import sources
            elif body['tool_id']==thermompnn.TOOL:
                from .thermompnn.source import sources
            elif body['tool_id']==foldx.TOOL:
                from .foldx.source import sources
            sources(self,db,content)

    def dispatch(self,job_id):
        if self.get(job_id)['tool_id']==codon.TOOL:
            from .codon.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==epitope_protection.TOOL:
            from .epitope_protection.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==variant_report.TOOL:
            from .variant_report.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==design_backend.TOOL:
            from .design_backend.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==wt_draft.TOOL:
            from .wt_draft.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==developability.TOOL:
            from .developability.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==domains.TOOL:
            from .domains.service import dispatch
            return dispatch(self,job_id)
        if self.get(job_id)['tool_id']==epitope_map.TOOL:return self._dispatch_epitope_map(job_id)
        if self.get(job_id)['tool_id']==glycosylation.TOOL:return self._dispatch_glycosylation(job_id)
        if self.get(job_id)['tool_id'] not in TOOLS:return super().dispatch(job_id)
        from ..winprocess import current_identity
        with self._tx() as db:
            before=self._job(db,job_id)
            worker=spec(before['tool_id'])
            if before['state']!='queued':return before
            try:
                ensure(before['execution_profile']==worker.registered_profile(),'PROFILE_NOT_APPROVED','Development code changed since admission')
                raw=self._input(db,before['request_artifact'],before['run_id']);body=worker.request(raw)
                data=self._structure_bytes(db,body,before['run_id']) if worker.TOOL==structure.TOOL else None
                upstream={};source_receipt=None
                if worker.TOOL in (proteinmpnn.TOOL,esm_if1.TOOL,thermompnn.TOOL,foldx.TOOL):
                    from .proteinmpnn.source import sources
                    if worker.TOOL==esm_if1.TOOL:
                        from .esm_if1.source import sources
                    elif worker.TOOL==thermompnn.TOOL:
                        from .thermompnn.source import sources
                    elif worker.TOOL==foldx.TOOL:
                        from .foldx.source import sources
                    upstream,source_receipt=sources(self,db,body)
            except RuntimeFault as exc:
                value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
                self._store(db,value,before,'preflight_failed');return value
            allowed=(None,'tool_failure','corrupt_output','crash_after_start','crash_after_receipt')
            if worker.TOOL==netmhc.TOOL:allowed=allowed+('mhc_i_failure','mhc_ii_failure','both_channels_failure')
            if worker.TOOL in (blast.TOOL,homology.TOOL,proteinmpnn.TOOL,esm_if1.TOOL,thermompnn.TOOL,foldx.TOOL):allowed=allowed+('slow_worker',)
            if worker.TOOL==esm_if1.TOOL:allowed=allowed+('first_variant_failure','all_variants_failure')
            ensure(self._development_fault in allowed,
                'INVALID_REQUEST','Unknown internal development fault')
            value=copy.deepcopy(before)
            value.update(state='running',attempt_id=new_id('attempt'),execution_identity='exec-'+new_id('attempt'),
                lease_epoch=1,started_at=now())
            path=self.attempt_path(value)
            publish(self.root,path+'/input.json',raw)
            internal_id=getattr(worker,'sequence_id',sequence_id)(body['protein_sequence'])
            publish(self.root,path+'/input.fasta',('>'+internal_id+'\n'+body['protein_sequence']+'\n').encode())
            for name,content in upstream.items():publish(self.root,path+'/'+name,content)
            if data is not None:
                publish(self.root,path+'/input.structure',data)
                binding={k:value[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
                binding.update(input_sha256=sha(raw),sequence_sha256=sha(body['protein_sequence'].encode()),structure_sha256=sha(data))
                publish(self.root,path+'/binding.json',encode(binding))
            within(self.root,path+'/output').mkdir()
            ex=dict(phase='reserved',dispatcher=current_identity(),supervisor=None,tree_stopped=False,
                container_name=worker.SLOT,container_id=None,timeout_seconds=body['timeout_seconds'],fault=self._development_fault,
                deadline=None,container_started=False)
            self._execution_store(db,job_id,ex);self._store(db,value,before,'claimed')
            if worker.TOOL in (proteinmpnn.TOOL,esm_if1.TOOL,thermompnn.TOOL,foldx.TOOL):
                ex['source_receipt']=source_receipt;self._execution_store(db,job_id,ex)
        with self._tx() as db:
            current=self._job(db,job_id);ex=self._execution(db,job_id)
            if current['state'] in TERMINAL or ex['phase']!='reserved':return current
            ex['phase']='spawn_intent';self._execution_store(db,job_id,ex)
        # The child registers under the attempt mutex before any Docker operation.
        # No suspended process can be orphaned by a dispatcher crash.
        try:
            command=[sys.executable,'-X','utf8',str(REPO/'scripts/t01_development_supervisor.py'),
                '--root',str(self.root),'--scope',self.scope,'--job-id',job_id]
            if worker.TOOL==blast.TOOL and self.blast_database_root is not None:
                command+=['--blast-database-root',str(self.blast_database_root)]
            if worker.TOOL==homology.TOOL and self.homology_database_root is not None:
                command += ['--homology-database-root',str(self.homology_database_root)]
            subprocess.Popen(command,cwd=REPO,
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as exc:return self._unknown(job_id,'Supervisor launch failed: '+str(exc))
        return self.get(job_id)

    def _dispatch_epitope_map(self,job_id):
        """Run bounded S-19 branches after re-verifying exact N03/N04/N05 artifacts."""
        from ..winprocess import current_identity
        from .epitope_map.result import compute
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state']!='queued':return before
            try:
                ensure(before['execution_profile']==epitope_map.registered_profile()
                    and before['rule_profile']==epitope_map.registered_rules(),
                    'PROFILE_NOT_APPROVED','N06 implementation or rule profile changed since admission')
                raw=self._input(db,before['request_artifact'],before['run_id']);body=epitope_map.request(raw)
                sources,source_receipts=self._epitope_sources(db,body)
            except RuntimeFault as exc:
                value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
                self._store(db,value,before,'preflight_failed');return value
            fault=self._development_fault
            ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim'),
                'INVALID_REQUEST','Unknown internal N06 development fault')
            value=copy.deepcopy(before);value.update(state='running',attempt_id=new_id('attempt'),
                execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
            path=self.attempt_path(value);fasta=('>'+epitope_map.sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
            publish(self.root,path+'/input.json',raw);publish(self.root,path+'/input.fasta',fasta)
            for name,(source_raw,_) in sources.items():publish(self.root,path+'/input/'+name+'-result.json',source_raw)
            within(self.root,path+'/output').mkdir()
            ex=dict(phase='local_compute',dispatcher=current_identity(),supervisor=None,tree_stopped=False,
                backend='trusted-local-in-process',container_started=False,container_id=None,network_used=False,
                timeout_seconds=body['timeout_seconds'],fault=fault,sources_verified=True,source_receipts=source_receipts)
            self._execution_store(db,job_id,ex);self._store(db,value,before,'claimed')
        if fault=='interrupt_after_claim':
            with self._tx() as db:
                ex=self._execution(db,job_id);ex.update(phase='interrupted_fixture',tree_stopped=True)
                self._execution_store(db,job_id,ex)
            return self.get(job_id)
        started=time.perf_counter();files={'input.json':raw,'input.fasta':fasta}
        files.update({'input/'+name+'-result.json':source_raw for name,(source_raw,_) in sources.items()})
        error=None;diagnostic=None;exit_code=0
        try:
            if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled N06 local calculation failure')
            decoded={name:value for name,(_,value) in sources.items()};computed=compute(body,decoded)
            observed=encode(dict(method='s19-bounded-map-v10.5',
                source_sha256={name:sha(encode(value)) for name,value in decoded.items()},result=computed))
            if fault=='corrupt_output':observed=b'{"truncated":true}'
            publish(self.root,path+'/output/observation.json',observed);files['output/observation.json']=observed
        except (RuntimeFault,OSError,ValueError) as exc:
            error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc);exit_code=1
        elapsed=time.perf_counter()-started
        if elapsed>body['timeout_seconds']:
            error='TIMEOUT';diagnostic='N06 local calculation exceeded its declared deadline';exit_code=124
            with self._tx() as db:
                current=self._job(db,job_id)
                if current['stop_reason'] is None:self._stop(db,current,'timeout')
        actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],
            exit_code=exit_code,error_code=error,diagnostic=diagnostic,stopped_confirmed=True,
            backend='trusted-local-in-process',container_id=None,network_used=False,elapsed_seconds=elapsed,
            sources_verified=True,source_receipts=source_receipts,recovered=False)
        current=self.get(job_id);built=self._build_epitope_map_result(current,body,files,actual,fault)
        ex=self.execution(job_id);ex.update(phase='collected',tree_stopped=True,elapsed_seconds=elapsed)
        return self._finish_development(job_id,ex,files,built)

    @staticmethod
    def _build_epitope_map_result(job,body,files,execution,fault):
        from .epitope_map.result import result
        return result(job,body,files,execution,fault)

    def _dispatch_glycosylation(self,job_id):
        """Run the bounded deterministic S-12 calculation in the trusted backend."""
        from ..winprocess import current_identity
        from .glycosylation.result import scan
        import Bio
        with self._tx() as db:
            before=self._job(db,job_id)
            if before['state']!='queued':return before
            try:
                ensure(before['execution_profile']==glycosylation.registered_profile()
                    and before['rule_profile']==glycosylation.registered_rules(),
                    'PROFILE_NOT_APPROVED','N07 implementation or rule profile changed since admission')
                raw=self._input(db,before['request_artifact'],before['run_id']);body=glycosylation.request(raw)
                hotspot_receipt=self._n06_hotspot_source(db,body);n06_raw=None
                source=body['hotspot_input']['source']
                if hotspot_receipt['status']=='VERIFIED_N06_ARTIFACT_REF':
                    _,n06_raw,_=self._registered_result_artifact(db,source['artifact'],epitope_map.TOOL)
            except RuntimeFault as exc:
                value=copy.deepcopy(before);value.update(state='failed',finished_at=now(),error_code=exc.code,scientific_disposition='rejected')
                self._store(db,value,before,'preflight_failed');return value
            fault=self._development_fault
            ensure(fault in (None,'compute_failure','corrupt_output','interrupt_after_claim'),
                'INVALID_REQUEST','Unknown internal N07 development fault')
            value=copy.deepcopy(before);value.update(state='running',attempt_id=new_id('attempt'),
                execution_identity='exec-'+new_id('attempt'),lease_epoch=1,started_at=now())
            path=self.attempt_path(value)
            publish(self.root,path+'/input.json',raw)
            publish(self.root,path+'/input.fasta',('>'+glycosylation.sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode())
            if n06_raw is not None:publish(self.root,path+'/input/n06-result.json',n06_raw)
            within(self.root,path+'/output').mkdir()
            ex=dict(phase='local_compute',dispatcher=current_identity(),supervisor=None,tree_stopped=False,
                backend='trusted-local-in-process',container_started=False,container_id=None,network_used=False,
                timeout_seconds=body['timeout_seconds'],fault=fault,hotspot_source_verification=hotspot_receipt)
            self._execution_store(db,job_id,ex);self._store(db,value,before,'claimed')
        if fault=='interrupt_after_claim':
            with self._tx() as db:
                ex=self._execution(db,job_id);ex.update(phase='interrupted_fixture',tree_stopped=True)
                self._execution_store(db,job_id,ex)
            return self.get(job_id)
        started=time.perf_counter();files={'input.json':raw,
            'input.fasta':('>'+glycosylation.sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()}
        if n06_raw is not None:files['input/n06-result.json']=n06_raw
        error=None;diagnostic=None;exit_code=0
        try:
            if fault=='compute_failure':raise RuntimeFault('TOOL_FAILED','Controlled local calculation failure')
            observed=encode(dict(biopython_version=Bio.__version__,method='overlap-aware-regex-lookahead',result=scan(body)))
            if fault=='corrupt_output':observed=b'{"truncated":true}'
            publish(self.root,path+'/output/observation.json',observed);files['output/observation.json']=observed
        except (RuntimeFault,OSError,ValueError) as exc:
            error=exc.code if isinstance(exc,RuntimeFault) else 'TOOL_FAILED';diagnostic=str(exc);exit_code=1
        elapsed=time.perf_counter()-started
        if elapsed>body['timeout_seconds']:
            error='TIMEOUT';diagnostic='Local calculation exceeded its declared deadline';exit_code=124
            with self._tx() as db:
                current=self._job(db,job_id)
                if current['stop_reason'] is None:self._stop(db,current,'timeout')
        actual=dict(job_id=job_id,attempt_id=value['attempt_id'],execution_identity=value['execution_identity'],
            exit_code=exit_code,error_code=error,diagnostic=diagnostic,stopped_confirmed=True,
            backend='trusted-local-in-process',container_id=None,network_used=False,biopython_version=Bio.__version__,
            elapsed_seconds=elapsed,recovered=False,hotspot_source_verification=hotspot_receipt)
        current=self.get(job_id)
        built=self._build_glycosylation_result(current,body,files,actual,fault)
        ex=self.execution(job_id);ex.update(phase='collected',tree_stopped=True,elapsed_seconds=elapsed)
        return self._finish_development(job_id,ex,files,built)

    @staticmethod
    def _build_glycosylation_result(job,body,files,execution,fault):
        from .glycosylation.result import result
        return result(job,body,files,execution,fault)

    def reconcile(self,job_id):
        before=self.get(job_id)
        if before['tool_id']==codon.TOOL:
            from .codon.service import recover
            return recover(self,before)
        if before['tool_id'] in (epitope_map.TOOL,glycosylation.TOOL,domains.TOOL,developability.TOOL,wt_draft.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL):return self._reconcile_local(before)
        if before['tool_id'] not in TOOLS:return super().reconcile(job_id)
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
                if not ex.get('container_started') and not ex.get('container_id'):
                    # A dead preflight supervisor never created an execution tree.
                    return collect_stopped(self,current,None,recovered=True)
                info=docker.inspect(self.root,ex.get('container_id') or spec(current['tool_id']).SLOT)
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

    def _reconcile_local(self,before):
        """An N06/N07 local in-process calculation has no child tree to guess or restart."""
        if before['state'] in TERMINAL or before['state']=='queued':return before
        from ..winprocess import alive
        ex=self.execution(before['job_id'])
        if ex.get('phase')!='interrupted_fixture' and alive(ex.get('dispatcher')) is True:
            if before['state']=='reconciling':
                with self._tx() as db:
                    current=self._job(db,before['job_id'])
                    if current['state']=='reconciling':
                        value=copy.deepcopy(current);value['state']='stop_requested' if value['stop_reason'] else 'running'
                        value['lease_epoch']+=1;self._store(db,value,current,'reattached')
            return self.get(before['job_id'])
        worker=spec(before['tool_id'])
        body=worker.request(self._request_bytes(before));path=self.attempt_path(before)
        files={'input.json':self._request_bytes(before)}
        fasta=within(self.root,path+'/input.fasta')
        if fasta.is_file():files['input.fasta']=read_locked(fasta)
        names=('bepipred','netmhc','blast') if worker.TOOL==epitope_map.TOOL else ('structure',) if worker.TOOL==developability.TOOL else ('n06',)
        for name in names:
            source=within(self.root,path+'/input/'+name+'-result.json')
            if source.is_file():files['input/'+name+'-result.json']=read_locked(source,32*1024**2)
        if worker.TOOL in (wt_draft.TOOL,design_backend.TOOL,variant_report.TOOL,epitope_protection.TOOL,codon.TOOL):
            for source in within(self.root,path+'/input').glob('*.json'):
                files['input/'+source.name]=read_locked(source,32*1024**2)
        actual=dict(job_id=before['job_id'],attempt_id=before['attempt_id'],execution_identity=before['execution_identity'],
            exit_code=None,error_code='INTERRUPTED',diagnostic='Local calculation dispatcher ended before durable result publication',
            stopped_confirmed=True,backend='trusted-local-in-process',container_id=None,network_used=False,
            elapsed_seconds=None,recovered=True)
        if worker.TOOL==epitope_protection.TOOL:
            from .epitope_protection.service import result as builder
            actual.update(source_receipts=ex.get('source_receipts'))
        elif worker.TOOL==variant_report.TOOL:
            from .variant_report.service import result as builder
            actual.update(source_receipts=ex.get('source_receipts'))
        elif worker.TOOL==design_backend.TOOL:
            from .design_backend.service import result as builder
            actual.update(source_receipts=ex.get('source_receipts'))
        elif worker.TOOL==wt_draft.TOOL:
            from .wt_draft.service import result as builder
            actual.update(source_receipts=ex.get('source_receipts'))
        elif worker.TOOL==domains.TOOL:
            from .domains.service import result as builder
            actual.update(source_receipts=ex.get('source_receipts'),database_receipt=None)
        elif worker.TOOL==developability.TOOL:
            from .developability.service import result as builder
            actual.update(source_receipt=ex.get('source_receipt'))
        elif worker.TOOL==epitope_map.TOOL:
            actual.update(sources_verified=ex.get('sources_verified'),source_receipts=ex.get('source_receipts'))
            builder=self._build_epitope_map_result
        else:
            actual.update(biopython_version=__import__('Bio').__version__,
                hotspot_source_verification=ex.get('hotspot_source_verification'))
            builder=self._build_glycosylation_result
        current=self.get(before['job_id']);built=builder(current,body,files,actual,ex.get('fault'))
        ex.update(phase='collected',tree_stopped=True,recovered=True)
        return self._finish_development(before['job_id'],ex,files,built)

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
                result.update(status='unreliable',null_reason=error)
                if before['tool_id']==TOOL:result.update(topology=None,raw_record=None)
                elif before['tool_id']==bepipred.TOOL:result.update(raw_scores=None,raw_record=None)
                elif before['tool_id']==netmhc.TOOL:result.update(channels=dict(mhc_i=None,mhc_ii=None))
                elif before['tool_id']==blast.TOOL:result.update(search=None)
                elif before['tool_id']==homology.TOOL:result.update(homolog_set=None,analysis=None)
                elif before['tool_id']==epitope_map.TOOL:result.update(epitopes=None,branch_status=None,blast_similarity=None)
                elif before['tool_id']==glycosylation.TOOL:result.update(glycosylation=None,sequons=None,hotspot_assessment=None)
                elif before['tool_id']==developability.TOOL:result.update(developability=None,steps=None)
                elif before['tool_id']==wt_draft.TOOL:result.update(draft=None)
                elif before['tool_id']==design_backend.TOOL:result.update(audit=None)
                elif before['tool_id']==variant_report.TOOL:result.update(report=None)
                elif before['tool_id']==epitope_protection.TOOL:result.update(protection=None)
                elif before['tool_id']==codon.TOOL:result.update(dna=None)
                elif before['tool_id']==proteinmpnn.TOOL:result.update(generation=None)
                elif before['tool_id']==esm_if1.TOOL:result.update(scoring=None,baseline=None,engineering_rules=None)
                elif before['tool_id']==thermompnn.TOOL:result.update(scan=None)
                elif before['tool_id']==foldx.TOOL:result.update(repair=None,ddg_results=None,variant_ddg=None)
                else:result.update(analysis=None)
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
        if self.get(job_id)['tool_id'] not in TOOLS:return super().artifact_bytes(job_id,artifact_id)
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
