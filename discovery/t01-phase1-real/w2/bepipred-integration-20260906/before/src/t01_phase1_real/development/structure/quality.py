"""S-09 local metadata logic. SOP/Structure ToolSpec plus six adopted decisions.

Source declarations are recorded, never inferred from B-factors or host names.
The prediction provenance/scale branch remains closed for this local input adapter.
"""
import math


def warning(code,message,level='failure'):
    return dict(code=code,message=message,level=level,severity='WARNING')


def experimental(method,resolution):
    """Adopted S-09 experimental bins; no invented confidence for uncovered methods."""
    known=method in ('X-ray','cryo-EM','NMR')
    topology=resolution is not None and resolution<=4.0
    if not known or method=='NMR' and resolution is not None and resolution>=3.0:
        return dict(status='review_required',quality=None,s11_quality_condition=None,
            topology_formula_diagnostic_only=topology,warnings=[warning('UNCOVERED_EXPERIMENTAL_BRANCH','实验方法/分辨率组合需要算法复核；不借用其他方法档位')])
    notices=[]
    if resolution is None:
        confidence='medium';notices=[warning('RESOLUTION_UNAVAILABLE','无法获取分辨率，默认 medium；建议人工复核','quality')]
    elif method=='NMR' or resolution<(3.0 if method=='X-ray' else 3.5):confidence='high'
    elif resolution<=4.0:confidence='medium'
    else:confidence='low'
    return dict(status='evaluated_unverified',quality=dict(confidence=confidence,topology_reliable=topology,low_confidence_regions=None),
        s11_quality_condition=confidence!='low',topology_formula_diagnostic_only=None,warnings=notices)


def assess(declaration,metadata):
    kind=declaration['kind'];fields=metadata['entries']
    method_rows=[r for r in fields if r['group']=='method' and r['parse_status']!='missing']
    resolution_rows=[r for r in fields if r['group']=='resolution' and r['parse_status']!='missing']
    # Canonicalize only exact observed method names; plain ELECTRON MICROSCOPY is
    # not sufficient evidence of cryo-EM.
    methods={'X-RAY DIFFRACTION':'X-ray','X-RAY':'X-ray','SOLUTION NMR':'NMR','SOLID-STATE NMR':'NMR','NMR':'NMR',
        'CRYO-EM':'cryo-EM','ELECTRON CRYO-MICROSCOPY':'cryo-EM'}
    values={methods.get(r['value'].strip().upper(),r['value'].strip()) for r in method_rows}
    numbers={r['parsed_number'] for r in resolution_rows if r['parse_status']=='numeric'}
    method=next(iter(values)) if len(values)==1 else None
    resolution=next(iter(numbers)) if len(numbers)==1 else None
    evidence=dict(declaration=declaration,source='user_experimental' if kind=='experimental' else kind,
        method=method,resolution=resolution,metadata_origins=method_rows+resolution_rows,
        source_status='USER_DECLARED_UNVERIFIED',missing_atom_fraction=None,mean_plddt=None,plddt_per_residue=None,ptm=None)
    if kind=='unknown':
        result=dict(status='evaluated_unverified',quality=dict(confidence='low',topology_reliable=False,low_confidence_regions=None),
            s11_quality_condition=False,topology_formula_diagnostic_only=None,warnings=[warning('UNKNOWN_STRUCTURE_SOURCE','未知结构来源，默认 low；原文件实验字段不改写用户来源声明','quality')])
    elif kind=='predicted':
        result=dict(status='review_required',quality=None,s11_quality_condition=None,topology_formula_diagnostic_only=None,
            warnings=[warning('PREDICTION_PROVENANCE_UNVERIFIED','本地预测文件的引擎、pLDDT 标度/来源与映射未验收；不从 B-factor 猜 pLDDT')])
    elif len(values)>1 or len(numbers)>1 or any(r['parse_status']=='unparseable' for r in resolution_rows):
        result=dict(status='review_required',quality=None,s11_quality_condition=None,topology_formula_diagnostic_only=None,
            warnings=[warning('QUALITY_METADATA_CONFLICT','实验方法或分辨率元数据冲突/不可解析，保留全部来源位置，不取最优值')])
    else:result=experimental(method,resolution)
    return dict(result,structure=evidence,scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,
        rule_basis='AgentA_SOP_v10.5 S-09; Structure ToolSpec 2c/5; adopted S09-D01/D02a/D02b/D03a/D03b/D03c',
        low_confidence_regions=None,requires_review=True)
