"""Validate BLAST+ receipts and expose raw/threshold-qualified HSPs without IEDB semantics."""
import math
import re

from ...common import RuntimeFault, decode, ensure, sha
from .policy import IMAGE, MAX_HSPS, asset_receipt, sequence_id
from ...resident_result import image_matches, isolation_matches

COLUMNS=('qseqid','sseqid','pident','length','mismatch','gapopen','qstart','qend','sstart','send','evalue',
    'bitscore','qlen','slen','qcovhsp','qseq','sseq','stitle')


def number(text,minimum,maximum,label):
    value=float(text);ensure(math.isfinite(value) and minimum<=value<=maximum,'OUTPUT_INVALID','Invalid '+label);return value


def parse_hsps(raw,body):
    try:lines=raw.decode('utf-8').splitlines()
    except UnicodeError as exc:raise RuntimeFault('OUTPUT_INVALID','BLAST table is not UTF-8') from exc
    ensure(len(lines)<=MAX_HSPS,'OUTPUT_INVALID','BLAST HSP count exceeds the bounded result envelope')
    result=[];seq=body['protein_sequence'];query_id=sequence_id(seq)
    for line_number,line in enumerate(lines,1):
        fields=line.split('\t')
        ensure(len(fields)==len(COLUMNS),'OUTPUT_INVALID',f'BLAST row {line_number} has unexpected columns')
        row=dict(zip(COLUMNS,fields));ensure(row['qseqid']==query_id,'OUTPUT_INVALID','BLAST query identity differs')
        ensure(row['sseqid'] and len(row['sseqid'])<=4096 and all(ord(c)>=32 for c in row['sseqid']),
            'OUTPUT_INVALID','Invalid BLAST subject identity')
        length=int(row['length']);mismatch=int(row['mismatch']);gapopen=int(row['gapopen'])
        qstart=int(row['qstart']);qend=int(row['qend']);sstart=int(row['sstart']);send=int(row['send'])
        qlen=int(row['qlen']);slen=int(row['slen'])
        ensure(1<=length<=max(qlen,slen) and mismatch>=0 and gapopen>=0 and qlen==len(seq) and slen>=1,
            'OUTPUT_INVALID','Invalid BLAST HSP lengths/counts')
        ensure(1<=qstart<=qend<=qlen and 1<=sstart<=send<=slen,'OUTPUT_INVALID','BLAST coordinates are outside sequence bounds')
        ensure(re.fullmatch('[A-Z*-]+',row['qseq']) is not None and re.fullmatch('[A-Z*-]+',row['sseq']) is not None
            and len(row['qseq'])==len(row['sseq'])==length,'OUTPUT_INVALID','Invalid aligned sequence columns')
        ensure(row['qseq'].replace('-','')==seq[qstart-1:qend],'OUTPUT_INVALID','Aligned query does not map to 1-based coordinates')
        identity=number(row['pident'],0,100,'percent identity');native_coverage=number(row['qcovhsp'],0,100,'query coverage')
        computed=(qend-qstart+1)*100/qlen
        ensure(abs(native_coverage-computed)<=0.501,'OUTPUT_INVALID','Native rounded query coverage differs from 1-based query interval')
        coverage=computed
        evalue=number(row['evalue'],0,float('inf'),'e-value');bitscore=number(row['bitscore'],0,float('inf'),'bit score')
        qualified=identity>=body['thresholds']['identity_percent_min'] and coverage>=body['thresholds']['query_coverage_percent_min']
        result.append(dict(hsp_index=line_number,query_id=row['qseqid'],subject_id=row['sseqid'],subject_title=row['stitle'],
            percent_identity=identity,alignment_length=length,mismatches=mismatch,gap_opens=gapopen,
            query_start=qstart,query_end=qend,subject_start=sstart,subject_end=send,query_length=qlen,subject_length=slen,
            query_coverage_percent=coverage,native_query_coverage_percent=native_coverage,evalue=evalue,bit_score=bitscore,query_alignment=row['qseq'],
            subject_alignment=row['sseq'],passes_registered_thresholds=qualified))
    return result


def _runtime(files,body):
    runtime=decode(files['output/runtime.json']);receipt=asset_receipt()
    ensure(runtime['python_exit_code']==0 and runtime['machine']=='x86_64'
        and isolation_matches(runtime,files,IMAGE,[0,1]),'OUTPUT_INVALID','Pinned BLAST runtime/isolation differs')
    ensure(runtime['versions']=={'blastp':'blastp: 2.17.0+','blastdbcmd':'blastdbcmd: 2.17.0+'}
        and runtime['database_manifest_sha256']==body['database_manifest_sha256'],'OUTPUT_INVALID','BLAST/database version identity differs')
    fasta=('>'+sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
    ensure(runtime['input_json_sha256']==sha(files['input.json']) and runtime['input_fasta_sha256']==sha(files['input.fasta'])
        and files['input.fasta'] in (fasta,fasta.replace(b'\n',b'\r\n')),'OUTPUT_INVALID','Executed BLAST request/FASTA binding differs')
    observed={name[len('output/'):]:raw for name,raw in files.items() if name.startswith('output/') and name!='output/runtime.json'}
    ensure(set(runtime['native_output_sha256'])==set(observed)=={'runtime_started.json','database-info.txt','database-info.stderr.txt',
        'blast.txt','blast.stderr.txt'},'OUTPUT_INVALID','Native BLAST output inventory differs')
    ensure(all(sha(observed[name])==digest for name,digest in runtime['native_output_sha256'].items()),
        'OUTPUT_INVALID','Native BLAST output bytes changed after execution')
    # Prefix is recovered from the recorded argv; exact executable/arguments are fixed below.
    commands=runtime['commands'];ensure(set(commands)=={'database_info','blastp'},'OUTPUT_INVALID','BLAST command receipt is incomplete')
    info_argv=commands['database_info']['argv'];blast_argv=commands['blastp']['argv']
    ensure(len(info_argv)==4 and info_argv[:2]==['/blast/bin/blastdbcmd','-db'] and info_argv[2].startswith('/database/')
        and info_argv[3]=='-info','OUTPUT_INVALID','Unexpected blastdbcmd command')
    expected=['/blast/bin/blastp','-query','/input.fasta','-db',info_argv[2],'-outfmt',
        '6 '+' '.join(COLUMNS),'-max_target_seqs','500','-max_hsps','10','-num_threads','2']
    ensure(blast_argv==expected,'OUTPUT_INVALID','Unexpected blastp command')
    for name,prefix in (('database_info','database-info'),('blastp','blast')):
        item=commands[name]
        ensure(item['exit_code']==0 and item['elapsed_seconds']>=0
            and item['stdout_sha256']==sha(files['output/'+prefix+'.txt'])
            and item['stderr_sha256']==sha(files['output/'+prefix+'.stderr.txt']),
            'OUTPUT_INVALID','Native BLAST command/output receipt differs')
    ensure(receipt['image_id']==IMAGE,'OUTPUT_INVALID','BLAST engine receipt changed')
    return runtime


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        database_id=body['database_id'],database_manifest_sha256=body['database_manifest_sha256'])
    database_receipt=execution.get('database_receipt')
    database_summary=None if not database_receipt else {k:database_receipt[k] for k in
        ('database_id','manifest_sha256','qualification','purpose','source','blast')}
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='N03_LOCAL_PROTEIN_SIMILARITY',binding=binding,
        user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',
        usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',
        requires_review=True,status='unreliable',null_reason=execution.get('error_code'),database=database_summary,
        search=None,controlled_fault=fault,execution=execution,method_summary=dict(tool='NCBI BLAST+',version='2.17.0+',
            image_id=IMAGE,input_mode='single_full_length_protein_fasta',coordinate_base=1,
            thresholds=body['thresholds'],coverage_definition='query HSP interval / full query length',
            native_search='blastp defaults except tabular columns, max_target_seqs=500, max_hsps=10, num_threads=2',
            aggregation='none; every validated HSP retained',evidence_mapping='similarity only; never IEDB literature/E3/E4'),warnings=[])
    if execution.get('error_code'):
        value['warnings']=[dict(level='failure',severity='WARNING',code=execution['error_code'],
            message=(execution.get('diagnostic') or 'Local BLAST execution unavailable')+'; unavailable is not a no-hit result')]
        return value
    try:
        ensure(execution.get('stopped_confirmed') is True and execution.get('exit_code')==0 and not execution.get('oom_killed')
            and image_matches(execution,IMAGE) and database_receipt is not None,
            'OUTPUT_INVALID','No clean pinned stopped BLAST/database execution')
        _runtime(files,body);raw=files['output/blast.txt']
        if fault=='corrupt_output':raw=b'bad\trow';files['fault/corrupt-blast.tsv']=raw
        hsps=parse_hsps(raw,body);qualified=[row for row in hsps if row['passes_registered_thresholds']]
        value['search']=dict(search_status='hit' if qualified else 'no_hit',raw_hsp_count=len(hsps),
            qualifying_hsp_count=len(qualified),raw_hsps=hsps,qualifying_hsps=qualified,iedb_hit=None,
            evidence_level=None,epitope_regions=None,contact_residues=None)
        value.update(status='similarity_hits_unreviewed' if qualified else 'no_qualifying_similarity_hit',null_reason=None)
        if database_receipt['qualification']=='ENGINEERING_FIXTURE':
            value['warnings'].append(dict(level='disclosure',severity='WARNING',code='ENGINEERING_DATABASE_ONLY',
                message='Engineering FASTA/index results do not validate the target database or scientific evidence use'))
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(status='unreliable',null_reason='OUTPUT_INVALID',search=None,
            warnings=[dict(level='failure',severity='WARNING',code='OUTPUT_INVALID',message=str(exc)+'; unavailable is not a no-hit result')])
    return value
