"""Verify native data/cluster/MSA facts before trusted S-14/S-15 calculation."""
from ...common import RuntimeFault, decode, ensure, sha
from . import compute, policy
from ...resident_result import image_matches, isolation_matches


def validated_observation(body, files, execution):
    runtime = decode(files['output/runtime.json'])
    ensure(runtime['python_exit_code']==0 and runtime['machine']=='x86_64'
           and isolation_matches(runtime,files,policy.IMAGE,[0,1]),
           'OUTPUT_INVALID','N08 runtime or isolation differs')
    ensure(runtime['versions']==policy.asset_receipt()['observed_versions'], 'OUTPUT_INVALID','N08 native versions differ')
    ensure(runtime['input_json_sha256']==sha(files['input.json']) and runtime['input_fasta_sha256']==sha(files['input.fasta'])
           and runtime['database_manifest_sha256']==body['database_manifest_sha256'],
           'OUTPUT_INVALID','N08 executed input binding differs')
    observed = {k.removeprefix('output/'):v for k,v in files.items() if k.startswith('output/') and k!='output/runtime.json'}
    ensure(set(observed)==set(runtime['native_output_sha256']) and all(sha(v)==runtime['native_output_sha256'][k] for k,v in observed.items()),
           'OUTPUT_INVALID','N08 native inventory or bytes differ')
    receipt = execution['database_receipt']
    manifest_raw = observed['database-manifest.json']
    ensure(sha(manifest_raw)==body['database_manifest_sha256'],'OUTPUT_INVALID','Executed data manifest changed')
    manifest = decode(manifest_raw)
    ensure(all(manifest[k]==receipt[k] for k in ('database_id','qualification','purpose','source','files')),
           'OUTPUT_INVALID','Executed data identity differs from operator receipt')
    for item in manifest['files']:
        raw = observed['database-'+item['path']]
        ensure(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'OUTPUT_INVALID','Executed database file changed')
    seqs = compute.fasta(observed['database-sequences.fasta'].decode())
    records = decode(observed['database-annotations.json'])
    collected = [dict(r,sequence=seqs[r['id']]) for r in records if r['organism_name']==body['organism_name'] and r['protein_name']==body['protein_name']]
    expected = [r for r in collected if r['source_label']=='wild']
    observation = decode(observed['observation.json'])
    ensure(observation['collected_ids']==[r['id'] for r in collected]
           and observation['pre_dedup_ids']==[r['id'] for r in expected]
           and observation['vaccine_sequences']==[r for r in collected if r['source_label']=='vaccine']
           and observation['excluded_source_ids']==[r['id'] for r in collected if r['source_label'] not in ('wild','vaccine')],
           'OUTPUT_INVALID','Collection/source separation differs')
    required_commands = set()
    if len(expected)<20:
        required_commands |= {'makeblastdb','supplement'}
        ensure(runtime['commands']['supplement']['argv']==['blastp','-query','/input.fasta','-db','/tmp/supplement','-num_threads','2',
            '-max_target_seqs','500','-max_hsps','10','-outfmt','6 qseqid sseqid pident qstart qend sstart send evalue bitscore'],
            'OUTPUT_INVALID','Supplement invocation differs')
        ensure(runtime['commands']['makeblastdb']['argv']==['makeblastdb','-in','/database/sequences.fasta','-dbtype','prot',
            '-parse_seqids','-out','/tmp/supplement','-blastdb_version','5'],'OUTPUT_INVALID','Supplement index invocation differs')
    if expected:
        required_commands |= {'mmseqs','mafft'}
        ensure(runtime['commands']['mmseqs']['argv']==['mmseqs','easy-cluster','/tmp/selected.fasta','/tmp/dedup','/tmp/mmseqs-tmp',
            '--min-seq-id','0.99','--alignment-mode','3','--threads','2'],'OUTPUT_INVALID','Dedup invocation differs')
        ensure(runtime['commands']['mafft']['argv']==['mafft','--amino','--auto','--thread','2','--inputorder','/out/alignment-input.fasta'],
            'OUTPUT_INVALID','MSA invocation differs')
    ensure(set(runtime['commands'])==required_commands and all(x['exit_code']==0 for x in runtime['commands'].values()),
           'OUTPUT_INVALID','Native command inventory or exit differs')
    for name, command in runtime['commands'].items():
        stdout = observed['global.msa.fasta' if name=='mafft' else name+'.txt']
        ensure(sha(stdout)==command['stdout_sha256'] and sha(observed[name+'.stderr.txt'])==command['stderr_sha256'],
               'OUTPUT_INVALID','Native stdout/stderr binding differs')
    if not expected:
        ensure(observation['collection_status']=='no_sequences' and observation['representatives']==[],
               'OUTPUT_INVALID','Empty collection misreported')
        return observation, None
    rows = [line.split('\t') for line in observed['clusters.tsv'].decode().splitlines()]
    ensure(all(len(row)==2 for row in rows),'OUTPUT_INVALID','Malformed cluster table')
    cluster = {}
    for rep, member in rows: cluster.setdefault(rep,[]).append(member)
    members = [m for items in cluster.values() for m in items]
    ensure(sorted(members)==sorted(r['id'] for r in expected) and all(rep in items for rep,items in cluster.items()),
           'OUTPUT_INVALID','Clusters must partition the ungrouped wild set exactly once')
    representatives = compute.fasta(observed['representatives.fasta'].decode())
    ensure(set(representatives)==set(cluster) and all(representatives[k]==seqs[k] for k in representatives)
           and cluster==observation['clusters'] and observation['representatives']==[r for r in expected if r['id'] in representatives],
           'OUTPUT_INVALID','Representative source or cluster mapping differs')
    alignment_input = compute.fasta(observed['alignment-input.fasta'].decode())
    ensure(alignment_input=={compute.ANCHOR:body['protein_sequence'],**representatives},'OUTPUT_INVALID','Alignment input members differ')
    msa = compute.fasta(observed['global.msa.fasta'].decode(),aligned=True)
    return observation, msa


def result(job,body,files,execution,fault=None):
    binding = {k:job[k] for k in ('run_id','request_id','job_id','attempt_id','execution_identity','execution_profile')}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
                   database_id=body['database_id'],database_manifest_sha256=body['database_manifest_sha256'])
    value = dict(contract_version='0.1.0',tool_id=policy.TOOL,scope='N08_LOCAL_HOMOLOGY',binding=binding,
        user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',
        usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',
        requires_review=True,status='unreliable',null_reason=execution.get('error_code'),execution=execution,
        database=execution.get('database_receipt'),homolog_set=None,analysis=None,controlled_fault=fault,warnings=[],
        method_summary=dict(versions=policy.asset_receipt()['observed_versions'],image_id=policy.IMAGE,
            rules=policy.registered_rules(),sequence_weighting='off',dedup_identity=.99,
            dedup_scope='ungrouped wild analysis input after vaccine separation; once before grouping',
            mmseqs_parameters='easy-cluster --min-seq-id 0.99 --alignment-mode 3 --threads 2; remaining pinned tool defaults',
            alignment='single MAFFT --amino --auto; query anchor excluded from all statistics',
            group_alignment='row subsets of the one global MSA, original columns retained',
            coordinate_base=1,scientific_rules_owner='trusted backend',target_database_validated=False))
    if execution.get('error_code'): return value
    try:
        ensure(execution.get('stopped_confirmed') is True and execution.get('exit_code')==0
               and image_matches(execution,policy.IMAGE) and not execution.get('oom_killed')
               and execution.get('database_receipt') is not None,'OUTPUT_INVALID','No clean pinned N08 execution')
        if fault=='corrupt_output':
            files['fault/corrupt-observation.json']=b'{}'
            raise ValueError('Controlled corrupt observation')
        observation, msa = validated_observation(body,files,execution)
        value['homolog_set']=observation
        if msa is None:
            execution.update(error_code='TOOL_FAILED',diagnostic='S-13 returned zero wild homologs; S-14/S-15 not executed')
            value.update(status='no_homolog_sequences',null_reason='NO_HOMOLOG_SEQUENCES')
            return value
        analysis = compute.analyze(msa,observation['representatives'],body,value['database']['qualification'])
        value.update(status='homology_computed_unreviewed',null_reason=None,analysis=analysis)
        value['warnings'] = ['DEVELOPMENT_UNREVIEWED','TARGET_DATABASE_NOT_VALIDATED']
        if value['database']['qualification']=='ENGINEERING_FIXTURE':value['warnings'].append('ENGINEERING_DATA_ONLY')
        if observation['supplementation']['status']=='review_required':value['warnings'].append('LOCAL_SUPPLEMENT_HIT_ADMISSION_UNRESOLVED')
        for key in ('subtype_parse_stats','host_parse_stats'):
            if analysis['groups'][key]['missing_rate']>.30: value['warnings'].append(key.upper()+'_MISSING_OVER_30_PERCENT')
        if not analysis['confidence']['stratification_supported']:value['warnings'].append('INDEPENDENT_STRATIFICATION_NOT_ESTABLISHED')
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc))
        value.update(status='unreliable',null_reason='OUTPUT_INVALID',homolog_set=None,analysis=None)
    return value
