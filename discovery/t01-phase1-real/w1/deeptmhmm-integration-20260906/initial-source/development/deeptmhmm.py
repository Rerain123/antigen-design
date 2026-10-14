"""Parse complete bound raw artifacts; return explicit development-only topology."""
import hashlib
import json
import struct
import zlib

from ..common import encode, sha
from .policy import asset_receipt, sequence_id
from .raw_format import three_line, region_table, probability_table, require, LABELS
from .token_trace import validate_trace


def verify_png(raw):
    require(raw.startswith(b'\x89PNG\r\n\x1a\n'),'Not a PNG plot')
    offset=8;chunks=[];compressed=b''
    while offset<len(raw):
        require(offset+12<=len(raw),'Truncated PNG chunk')
        size=struct.unpack('>I',raw[offset:offset+4])[0]
        name=raw[offset+4:offset+8];data=raw[offset+8:offset+8+size]
        require(offset+12+size<=len(raw),'Truncated PNG data')
        crc=struct.unpack('>I',raw[offset+8+size:offset+12+size])[0]
        require(zlib.crc32(name+data)==crc,'PNG checksum mismatch')
        if name==b'IHDR':
            require(not chunks and size==13,'Invalid PNG header')
            width,height,depth,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data)
            require(0<width<=10000 and 0<height<=10000 and depth==8 and color in (2,6)
                and compression==filtering==interlace==0,'Unsupported PNG plot encoding')
        if name==b'IDAT':compressed+=data
        chunks.append(name);offset+=size+12
    require(chunks and chunks[0]==b'IHDR' and chunks[-1]==b'IEND' and raw[-12:-8]==b'\0\0\0\0','Incomplete PNG')
    expected=height*(1+width*(3 if color==2 else 4))
    require(expected<=32*1024**2,'PNG exceeds plot limit')
    decoder=zlib.decompressobj();pixels=decoder.decompress(compressed,expected+1)
    require(decoder.eof and not decoder.unused_data and len(pixels)==expected,'Corrupt PNG pixels')


def parse(files, seq, fault=None):
    identifier=sequence_id(seq)
    prefix='output/result/'
    required=['predicted_topologies.3line','TMRs.gff3','deeptmhmm_results.md','plot.png',
        'probabilities/'+identifier+'_probs.csv','embeddings/'+hashlib.md5(seq.encode()).hexdigest()]
    for name in required:
        require(files.get(prefix+name), 'Missing required artifact: '+name)
    prediction=files[prefix+'predicted_topologies.3line'].decode('utf-8')
    if fault=='corrupt_output':
        lines=prediction.splitlines();lines[2]=lines[2][:-1]
        prediction='\n'.join(lines)+'\n'
        # Actual raw output is retained; only a declared parser input copy is damaged.
        files['fault/invalid-prediction.3line']=prediction.encode()
    records=three_line(prediction,{identifier:seq})
    counts=region_table(files[prefix+'TMRs.gff3'].decode('utf-8'),records)
    record=records[identifier];labels=record['labels']
    expected='BETA' if 'B' in labels else 'SP+TM' if 'S' in labels and 'M' in labels else 'TM' if 'M' in labels else 'SP' if 'S' in labels else 'GLOB'
    require(record['type']==expected,'Protein type/label contradiction')
    probability=probability_table(files[prefix+required[4]].decode('utf-8'),identifier,seq)
    require([p for p in files if p.startswith(prefix+'probabilities/')]==[prefix+required[4]],'Unexpected probability filename')
    verify_png(files[prefix+'plot.png'])
    require(identifier in files[prefix+'deeptmhmm_results.md'].decode('utf-8'),'Report identity mismatch')
    runtime=json.loads(files['output/runtime.json'])
    require(runtime['python_exit_code']==0 and not runtime['cuda_available']
        and runtime['network_interfaces']==[[1,'lo']],'Runtime failure/offline mismatch')
    require(runtime['packages']==asset_receipt()['method_summary']['runtime_packages'],'Runtime version mismatch')
    trace=validate_trace([json.loads(line) for line in files['output/token_trace.jsonl'].splitlines()],seq)
    pb=bool(set(labels)&set('PB'))
    topology=None if pb else dict(labels=[LABELS[x] for x in labels],
        segments=[{k:s[k] for k in ['type','start','end']} for s in record['segments']],
        tm_count=sum(s['label']=='M' for s in record['segments']),outside_length=labels.count('O'),has_signal='S' in labels)
    return dict(topology=topology,raw_record=dict(record_id=identifier,raw_tmr_count=counts[identifier],**record),
        status='unreliable' if pb else 'parsed_unverified',null_reason='PB_OUT_OF_DOMAIN' if pb else None,
        warnings=[dict(level='failure',severity='WARNING',code='PB_OUT_OF_DOMAIN',message='P/B 超出项目标签域；保留原始标签并禁止自动交接')] if pb else [],
        probability=probability,token_observation=trace)


def result(job, request, files, execution, fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(request['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id='t01.real.deeptmhmm',evidence_kind='G0_REAL_OUTPUT',
        qualification='DEVELOPMENT_UNREVIEWED',binding=binding,user_sequence_id=request['user_sequence_id'],
        internal_sequence_id=sequence_id(request['protein_sequence']),usable_for_pipeline=False,automatic_handoff=False,
        requires_review=True,scientific_signoff=None,production_status='NOT_DEPLOYED',
        method_summary=asset_receipt()['method_summary'],execution=execution,controlled_fault=fault)
    value['method_summary']['identity_scope']='UNIFIED_DEVELOPMENT_EXECUTION; no scientific approval'
    value['method_summary']['parameters']['long_sequence_chunk_code']='Original code retained; exact token/chunk observations are per execution'
    if execution.get('error_code'):
        value.update(topology=None,raw_record=None,status='unreliable',null_reason=execution['error_code'],
            warnings=[dict(level='failure',severity='WARNING',code=execution['error_code'],message=execution.get('diagnostic','执行未完成'))])
    else:
        try: value.update(parse(files,request['protein_sequence'],fault))
        except (ValueError,KeyError,TypeError,OSError,zlib.error,struct.error) as exc:
            execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc))
            value.update(topology=None,raw_record=None,status='unreliable',null_reason='OUTPUT_INVALID',
                warnings=[dict(level='failure',severity='WARNING',code='OUTPUT_INVALID',message=str(exc))])
    return value
