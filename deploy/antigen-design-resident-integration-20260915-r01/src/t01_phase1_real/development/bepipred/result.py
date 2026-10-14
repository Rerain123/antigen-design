"""Strict raw CLI output validation; project S-17/S-19 postprocessing is not inferred."""
import csv
import io
import math
import struct

from ...common import RuntimeFault, decode, encode, ensure, sha
from ..policy import sequence_id
from .policy import HERE, IMAGE, PARAMETERS
from ...resident_result import image_matches, isolation_matches

CSV_COLUMNS=['Accession','Residue','BepiPred-3.0 score','BepiPred-3.0 linear epitope score']
NATIVE_FILES={'raw_output.csv','Bcell_epitope_preds.fasta','Bcell_epitope_top_20pct_preds.fasta',
    'Bcell_linepitope_top_20pct_preds.fasta','output_interactive_figures.html'}


def finite(value):
    ensure(type(value) in (int,float) and math.isfinite(value) and 0<=value<=1,'OUTPUT_INVALID','Nonfinite or out-of-domain native probability')
    return value


def parse(files,sequence):
    ident=sequence_id(sequence);length=len(sequence);prefix='output/result/'
    receipt=decode((HERE/'assets.json').read_bytes());runtime=decode(files['output/runtime.json'])
    ensure(runtime['python_exit_code']==0 and runtime['tool_version']=='BepiPred-3.0' and runtime['source_modules_modified'] is False,
        'OUTPUT_INVALID','No clean unchanged upstream CLI execution')
    ensure(runtime['packages']==receipt['packages'] and runtime['python']==receipt['python']
        and isolation_matches(runtime,files,IMAGE,list(range(8))),'OUTPUT_INVALID','Pinned runtime/isolation differs')
    fasta=('>'+ident+'\n'+sequence+'\n').encode()
    ensure(runtime['input_fasta_sha256']==sha(files['input.fasta']) and files['input.fasta'] in (fasta,fasta.replace(b'\n',b'\r\n')),
        'OUTPUT_INVALID','Executed FASTA identity differs')
    inventory=runtime['native_output_sha256']
    ensure(set(inventory)=={n[len('output/'):] for n in files if n.startswith('output/') and n!='output/runtime.json'},
        'OUTPUT_INVALID','Native output inventory is incomplete or unexpected')
    ensure(all(sha(files['output/'+n])==digest for n,digest in inventory.items()),'OUTPUT_INVALID','Native output bytes changed')
    ensure({n[len(prefix):] for n in files if n.startswith(prefix)}==NATIVE_FILES,'OUTPUT_INVALID','Required CLI products missing or unexpected')
    observed=decode(files['output/observations.json'])
    ensure(observed['upstream_cli_sha256']==receipt['upstream_cli_sha256'] and observed['bp3_source_sha256']==receipt['bp3_source_sha256']
        and sorted(observed['folds'],key=lambda r:r['name'])==sorted(receipt['folds'],key=lambda r:r['name']),
        'OUTPUT_INVALID','CLI, bp3 or five-fold model identity differs')
    ensure(observed['model_variant']=='BP3C50IDFFNN' and observed['add_seq_len'] is False and observed['threshold']==0.1512
        and observed['top_fraction']==0.2 and observed['rolling_window']==9,'OUTPUT_INVALID','Native CLI parameter/variant changed')
    ensure(len(observed['records'])==1,'OUTPUT_INVALID','Expected exactly one executed sequence')
    record=observed['records'][0]
    ensure(record['internal_sequence_id']==ident and record['sequence']==sequence and record['sequence_sha256']==sha(sequence.encode())
        and record['embedding_shape']==[length,1280] and record['embedding_file']=='encodings/'+ident+'_0.pt',
        'OUTPUT_INVALID','ESM input or embedding length differs')
    ensure(sha(files['output/'+record['embedding_file']])==record['embedding_sha256'],'OUTPUT_INVALID','Embedding artifact changed')
    ensure(len(record['fold_probabilities'])==5 and all(len(f)==length for f in record['fold_probabilities'])
        and len(record['average_probabilities'])==len(record['rolling_mean'])==length,'OUTPUT_INVALID','Five-fold score lengths differ')
    for fold in record['fold_probabilities']:
        for value in fold:finite(value)
    reader=csv.reader(io.StringIO(files[prefix+'raw_output.csv'].decode('utf-8')))
    ensure(next(reader)==CSV_COLUMNS,'OUTPUT_INVALID','Unsupported raw CSV columns')
    rows=list(reader);ensure(len(rows)==length,'OUTPUT_INVALID','Raw score length differs from input')
    scores=[]
    for i,row in enumerate(rows):
        ensure(len(row)==4 and row[:2]==[ident,sequence[i]],'OUTPUT_INVALID','CSV row identity/order changed')
        prob=finite(float(row[2]));smooth=finite(float(row[3]))
        ensure(prob==record['average_probabilities'][i] and smooth==record['rolling_mean'][i],'OUTPUT_INVALID','CSV scores differ from native tensors')
        # Numeric consistency check only, not a project score selection rule.
        mean=math.fsum(f[i] for f in record['fold_probabilities'])/5
        ensure(abs(mean-prob)<=8*2**-24,'OUTPUT_INVALID','Five-fold average mismatch')
        scores.append(dict(sequence_position=i+1,residue=sequence[i],ensemble_probability=prob,linear_epitope_score=smooth))
    probabilities=[s['ensemble_probability'] for s in scores];smoothed=[s['linear_epitope_score'] for s in scores]
    ensure(all(abs(math.fsum(probabilities[max(0,i-4):min(length,i+5)])/9-smoothed[i])<=1e-12 for i in range(length)),
        'OUTPUT_INVALID','Native zero-padded window-nine smoothing differs')
    raw_masks={}
    threshold=struct.unpack('f',struct.pack('f',0.1512))[0]  # PyTorch compares in float32.
    expected={
        'Bcell_epitope_preds.fasta':{i for i,p in enumerate(probabilities) if p>=threshold},
        'Bcell_epitope_top_20pct_preds.fasta':set(sorted(range(length),key=lambda i:probabilities[i],reverse=True)[:round(length*.2)]),
        'Bcell_linepitope_top_20pct_preds.fasta':set(sorted(range(length),key=lambda i:smoothed[i],reverse=True)[:round(length*.2)])}
    for name,selected in expected.items():
        lines=files[prefix+name].decode('utf-8').splitlines()
        ensure(len(lines)==2 and lines[0]=='>'+ident and lines[1].upper()==sequence,'OUTPUT_INVALID','FASTA product sequence/identity differs')
        mask=''.join(aa if i in selected else aa.lower() for i,aa in enumerate(sequence))
        ensure(lines[1]==mask,'OUTPUT_INVALID','Native threshold/Top20 product disagrees with scores')
        raw_masks[name]=lines[1]
    html=files[prefix+'output_interactive_figures.html']
    ensure(html.lstrip().startswith(b'<div>') and html.rstrip().endswith(b'</div>') and b'Plotly.newPlot' in html and ident.encode() in html,
        'OUTPUT_INVALID','Incomplete native Plotly HTML fragment')
    return dict(raw_scores=scores,raw_record=dict(internal_sequence_id=ident,csv_columns=CSV_COLUMNS,classification_fastas=raw_masks,
        native_parameters=PARAMETERS,embedding_shape=record['embedding_shape'],folds=observed['folds']),runtime_observation=runtime)


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='BEPIPRED_RAW_SCORES',binding=binding,execution=execution,
        user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',evidence_kind='G0_REAL_OUTPUT',
        usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,production_status='NOT_DEPLOYED',requires_review=True,
        status='unreliable',null_reason=execution.get('error_code'),raw_scores=None,raw_record=None,controlled_fault=fault,
        postprocessing=dict(status='review_required',open_item='OI-026',linear_scores=None,linear_peaks=None,conf_scores=None,conf_peaks=None,
            epitope_map=None,issues=['score column/smoothing applicability','Top20 combination/ties/rounding','peak filtering/bridging order and mean range',
                'CLI no-length variant versus web length feature','native >= threshold versus project peak > threshold']),
        method_summary=dict(tool='BepiPred-3.0',bp3='0.0.12.7',esm='esm2_t33_650M_UR50D',native_parameters=PARAMETERS,
            raw_classifications_are_project_peaks=False,structure_consumed=False,scientific_rules_approved=False),warnings=[])
    try:
        if execution.get('error_code'):raise RuntimeFault(execution['error_code'],execution.get('diagnostic') or 'A3 execution unavailable')
        ensure(execution.get('stopped_confirmed') is True and type(execution.get('exit_code')) is int and execution['exit_code']==0
            and not execution.get('oom_killed') and image_matches(execution,IMAGE),'OUTPUT_INVALID','No clean pinned stopped execution')
        parsed_files=files
        if fault=='corrupt_output':
            parsed_files=dict(files);parsed_files['output/result/raw_output.csv']=b'truncated'
            files['fault/corrupt-raw-output.csv']=b'truncated'
        parsed=parse(parsed_files,body['protein_sequence'])
        value.update(parsed,status='raw_scores_unreviewed',null_reason=None,warnings=[
            dict(code='LINEAR_ONLY',level='quality',severity='WARNING',message='一期仅线性路径；不运行 DiscoTope'),
            dict(code='BEPIPRED_POSTPROCESSING_REVIEW',level='quality',severity='WARNING',message='原始列和原包分类完整保留；OI-026 未签收，项目 linear_scores/peaks/map 保持 null')])
    except (RuntimeFault,KeyError,ValueError,TypeError,StopIteration,UnicodeError,csv.Error) as exc:
        error=execution.get('error_code') or 'OUTPUT_INVALID';execution.update(error_code=error,diagnostic=str(exc))
        value.update(status='unreliable',null_reason=error,raw_scores=None,raw_record=None,failure_policy='A3_UNAVAILABLE_HALT',
            warnings=[dict(code=error,level='failure',severity='WARNING',message='A3 原始分数不可用；禁止作为无表位成功结果消费：'+str(exc))])
    return value
