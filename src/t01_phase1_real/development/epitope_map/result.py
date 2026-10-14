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


def _presentation(hits,sequence,summaries=()):
    length=len(sequence);rank=[None]*length;sb=[set() for _ in sequence];support=[set() for _ in sequence]
    for hit in hits:
        for offset in range(hit['start']-1,hit['end']):
            rank[offset]=hit['percent_rank'] if rank[offset] is None else min(rank[offset],hit['percent_rank'])
            if hit['classification'] in ('SB','WB'):support[offset].add(hit['allele'])
            if hit['classification']=='SB':sb[offset].add(hit['allele'])
    for summary in summaries:
        from ..netmhc.pan import summary_sb
        ensure(len(summary['min_percent_rank'])==length,
            'OUTPUT_INVALID','Pan residue summary length differs')
        strong=list(summary_sb(summary,length))
        for i,value in enumerate(summary['min_percent_rank']):
            ensure(value is None or type(value) in (int,float) and math.isfinite(value) and 0<=value<=100,
                'OUTPUT_INVALID','Pan residue rank is invalid')
            if value is not None:rank[i]=value if rank[i] is None else min(rank[i],value)
            sb[i].update(strong[i])
            if summary['has_binding'][i]:support[i].add('PRESENT_IN_NATIVE_BATCH')
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


def _blast_similarity(source,item,sequence):
    state=item['state']
    if state!='available':
        return dict(state=state,source_artifact=item['artifact'],reason_code=item['reason_code'],
            result_status=None,database=None,search_status=None,raw_hsp_count=None,qualifying_hsp_count=None,
            raw_hsps=None,qualifying_hsps=None,interpretation='NOT_AVAILABLE',iedb_evidence=None,
            epitope_evidence_level=None,epitope_regions=None,contact_residues=None)
    ensure(isinstance(source,dict) and source.get('tool_id')=='t01.real.blast'
        and source.get('status') in ('similarity_hits_unreviewed','no_qualifying_similarity_hit')
        and source.get('qualification')=='DEVELOPMENT_UNREVIEWED'
        and source.get('usable_for_pipeline') is False and source.get('automatic_handoff') is False
        and source.get('scientific_signoff') is None,'OUTPUT_INVALID','BLAST source qualification differs')
    binding=source.get('binding');database=source.get('database');search=source.get('search')
    ensure(isinstance(binding,dict) and binding.get('sequence_sha256')==sha(sequence.encode())
        and isinstance(database,dict) and isinstance(search,dict),'OUTPUT_INVALID','BLAST source binding/database/search is incomplete')
    ensure(database.get('database_id')==binding.get('database_id')
        and database.get('manifest_sha256')==binding.get('database_manifest_sha256')
        and database.get('qualification') in ('ENGINEERING_FIXTURE','TARGET_DATABASE_UNREVIEWED'),
        'OUTPUT_INVALID','BLAST database ID/manifest/qualification differs')
    raw=search.get('raw_hsps');qualified=search.get('qualifying_hsps')
    ensure(isinstance(raw,list) and isinstance(qualified,list)
        and search.get('raw_hsp_count')==len(raw) and search.get('qualifying_hsp_count')==len(qualified)
        and qualified==[row for row in raw if isinstance(row,dict) and row.get('passes_registered_thresholds') is True],
        'OUTPUT_INVALID','BLAST HSP counts or threshold subset differs')
    search_status='hit' if qualified else 'no_hit'
    prior=source.get('iedb_prior')
    ensure(search.get('search_status')==search_status
        and source['status']==('similarity_hits_unreviewed' if qualified else 'no_qualifying_similarity_hit'),
        'OUTPUT_INVALID','BLAST hit state or prohibited epitope semantics differs')
    if prior is None:
        ensure(all(search.get(name) is None for name in ('iedb_hit','evidence_level','epitope_regions','contact_residues')),
            'OUTPUT_INVALID','Ordinary similarity cannot provide IEDB evidence')
    else:
        ensure(source.get('scope')=='N03_LOCAL_IEDB_PRIOR' and prior['database_id']==binding['database_id']
            and all(search.get(n)==prior[n] for n in ('iedb_hit','evidence_level','epitope_regions','contact_residues')),
            'OUTPUT_INVALID','IEDB prior differs from N03 result')
        for row in prior['epitope_regions']:
            ensure(type(row['start']) is int and type(row['end']) is int and 1<=row['start']<=row['end']<=len(sequence)
                and row['e_level']=='E3-region' and row['source_iedb_id'] and row['reference_id']
                and row['epitope_type'] in ('B','T','mixed','unknown'), 'OUTPUT_INVALID','Invalid IEDB region')
        for row in prior['contact_residues']:
            ensure(type(row['sequence_position']) is int and 1<=row['sequence_position']<=len(sequence)
                and row['residue']==sequence[row['sequence_position']-1]
                and row['evidence_source']==row['source_iedb_id'] and row['coordinate_sha256']
                and row['epitope_type'] in ('B','T','mixed','unknown'), 'OUTPUT_INVALID','Invalid coordinate-backed IEDB contact')
    result=dict(state='available',source_artifact=item['artifact'],reason_code=None,result_status=source['status'],
        database={name:database[name] for name in ('database_id','manifest_sha256','qualification','purpose','source','blast')},
        search_status=search_status,raw_hsp_count=len(raw),qualifying_hsp_count=len(qualified),raw_hsps=raw,
        qualifying_hsps=qualified,interpretation='ORDINARY_PROTEIN_SIMILARITY_ONLY',iedb_evidence=None,
        epitope_evidence_level=None,epitope_regions=None,contact_residues=None)
    if prior is not None:
        result.update(interpretation='IEDB_LOCAL_LITERATURE_PRIOR',iedb_evidence=prior,
            epitope_evidence_level=prior['evidence_level'],epitope_regions=prior['epitope_regions'],
            contact_residues=prior['contact_residues'])
    return result


def _empty_hotspot_proof(b_map,t_map,parameters):
    """Prove emptiness only when the configured strict threshold permits it."""
    from .composition import channel_weights as normalized_weights
    present=[name for name,value in (('bcell',b_map),('tcell',t_map)) if value is not None]
    channel_weights=normalized_weights(present,parameters)
    maxima=dict(bcell=0.2,tcell=0.5)
    components={name:channel_weights[name]*maxima[name] for name in present}
    upper_bound=sum(components.values())
    if upper_bound>parameters['hotspot_threshold']:return None
    return dict(kind='S19_SOURCE_SET_UPPER_BOUND',qualification='DEVELOPMENT_UNREVIEWED',
        available_channels=present,channel_weights=channel_weights,
        maximum_evidence_weight_by_channel={name:maxima[name] for name in present},
        maximum_component_by_channel=components,maximum_possible_score=upper_bound,
        normalized_score_upper_bound=1.0,hotspot_threshold=parameters['hotspot_threshold'],comparison='STRICT_GREATER_THAN',
        source_semantics=dict(bcell='BEPIPRED_ONLY_MAX_E1',tcell='NETMHC_MAX_E2',e3_e4='ABSENT_BY_SCOPE'),
        conclusion='NO_HOTSPOT_CAN_EXCEED_THRESHOLD',scientific_consumption=False)


def prediction_type_join(b_map, prior):
    """A3 §3: inherit assay type on overlapping pieces only; keep E1 identity."""
    evidence=list(prior['epitope_regions'])+[dict(r,start=r['sequence_position'],end=r['sequence_position'])
                                            for r in prior['contact_residues']]
    profile=b_map['raw_score_profiles']['ensemble_probability'];lo,hi=min(profile),max(profile)
    joined=[]
    for region in b_map['regions']:
        bounds={region['start'],region['end']+1}
        overlaps=[r for r in evidence if r['start']<=region['end'] and r['end']>=region['start']]
        for row in overlaps:
            bounds.update((max(region['start'],row['start']),min(region['end']+1,row['end']+1)))
        ordered=sorted(bounds)
        for start,limit in zip(ordered,ordered[1:]):
            end=limit-1;active=[r for r in overlaps if r['start']<=start and r['end']>=end]
            types=sorted({r['epitope_type'] for r in active})
            values=profile[start-1:end];mask=[v>.1512 for v in values];positives=[v for v in values if v>.1512]
            from ..bepipred.postprocessing import segments
            joined.append(dict(region,start=start,end=end,epitope_type=types[0] if len(types)==1 else None,
                source_peak=dict(start=region['start'],end=region['end']),
                mean_score=math.fsum(values)/len(values),mean_score_all=math.fsum(values)/len(values),
                mean_score_positive=math.fsum(positives)/len(positives) if positives else None,
                positive_count=len(positives),positive_fraction=len(positives)/len(values),bridge_count=len(values)-len(positives),
                longest_positive_run=max((r['end']-r['start']+1 for r in segments(mask)),default=0),
                norm_score=(math.fsum((v-lo)/(hi-lo) for v in values)/len(values)) if hi>lo else None,
                overlapping_iedb_types=types,overlapping_iedb_ids=sorted({r['source_iedb_id'] for r in active}),
                type_join_status='CONFLICTING_ASSAY_TYPES_NOT_COLLAPSED' if len(types)>1 else 'OVERLAP' if types else 'PREDICTION_ONLY'))
    b_map['regions']=joined


def literature_prediction_norm(b_map,region,artifact):
    """S19: normalize the available BepiPred field, then average this interval.

    Literature strength stays in the E3/E4 weight. This is a predictor score
    attached to an evidence interval, never an invented experimental probability.
    """
    if not b_map or b_map.get('selected_project_score')!='ensemble_probability':return {}
    profile=b_map['raw_score_profiles']['ensemble_probability'];lo,hi=min(profile),max(profile)
    values=profile[region['start']-1:region['end']]
    score=math.fsum((v-lo)/(hi-lo) for v in values)/len(values) if hi>lo else None
    return dict(norm_score=score,prediction_score_mean=math.fsum(values)/len(values),
        normalization_evidence=dict(source='BEPIPRED_RAW_ENSEMBLE_SEQUENCE_MINMAX_INTERVAL_MEAN_ALL',
            source_artifact=artifact,score_profile_sha256=sha(encode(profile)),
            prediction_policy=b_map['prediction_policy'],minimum=lo,maximum=hi,
            interval=[region['start'],region['end']],status='computed' if hi>lo else 'NOT_ASSESSED',
            reason_code=None if hi>lo else 'DEGENERATE_SCORE_RANGE'))


def compute(body,sources):
    from .composition import settings
    parameters=settings(body.get('composition_parameters'))
    sequence=body['protein_sequence'];bepi=sources.get('bepipred');netmhc=sources.get('netmhc')
    blast_similarity=_blast_similarity(sources.get('blast'),body['blast_input'],sequence)
    b_map=None;t_map=None;warnings=[]
    if netmhc is not None and netmhc.get('status')=='unreliable':
        warnings.append(dict(code='T_CELL_CHANNELS_UNAVAILABLE',level='failure',severity='WARNING',
            message='S-18 无可用 T 细胞预测通道；继续可用 B 通道，不把缺失结果解释为无结合。'))
        netmhc=None
    if bepi is not None:
        ensure(bepi['tool_id']=='t01.real.bepipred' and bepi['status']=='raw_scores_unreviewed'
            and bepi['binding']['sequence_sha256']==sha(sequence.encode()) and bepi['postprocessing']['status'] in ('review_required','computed_pending_calibration'),
            'OUTPUT_INVALID','BepiPred source qualification/binding differs')
        rows=bepi['raw_scores'];ensure(len(rows)==len(sequence),'OUTPUT_INVALID','BepiPred score length differs')
        for index,row in enumerate(rows,1):
            ensure(row['sequence_position']==index and row['residue']==sequence[index-1],
                'OUTPUT_INVALID','BepiPred residue identity/order differs')
        b_map=dict(status='review_required',regions=None,
            raw_score_profiles=dict(ensemble_probability=[row['ensemble_probability'] for row in rows],
                linear_epitope_score=[row['linear_epitope_score'] for row in rows]),
            selected_project_score=None,closure='OI-026')
        if bepi['postprocessing']['status']=='computed_pending_calibration':
            from ..bepipred.postprocessing import project
            processed=project(rows)
            ensure(processed==bepi['postprocessing'],'OUTPUT_INVALID','BepiPred postprocessing differs from expert policy')
            profile=processed['linear_scores'];lo,hi=min(profile),max(profile)
            normalized=[(v-lo)/(hi-lo) for v in profile] if hi>lo else None
            regions=[dict(r,predictor='BepiPred-3.0',epitope_type=None,evidence_source='prediction',
                epitope_level='E1-single',norm_score=math.fsum(normalized[r['start']-1:r['end']])/(r['end']-r['start']+1)
                if normalized is not None else None) for r in processed['linear_peaks_threshold']]
            b_map.update(status='computed_pending_calibration',regions=regions,
                selected_project_score='ensemble_probability',closure=None,
                normalization=dict(method='SEQUENCE_MINMAX_THEN_INTERVAL_MEAN_ALL_RESIDUES',minimum=lo,maximum=hi,
                    status='computed' if hi>lo else 'review_required',reason_code=None if hi>lo else 'DEGENERATE_SCORE_RANGE'),
                prediction_policy=processed['policy_version'],linear_peaks_top20=processed['linear_peaks_top20'],
                top20_audit=processed['top20_audit'])
            warnings.append(dict(code='B_CELL_PREDICTED_REGIONS_PENDING_CALIBRATION',level='quality',severity='WARNING',
                message='阈值区段进入图1，前20%区段仅用于报告对照；均为连续预测候选区段，拟议参数待回测。'))
        else:
            warnings.append(dict(code='B_CELL_PEAKS_REVIEW_REQUIRED',level='quality',severity='WARNING',
                message='历史BepiPred产物未包含10-09项目后处理，不追改旧预测区段。'))
    if netmhc is not None:
        ensure(netmhc['tool_id']=='t01.real.netmhc' and netmhc['binding']['sequence_sha256']==sha(sequence.encode())
            and netmhc['status'] in ('raw_predictions_unreviewed','partial_unreliable'),
            'OUTPUT_INVALID','NetMHC source qualification/binding differs')
        channels={};all_hits=[];summaries=[]
        for name in ('mhc_i','mhc_ii'):
            source=netmhc['channels'].get(name)
            if source is None or source['status']=='unavailable':channels[name]=None;continue
            if source.get('hits_storage')=='REGISTERED_BATCH_ARTIFACTS':
                ensure(netmhc.get('scope') in ('N05_NETMHC_PACKAGE_PAN','N05_NETMHC_HOST_PANEL') and source.get('residue_summary') is not None,
                    'OUTPUT_INVALID','Unbound pan residue summary')
                summaries.append(source['residue_summary']);channels[name]=[]
            else:
                mapped=[_hit(row,sequence) for row in source['hits']];channels[name]=mapped;all_hits.extend(mapped)
        presentation=_presentation(all_hits,sequence,summaries)
        t_map=dict(status='computed' if all(value is not None for value in channels.values()) else 'partial',
            mhc_i_hits=channels['mhc_i'],mhc_ii_hits=channels['mhc_ii'],channel_status={name:
                ('unavailable' if channels[name] is None else netmhc['channels'][name]['status']) for name in channels},**presentation)
        if t_map['status']=='partial':warnings.append(dict(code='T_CELL_CHANNEL_PARTIAL',level='failure',severity='WARNING',
            message='至少一个 NetMHC 通道不可用；保留其余通道地图，不将缺失通道解释为空命中。'))
        if summaries:
            t_map.update(hits_storage='REGISTERED_BATCH_ARTIFACTS',batch_sources=netmhc['batch_sources'],
                panel_selection=netmhc['panel_selection'],mhc_i_hits=None,mhc_ii_hits=None)
    ensure(b_map is not None or t_map is not None,'TOOL_FAILED','S-19 has no available epitope predictor input')
    prior=blast_similarity.get('iedb_evidence')
    experimental=bool(prior and (prior['epitope_regions'] or prior['contact_residues']))
    proof=None if experimental else _empty_hotspot_proof(b_map,t_map,parameters)
    if experimental:
        if b_map is not None and b_map.get('status')=='computed_pending_calibration':
            prediction_type_join(b_map,prior)
        evidence_rows=list(prior['epitope_regions'])+[dict(row,start=row['sequence_position'],end=row['sequence_position'],
            e_level='E4-contact') for row in prior['contact_residues']]
        for row in evidence_rows:
            mapped=dict(row,epitope_level=row['e_level'],evidence_source='IEDB',
                        evidence_provenance=dict(source_iedb_id=row['source_iedb_id'],reference_id=row['reference_id'],
                            source_artifact=body['blast_input']['artifact']))
            if row['epitope_type'] in ('B','mixed','unknown'):
                if b_map is None:b_map=dict(status='literature_only',regions=[])
                if b_map.get('regions') is None:b_map['regions']=[]
                if row['epitope_type']=='unknown':mapped=dict(mapped,reasons=['epitope_type=unknown, 默认bcell'])
                b_map['regions'].append(dict(mapped,**literature_prediction_norm(b_map,row,
                    (body.get('bepipred_input') or {}).get('artifact'))))
            if row['epitope_type'] in ('T','mixed'):
                if t_map is None:t_map=dict(status='literature_only',evidence_regions=[])
                t_map.setdefault('evidence_regions',[]).append(mapped)
        warnings.append(dict(code='IEDB_WEIGHTED_HOTSPOT_REVIEW_REQUIRED',level='quality',severity='WARNING',
            message='已保留 IEDB E3/E4 来源；原无实验来源的空热点上界证明不再适用，不能把未计算热点当作空集合。'))
    elif proof is not None:
        warnings.append(dict(code='HOTSPOT_EMPTY_BY_SOURCE_SET_BOUND_UNREVIEWED',level='quality',severity='WARNING',
            message='按 S-19 固定权重，当前来源集合的逐残基得分上界不超过严格热点阈值；输出工程空热点，科学消费仍未签收。'))
    topology=sources.get('topology');labels=None
    if topology is not None:
        ensure(topology['binding']['sequence_sha256']==sha(sequence.encode()),'OUTPUT_INVALID','Topology sequence differs')
        if topology.get('topology') is not None:
            labels=topology['topology']['labels']
            ensure(len(labels)==len(sequence),'OUTPUT_INVALID','Topology labels length differs')
    from .composition import synthesize
    composition=synthesize(len(sequence),b_map,t_map,labels,parameters)
    if 'composition_parameters' in body:composition['configured_parameters']=parameters
    if composition['density'] is None:
        warnings.append(dict(code='WEIGHTED_DENSITY_REVIEW_REQUIRED',level='quality',severity='WARNING',
            message='逐残基合成缺少已确定的预测分数或归一化输入；保留可计算通道，不补零或猜选列。'))
    elif not composition['hotspots']:
        warnings.append(dict(code='NO_ANTIGENIC_HOTSPOTS',level='quality',severity='WARNING',
            message='无抗原性热点——表位保护仅E3/E4生效, 继续流程'))
    if blast_similarity['state']=='available' and prior is None:
        warnings.append(dict(code='BLAST_SIMILARITY_NOT_EPITOPE_EVIDENCE',level='disclosure',severity='WARNING',
            message='N03 普通蛋白相似性结果已原样回连；不生成 IEDB 命中、E3/E4 证据、表位区或接触残基。'))
    elif blast_similarity['state']=='upstream_unavailable':
        warnings.append(dict(code='N03_UPSTREAM_UNAVAILABLE',level='failure',severity='WARNING',
            message='N03 诊断产物已验证；执行不可用不得解释为无相似性命中。'))
    epitopes=dict(b_cell_epitope_map=b_map,t_cell_presentation_map=t_map,
        b_cell_antigenic_hotspot_map=dict(status='computed_empty_unreviewed' if proof is not None else 'review_required',
            hotspots=[] if proof is not None else None,proof=proof,
            reason_codes=(['IEDB_WEIGHTED_HOTSPOT_REVIEW_REQUIRED'] if experimental else ['WEIGHTED_DENSITY_REVIEW_REQUIRED']) if proof is None else
                ['CURRENT_SOURCE_SET_SCORE_UPPER_BOUND_LE_STRICT_THRESHOLD','OI-007_SCIENTIFIC_WEIGHT_SIGNOFF_PENDING']),
        immunogenicity_scores=None,density_per_residue=composition['density'])
    if composition['hotspots'] is not None:
        epitopes['b_cell_antigenic_hotspot_map'].update(status='computed_unreviewed',hotspots=composition['hotspots'],reason_codes=[])
        warnings=[w for w in warnings if w['code']!='IEDB_WEIGHTED_HOTSPOT_REVIEW_REQUIRED']
    return dict(epitopes=epitopes,composition=composition,blast_input=body['blast_input'],blast_similarity=blast_similarity,warnings=warnings,
        branch_status=dict(b_cell=b_map['status'] if b_map else 'unavailable',
            t_cell=t_map['status'] if t_map else 'unavailable',blast=blast_similarity['state'],
            weighted_hotspot=epitopes['b_cell_antigenic_hotspot_map']['status'],density=composition['status']))


def _parse(files,body):
    source_names={name:decode(files['input/'+name+'-result.json']) for name in ('bepipred','netmhc','blast','topology')
        if 'input/'+name+'-result.json' in files}
    observed=decode(files['output/observation.json'])
    ensure(isinstance(observed,dict) and set(observed)=={'method','source_sha256','result'}
        and observed['method']=='s19-bounded-map-v10.5','OUTPUT_INVALID','Unexpected N06 observation shape/method')
    ensure(observed['source_sha256']=={name:sha(encode(value)) for name,value in source_names.items()},
        'OUTPUT_INVALID','N06 observation source hashes differ')
    expected=compute(body,source_names);ensure(observed['result']==expected,'OUTPUT_INVALID','Stored N06 map differs from deterministic calculation')
    return expected


def result(job,body,files,execution,fault=None):
    from .composition import settings
    binding={key:job[key] for key in ['run_id','request_id','job_id','attempt_id','execution_identity','execution_profile','rule_profile']}
    binding.update(input_sha256=job['request_artifact']['sha256'],sequence_sha256=sha(body['protein_sequence'].encode()),
        upstream_artifacts={name:body[name+'_input']['artifact'] for name in ('bepipred','netmhc','blast')})
    value=dict(contract_version='0.2.0',tool_id=job['tool_id'],scope='N06_S19_EPITOPE_MAP',binding=binding,
        execution=execution,user_sequence_id=body['user_sequence_id'],qualification='DEVELOPMENT_UNREVIEWED',
        evidence_kind='G0_REAL_OUTPUT',usable_for_pipeline=False,automatic_handoff=False,scientific_signoff=None,
        production_status='NOT_DEPLOYED',requires_review=True,status='unreliable',null_reason=execution.get('error_code'),
        epitopes=None,branch_status=None,blast_input=body['blast_input'],blast_similarity=None,controlled_fault=fault,
        method_summary=dict(operation='S-19 bounded three-map development',rule_profile=registered_rules(),
            composition_parameters=settings(body.get('composition_parameters')),
            t_cell_map_computed=False,bepipred_raw_columns_bound=False,b_cell_peaks_computed=False,
            blast_source_bound=False,blast_similarity_retained=False,iedb_evidence_generated=False,
            e3_e4_evidence_generated=False,weighted_hotspots_computed=False,density_per_residue_computed=False,
            weighted_hotspot_emptiness_proved=False,hotspot_score_upper_bound=None,
            n07_hotspot_window_generated=False,n07_hotspot_input_available=False),warnings=[])
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
            b_cell_peaks_computed=(parsed['epitopes']['b_cell_epitope_map'] or {}).get('status')=='computed_pending_calibration',
            density_per_residue_computed=parsed['epitopes']['density_per_residue'] is not None,
            weighted_hotspots_computed=parsed['composition']['hotspots'] is not None,
            t_cell_map_computed=parsed['epitopes']['t_cell_presentation_map'] is not None,
            bepipred_raw_columns_bound='raw_score_profiles' in (parsed['epitopes']['b_cell_epitope_map'] or {}),
            blast_source_bound=parsed['blast_similarity']['state']=='available',
            blast_similarity_retained=parsed['blast_similarity']['state']=='available',
            iedb_evidence_generated=parsed['blast_similarity'].get('iedb_evidence') is not None,
            e3_e4_evidence_generated=bool(parsed['blast_similarity'].get('epitope_regions') or parsed['blast_similarity'].get('contact_residues')),
            weighted_hotspot_emptiness_proved=parsed['epitopes']['b_cell_antigenic_hotspot_map']['proof'] is not None,
            hotspot_score_upper_bound=(parsed['epitopes']['b_cell_antigenic_hotspot_map']['proof'] or {}).get('maximum_possible_score'),
            n07_hotspot_input_available=parsed['epitopes']['b_cell_antigenic_hotspot_map']['hotspots'] is not None)
        value.update(parsed,status=status,null_reason=None)
    except (RuntimeFault,KeyError,ValueError,TypeError,UnicodeError) as exc:
        error=execution.get('error_code') or getattr(exc,'code','OUTPUT_INVALID')
        execution.update(error_code=error,diagnostic=str(exc));value.update(status='unreliable',null_reason=error,
            epitopes=None,branch_status=None,blast_similarity=None,warnings=[dict(code=error,level='failure',severity='WARNING',
                message='N06 上游绑定或地图计算失败，结果不可消费：'+str(exc))])
    return value
