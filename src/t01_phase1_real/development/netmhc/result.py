"""Parse documented 4.2/4.3 native tables without recomputing BindLevel."""
import math
import re

from ...common import RuntimeFault, decode, ensure, sha
from ...resident_result import image_matches, isolation_matches
from .policy import (IMAGE, MHC_I_LENGTHS, MHC_II_LENGTHS, asset_receipt,
    native_output_alleles, sequence_id)

I_HEADER=('Pos','MHC','Peptide','Core','Of','Gp','Gl','Ip','Il','Icore','Identity','Score_EL','%Rank_EL','BindLevel')
II_HEADER=('Pos','MHC','Peptide','Of','Core','Core_Rel','Inverted','Identity','Score_EL','%Rank_EL','Exp_Bind','BindLevel')


def _number(text,minimum,maximum,label):
    value=float(text)
    ensure(math.isfinite(value) and minimum<=value<=maximum,'OUTPUT_INVALID',f'Invalid {label}')
    return value


def _classification(fields):
    raw=' '.join(fields).strip()
    compact=raw.replace(' ','')
    if not raw:return 'NB',raw
    if compact in ('SB','<=SB'):return 'SB',raw
    if compact in ('WB','<=WB'):return 'WB',raw
    raise RuntimeFault('OUTPUT_INVALID','Unknown native BindLevel')


def _version(lines,engine,prefix):
    pattern=re.compile(r'^#\s*'+re.escape(engine)+r'(?:\s*-)?\s*version\s+([^\s]+)',re.I)
    for line in lines:
        match=pattern.match(line.strip())
        if match:
            ensure(match.group(1).startswith(prefix),'OUTPUT_INVALID',f'Unexpected {engine} version')
            return match.group(1)
    raise RuntimeFault('OUTPUT_INVALID',f'Missing {engine} version line')


def _header(lines,kind):
    expected=I_HEADER if kind=='mhc_i' else II_HEADER
    for index,line in enumerate(lines):
        fields=tuple(line.split())
        if fields and fields[0]=='Pos' and 'Peptide' in fields:
            # Current NetMHCpan documentation has MHC; an older 4.2 display used HLA.
            if kind=='mhc_i' and fields==('Pos','HLA',*expected[2:]):return index,fields
            ensure(fields==expected,'OUTPUT_INVALID',f'Unsupported {kind} native columns')
            return index,fields
    raise RuntimeFault('OUTPUT_INVALID',f'Missing {kind} native header')


def _identity(value,expected):
    ensure(value==expected,'OUTPUT_INVALID','Native Identity does not match the bound short sequence ID')


def _coordinate(sequence,peptide,start):
    ensure(start>=1 and start+len(peptide)-1<=len(sequence),'OUTPUT_INVALID','Native Pos is outside the input sequence')
    ensure(sequence[start-1:start-1+len(peptide)]==peptide,'OUTPUT_INVALID','Native peptide/1-based Pos does not map to input')
    return start+len(peptide)-1


def _i_row(fields,sequence,alleles,identity):
    ensure(len(fields)>=13,'OUTPUT_INVALID','Truncated MHC-I row')
    start=int(fields[0]);allele=fields[1];peptide=fields[2];core=fields[3]
    ensure(allele in alleles,'OUTPUT_INVALID','Unrequested MHC-I allele')
    ensure(len(peptide) in MHC_I_LENGTHS and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',peptide),'OUTPUT_INVALID','Invalid MHC-I peptide')
    ensure(re.fullmatch('[ACDEFGHIKLMNPQRSTVWY-]+',core) is not None,'OUTPUT_INVALID','Invalid MHC-I core')
    ensure(all(re.fullmatch('-?\d+',v) for v in fields[4:9]),'OUTPUT_INVALID','Invalid MHC-I core offsets')
    ensure(re.fullmatch('[ACDEFGHIKLMNPQRSTVWY-]+',fields[9]) is not None,'OUTPUT_INVALID','Invalid MHC-I interaction core')
    _identity(fields[10],identity)
    score=_number(fields[11],0,1,'MHC-I Score_EL');rank=_number(fields[12],0,100,'MHC-I %Rank_EL')
    classification,raw=_classification(fields[13:])
    return dict(peptide_seq=peptide,start=start,end=_coordinate(sequence,peptide,start),allele=allele,
        percent_rank=rank,classification=classification,core=core,score_el=score,bind_level_raw=raw,
        interaction_core=fields[9],native_offsets=dict(of=int(fields[4]),gp=int(fields[5]),gl=int(fields[6]),ip=int(fields[7]),il=int(fields[8])))


def _ii_row(fields,sequence,alleles,identity):
    ensure(len(fields)>=11,'OUTPUT_INVALID','Truncated MHC-II row')
    start=int(fields[0]);allele=fields[1];peptide=fields[2];inverted=int(fields[6])
    ensure(allele in alleles,'OUTPUT_INVALID','Unrequested MHC-II allele')
    ensure(len(peptide) in MHC_II_LENGTHS and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',peptide),'OUTPUT_INVALID','Invalid MHC-II peptide')
    ensure(re.fullmatch('-?\d+',fields[3]) is not None and len(fields[4])==9
        and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',fields[4]),'OUTPUT_INVALID','Invalid MHC-II core/offset')
    core_rel=_number(fields[5],0,1,'MHC-II Core_Rel')
    ensure(inverted in (0,1),'OUTPUT_INVALID','Invalid MHC-II Inverted flag')
    _identity(fields[7],identity)
    score=_number(fields[8],0,1,'MHC-II Score_EL');rank=_number(fields[9],0,100,'MHC-II %Rank_EL')
    exp_bind=None if fields[10]=='NA' else _number(fields[10],0,1,'MHC-II Exp_Bind')
    classification,raw=_classification(fields[11:])
    hit=dict(peptide_seq=peptide,start=start,end=_coordinate(sequence,peptide,start),allele=allele,
        percent_rank=rank,classification=classification,core=fields[4],score_el=score,bind_level_raw=raw,
        core_offset=int(fields[3]),core_reliability=core_rel,experimental_binding=exp_bind,inverted=bool(inverted))
    return hit


def parse_channel(raw,sequence,alleles,kind):
    """Return valid rows plus per-row warnings; one bad row never poisons other rows."""
    engine,prefix=('NetMHCpan','4.2') if kind=='mhc_i' else ('NetMHCIIpan','4.3')
    try:
        text=raw.decode('utf-8');lines=text.splitlines();version=_version(lines,engine,prefix);header_index,header=_header(lines,kind)
    except (RuntimeFault,UnicodeError) as exc:
        return dict(status='unavailable',engine=engine,version=None,columns=None,hits=[],observed_rows=0,
            skipped_inverted_rows=0,parse_failures=1,warnings=[dict(level='failure',severity='WARNING',code='OUTPUT_INVALID',message=str(exc))])
    identity=sequence_id(sequence);allowed=native_output_alleles(kind,alleles)
    hits=[];warnings=[];observed=0;inverted=0
    for line_number,line in enumerate(lines[header_index+1:],header_index+2):
        fields=line.split()
        if not fields or not fields[0].isdigit():continue
        observed+=1
        try:
            hit=_i_row(fields,sequence,allowed,identity) if kind=='mhc_i' else _ii_row(fields,sequence,allowed,identity)
            if kind=='mhc_ii' and hit['inverted']:
                inverted+=1;continue
            hits.append(hit)
        except (RuntimeFault,ValueError,TypeError) as exc:
            warnings.append(dict(level='failure',severity='WARNING',code='ROW_PARSE_FAILED',line=line_number,message=str(exc)))
    if not observed:
        warnings.append(dict(level='failure',severity='WARNING',code='NO_NATIVE_ROWS',message=f'{engine} produced no prediction rows'))
    valid_or_intentionally_skipped=len(hits)+inverted
    status='unavailable' if not observed or not valid_or_intentionally_skipped else 'partial' if warnings else 'parsed_unreviewed'
    if observed and not valid_or_intentionally_skipped:
        warnings.append(dict(level='failure',severity='WARNING',code='ALL_ROWS_FAILED',message=f'All {engine} rows failed validation'))
    return dict(status=status,engine=engine,version=version,columns=list(header),hits=hits,observed_rows=observed,
        skipped_inverted_rows=inverted,parse_failures=len([w for w in warnings if w['code']=='ROW_PARSE_FAILED']),warnings=warnings)


def parse(files,body):
    ensure('output/netmhcpan.txt' in files and 'output/netmhciipan.txt' in files,'OUTPUT_INVALID','Both native channel outputs must be retained')
    return dict(mhc_i=parse_channel(files['output/netmhcpan.txt'],body['protein_sequence'],body['mhc_i_alleles'],'mhc_i'),
        mhc_ii=parse_channel(files['output/netmhciipan.txt'],body['protein_sequence'],body['mhc_ii_alleles'],'mhc_ii'))


def _runtime(files,body):
    receipt=asset_receipt();runtime=decode(files['output/runtime.json'])
    ensure(runtime['python_exit_code']==0 and runtime['machine']=='x86_64'
        and isolation_matches(runtime,files,IMAGE,[0,1,2,3]),'OUTPUT_INVALID','Pinned NetMHC runtime/isolation differs')
    ensure(runtime['versions']=={name:receipt['components'][name]['observed_version'] for name in ('mhc_i','mhc_ii')}
        and runtime['package_files']==receipt['runtime_package_files'],'OUTPUT_INVALID','NetMHC package identity/version differs')
    fasta=('>'+sequence_id(body['protein_sequence'])+'\n'+body['protein_sequence']+'\n').encode()
    ensure(runtime['input_json_sha256']==sha(files['input.json']) and runtime['input_fasta_sha256']==sha(files['input.fasta'])
        and files['input.fasta'] in (fasta,fasta.replace(b'\n',b'\r\n')),
        'OUTPUT_INVALID','Executed NetMHC request/FASTA binding differs')
    inventory=runtime['native_output_sha256']
    observed={name[len('output/'):]:raw for name,raw in files.items()
        if name.startswith('output/') and name!='output/runtime.json'}
    ensure(set(inventory)==set(observed)=={'runtime_started.json','netmhcpan.txt','netmhcpan.stderr.txt',
        'netmhciipan.txt','netmhciipan.stderr.txt'},'OUTPUT_INVALID','Native NetMHC output inventory differs')
    ensure(all(sha(observed[name])==digest for name,digest in inventory.items()),
        'OUTPUT_INVALID','Native NetMHC output bytes changed after execution')
    expected={
        'mhc_i':['/tools/src/netMHCpan-4.2/Linux_x86_64/bin/netMHCpan-4.2','-f','/input.fasta','-a',
            ','.join(body['mhc_i_alleles']),'-l','8,9,10,11,12,13,14'],
        'mhc_ii':['/tools/src/netMHCIIpan-4.3/Linux_x86_64/bin/NetMHCIIpan-4.3','-f','/input.fasta','-a',
            ','.join(body['mhc_ii_alleles']),'-length','15']}
    ensure(set(runtime['commands'])==set(expected),'OUTPUT_INVALID','Native NetMHC command receipt is incomplete')
    for kind,argv in expected.items():
        item=runtime['commands'][kind];prefix='netmhcpan' if kind=='mhc_i' else 'netmhciipan'
        if not body[kind+'_alleles']:
            ensure(body.get('host_panel_sha256') and item.get('not_executed') is True
                   and item.get('reason')=='HOST_PANEL_CHANNEL_UNAVAILABLE' and item['argv']==[]
                   and item['exit_code'] is None and item['elapsed_seconds']==0
                   and files['output/'+prefix+'.txt']==files['output/'+prefix+'.stderr.txt']==b''
                   and item['stdout_sha256']==item['stderr_sha256']==sha(b''),
                   'OUTPUT_INVALID','Unavailable channel was executed or contains fabricated output')
            continue
        ensure(item['argv']==argv and type(item['exit_code']) is int and item['elapsed_seconds']>=0
            and item['stdout_sha256']==sha(files['output/'+prefix+'.txt'])
            and item['stderr_sha256']==sha(files['output/'+prefix+'.stderr.txt']),
            'OUTPUT_INVALID','Native NetMHC command/output receipt differs')
    return runtime


def _channel_failure(kind,runtime,files):
    engine='NetMHCpan' if kind=='mhc_i' else 'NetMHCIIpan';prefix='netmhcpan' if kind=='mhc_i' else 'netmhciipan'
    stderr=files['output/'+prefix+'.stderr.txt'].decode('utf-8',errors='replace').strip()[:1024]
    return dict(status='unavailable',engine=engine,version=runtime['versions'][kind].split()[-1],columns=None,hits=[],
        observed_rows=0,skipped_inverted_rows=0,parse_failures=0,warnings=[dict(level='failure',severity='WARNING',
            code='NATIVE_CHANNEL_FAILED',message=f'{engine} exited {runtime["commands"][kind]["exit_code"]}: {stderr}')])


def _check_row_count(channel,kind,body):
    if channel['status']=='unavailable':return
    lengths=MHC_I_LENGTHS if kind=='mhc_i' else MHC_II_LENGTHS
    alleles=body['mhc_i_alleles'] if kind=='mhc_i' else body['mhc_ii_alleles']
    expected=len(alleles)*sum(max(0,len(body['protein_sequence'])-length+1) for length in lengths)
    if channel['observed_rows']!=expected:
        channel['warnings'].append(dict(level='failure',severity='WARNING',code='INCOMPLETE_NATIVE_GRID',
            message=f'Expected {expected} full-FASTA predictions, observed {channel["observed_rows"]}'))
        channel['status']='partial' if channel['hits'] else 'unavailable'


def result(job,body,files,execution,fault=None):
    binding={k:job[k] for k in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()))
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='N05_NETMHC_RAW_PRESENTATION',binding=binding,
        user_sequence_id=body['user_sequence_id'],host_species=body['host_species'],qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,status='unreliable',null_reason=execution.get('error_code'),
        channels=dict(mhc_i=None,mhc_ii=None),controlled_fault=fault,execution=execution,
        panel_selection=dict(mode='explicit_alleles',mhc_tier=None,near_species_warning=False,pan_allele_warning=False,
            pig_mhc_ii_degraded=None,open_item='OI-003',host_mapping_applied=False),
        method_summary=dict(tools=dict(mhc_i='NetMHCpan 4.2e',mhc_ii='NetMHCIIpan 4.3k'),input_mode='full_length_fasta',
            mhc_i_lengths=list(MHC_I_LENGTHS),mhc_ii_lengths=list(MHC_II_LENGTHS),position_base=1,
            classification_source='native BindLevel; never recomputed from project thresholds',inverted_mhc_ii_rows='skipped',
            scientific_rules_approved=False),warnings=[])
    if execution.get('error_code'):
        value['warnings']=[dict(level='failure',severity='WARNING',code=execution['error_code'],
            message=(execution.get('diagnostic') or 'A1/A2 execution unavailable')+'; S-18 caller must WARNING+continue without this T-cell channel')]
        return value
    try:
        ensure(execution.get('stopped_confirmed') is True and execution.get('exit_code')==0 and not execution.get('oom_killed')
            and image_matches(execution,IMAGE),'OUTPUT_INVALID','No clean pinned stopped NetMHC execution')
        runtime=_runtime(files,body);parsed_files=files
        if fault=='corrupt_output':
            parsed_files=dict(files);parsed_files['output/netmhcpan.txt']=b'truncated'
            files['fault/corrupt-netmhcpan.txt']=b'truncated'
        channels={}
        for kind,prefix in [('mhc_i','netmhcpan'),('mhc_ii','netmhciipan')]:
            if not body[kind+'_alleles']:
                channels[kind]=dict(status='unavailable',hits=None,observed_rows=None,skipped_inverted_rows=0,parse_failures=0,
                    assessment_status='NOT_ASSESSED',
                    warnings=[dict(level='failure',severity='WARNING',code='HOST_PANEL_CHANNEL_UNAVAILABLE',
                        message='Registered host panel has no validated executable alleles for '+kind+'; not evaluated')])
            elif runtime['commands'][kind]['exit_code']:
                channels[kind]=_channel_failure(kind,runtime,files)
            else:
                alleles=body['mhc_i_alleles'] if kind=='mhc_i' else body['mhc_ii_alleles']
                channels[kind]=parse_channel(parsed_files['output/'+prefix+'.txt'],body['protein_sequence'],alleles,kind)
                _check_row_count(channels[kind],kind,body)
        value['channels']=channels
        available=[name for name,channel in channels.items() if channel['status']!='unavailable']
        warnings=[w for channel in channels.values() for w in channel['warnings']]
        value.update(status='raw_predictions_unreviewed' if len(available)==2 else 'partial_unreliable' if available else 'unreliable',
            null_reason=None if available else 'ALL_CHANNELS_UNAVAILABLE',warnings=warnings)
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        execution.update(error_code='OUTPUT_INVALID',diagnostic=str(exc));value.update(null_reason='OUTPUT_INVALID',warnings=[
            dict(level='failure',severity='WARNING',code='OUTPUT_INVALID',message=str(exc)+'; S-18 caller must WARNING+continue')])
    return value
