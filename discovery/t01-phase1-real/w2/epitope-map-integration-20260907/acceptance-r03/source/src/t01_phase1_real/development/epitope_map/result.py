"""Compute only the S-19 branches whose current scientific rules are unambiguous."""
import math

from ...common import RuntimeFault, decode, encode, ensure, sha
from .policy import registered_rules


def _hit(row,sequence):
    fields=('peptide_seq','start','end','allele','percent_rank','classification','core')
    ensure(isinstance(row,dict) and all(name in row for name in fields),'OUTPUT_INVALID','Malformed NetMHC hit')
    start,end=row['start'],row['end'];peptide=row['peptide_seq']
    ensure(type(start) is int and type(end) is int and 1<=start<=end<=len(sequence)
        and end==start+len(peptide)-1 and sequence[start-1:end]==peptide,
        'OUTPUT_INVALID','NetMHC hit does not map to the bound sequence')
    ensure(row['classification'] in ('SB','WB','NB') and isinstance(row['allele'],str)
        and type(row['percent_rank']) in (int,float) and math.isfinite(row['percent_rank']) and 0<=row['percent_rank']<=100,
        'OUTPUT_INVALID','Malformed NetMHC rank/classification')
    return {name:row[name] for name in fields}


def _intervals(mask):
    result=[];start=None
    for index,active in enumerate(mask,1):
        if active and start is None:start=index
        if start is not None and (not active or index==len(mask)):
            end=index if active and index==len(mask) else index-1
            result.append([start,end]);start=None
    return result


def _presentation(hits,sequence):
    length=len(sequence);rank=[None]*length;sb=[set() for _ in sequence];support=[set() for _ in sequence]
    for hit in hits:
        for offset in range(hit['start']-1,hit['end']):
            rank[offset]=hit['percent_rank'] if rank[offset] is None else min(rank[offset],hit['percent_rank'])
            if hit['classification'] in ('SB','WB'):support[offset].add(hit['allele'])
            if hit['classification']=='SB':sb[offset].add(hit['allele'])
    values=[value for value in rank if value is not None]
    if values and max(values)>min(values):
        low,high=min(values),max(values)
        inverse=[None if value is None else 1-(value-low)/(high-low) for value in rank]
        normalization=dict(status='computed',minimum_percent_rank=low,maximum_percent_rank=high,direction='1-minmax')
    elif values:
        inverse=None;normalization=dict(status='review_required',reason_code='DEGENERATE_RANK_RANGE',
            minimum_percent_rank=values[0],maximum_percent_rank=values[0],direction='1-minmax')
    else:
        inverse=None;normalization=dict(status='not_computed',reason_code='NO_MHC_HITS',direction='1-minmax')
    raw=_intervals([len(alleles)>=2 for alleles in sb]);merged=[]
    for start,end in raw:
        if merged and start-merged[-1][1]-1<=10:merged[-1][1]=end
        else:merged.append([start,end])
    hotspots=[]
    for start,end in merged:
        alleles=sorted({allele for values_at_position in sb[start-1:end] for allele in values_at_position})
        hotspots.append(dict(start=start,end=end,epitope_level='E2-consensus',support='SB_DISTINCT_ALLELES_GTE_2',
            alleles=alleles,allele_count=len(alleles)))
    e1=_intervals([bool(supports) and len(strong)<2 for supports,strong in zip(support,sb)])
    evidence_regions=[dict(start=start,end=end,epitope_level='E1-single',support='SINGLE_SB_OR_WB') for start,end in e1]
    return dict(residue_min_percent_rank=rank,residue_inverse_minmax_score=inverse,normalization=normalization,
        presentation_hotspots=hotspots,evidence_regions=evidence_regions)


def compute(body,sources):
    sequence=body['protein_sequence'];bepi=sources.get('bepipred');netmhc=sources.get('netmhc')
    b_map=None;t_map=None;warnings=[]
    if bepi is not None:
        ensure(bepi['tool_id']=='t01.real.bepipred' and bepi['status']=='raw_scores_unreviewed'
            and bepi['binding']['sequence_sha256']==sha(sequence.encode()) and bepi['postprocessing']['status']=='review_required',
            'OUTPUT_INVALID','BepiPred source qualification/binding differs')
        rows=bepi['raw_scores'];ensure(len(rows)==len(sequence),'OUTPUT_INVALID','BepiPred score length differs')
        for index,row in enumerate(rows,1):
            ensure(row['sequence_position']==index and row['residue']==sequence[index-1],
                'OUTPUT_INVALID','BepiPred residue identity/order differs')
        b_map=dict(status='review_required',regions=None,
            raw_score_profiles=dict(ensemble_probability=[row['ensemble_probability'] for row in rows],
                linear_epitope_score=[row['linear_epitope_score'] for row in rows]),
            selected_project_score=None,closure='OI-026')
        warnings.append(dict(code='B_CELL_PEAKS_REVIEW_REQUIRED',level='quality',severity='WARNING',
            message='BepiPred 原始两列已绑定；项目选列、峰提取及后处理仍由 OI-026 约束。'))
    if netmhc is not None:
        ensure(netmhc['tool_id']=='t01.real.netmhc' and netmhc['binding']['sequence_sha256']==sha(sequence.encode())
            and netmhc['status'] in ('raw_predictions_unreviewed','partial_unreliable'),
            'OUTPUT_INVALID','NetMHC source qualification/binding differs')
        channels={};all_hits=[]
        for name in ('mhc_i','mhc_ii'):
            source=netmhc['channels'].get(name)
            if source is None or source['status']=='unavailable':channels[name]=None;continue
            mapped=[_hit(row,sequence) for row in source['hits']];channels[name]=mapped;all_hits.extend(mapped)
        presentation=_presentation(all_hits,sequence)
        t_map=dict(status='computed' if all(value is not None for value in channels.values()) else 'partial',
            mhc_i_hits=channels['mhc_i'],mhc_ii_hits=channels['mhc_ii'],channel_status={name:
                ('unavailable' if channels[name] is None else netmhc['channels'][name]['status']) for name in channels},**presentation)
        if t_map['status']=='partial':warnings.append(dict(code='T_CELL_CHANNEL_PARTIAL',level='failure',severity='WARNING',
            message='至少一个 NetMHC 通道不可用；保留其余通道地图，不将缺失通道解释为空命中。'))
    ensure(b_map is not None or t_map is not None,'TOOL_FAILED','S-19 has no available epitope predictor input')
    warnings.append(dict(code='WEIGHTED_MAP_REVIEW_REQUIRED',level='quality',severity='WARNING',
        message='OI-007/026 未签收；证据权重、B 细胞抗原热点和 density_per_residue 不计算。'))
    epitopes=dict(b_cell_epitope_map=b_map,t_cell_presentation_map=t_map,
        b_cell_antigenic_hotspot_map=dict(status='review_required',hotspots=None,
            reason_codes=['OI-026_BEPIPRED_POSTPROCESSING','OI-007_EVIDENCE_WEIGHTS']),
        immunogenicity_scores=None,density_per_residue=None)
    return dict(epitopes=epitopes,blast_input=body['blast_input'],warnings=warnings,
        branch_status=dict(b_cell='review_required' if b_map else 'unavailable',
            t_cell=t_map['status'] if t_map else 'unavailable',weighted_hotspot='review_required',density='review_required'))


def _parse(files,body):
    source_names={name:decode(files['input/'+name+'-result.json']) for name in ('bepipred','netmhc')
        if 'input/'+name+'-result.json' in files}
    observed=decode(files['output/observation.json'])
    ensure(isinstance(observed,dict) and set(observed)=={'method','source_sha256','result'}
        and observed['method']=='s19-bounded-map-v10.5','OUTPUT_INVALID','Unexpected N06 observation shape/method')
    ensure(observed['source_sha256']=={name:sha(encode(value)) for name,value in source_names.items()},
        'OUTPUT_INVALID','N06 observation source hashes differ')
    expected=compute(body,source_names);ensure(observed['result']==expected,'OUTPUT_INVALID','Stored N06 map differs from deterministic calculation')
    return expected


def result(job,body,files,execution,fault=None):
    binding={key:job[key] for key in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        upstream_artifacts={name:body[name+'_input']['artifact'] for name in ('bepipred','netmhc')})
    value=dict(contract_version='0.1.0',tool_id=job['tool_id'],scope='N06_S19_EPITOPE_MAP',binding=binding,
        execution=execution,user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,status='unreliable',null_reason=execution.get('error_code'),
        epitopes=None,branch_status=None,blast_input=body['blast_input'],controlled_fault=fault,
        method_summary=dict(operation='S-19 bounded three-map development',rule_profile=registered_rules(),
            t_cell_map_computed=False,bepipred_raw_columns_bound=False,b_cell_peaks_computed=False,
            weighted_hotspots_computed=False,density_per_residue_computed=False,n07_hotspot_window_generated=False),warnings=[])
    try:
        if execution.get('error_code'):raise RuntimeFault(execution['error_code'],execution.get('diagnostic') or 'N06 unavailable')
        ensure(execution.get('stopped_confirmed') is True and execution.get('exit_code')==0
            and execution.get('backend')=='trusted-local-in-process' and execution.get('network_used') is False
            and execution.get('container_id') is None and execution.get('sources_verified') is True,
            'OUTPUT_INVALID','No clean registered N06 local calculation/source verification')
        parsed_files=files
        if fault=='corrupt_output':
            parsed_files=dict(files);parsed_files['output/observation.json']=b'{"truncated":true}'
        parsed=_parse(parsed_files,body)
        source_states=[body[name+'_input']['state'] for name in ('bepipred','netmhc')]
        status='maps_unreviewed' if all(state=='available' for state in source_states) else 'partial_maps_unreviewed'
        value['method_summary'].update(
            t_cell_map_computed=parsed['epitopes']['t_cell_presentation_map'] is not None,
            bepipred_raw_columns_bound=parsed['epitopes']['b_cell_epitope_map'] is not None)
        value.update(parsed,status=status,null_reason=None)
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        error=execution.get('error_code') or getattr(exc,'code','OUTPUT_INVALID')
        execution.update(error_code=error,diagnostic=str(exc));value.update(status='unreliable',null_reason=error,
            epitopes=None,branch_status=None,warnings=[dict(code=error,level='failure',severity='WARNING',
                message='N06 上游绑定或地图计算失败，结果不可消费：'+str(exc))])
    return value
