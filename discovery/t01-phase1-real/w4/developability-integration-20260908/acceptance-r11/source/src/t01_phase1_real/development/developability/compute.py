"""S-36a, S-39 and guarded S-40 partial aggregation."""
import math

import Bio
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from ...common import ensure
from .policy import DIMENSIONS
from .propka import assess as assess_propka
from .aggrescan3d import assess as assess_a3d


def sigmoid(value,k):return 1.0/(1.0+math.exp(-k*value))


def gaussian(value,center,sigma):return math.exp(-((value-center)**2)/(2.0*sigma**2))


def expressibility(sequence):
    analysis=ProteinAnalysis(sequence)
    instability=float(analysis.instability_index());gravy=float(analysis.gravy())
    mw_kda=float(analysis.molecular_weight())/1000.0
    length=len(sequence);fraction=lambda residue:sequence.count(residue)/length
    aliphatic=100.0*(fraction('A')+2.9*fraction('V')+3.9*(fraction('I')+fraction('L')))
    score=sigmoid(40.0-instability,.2)*.4+gaussian(gravy,-.25,.3)*.3+sigmoid(100.0-mw_kda,.05)*.3
    return dict(mw_kda=mw_kda,pi=float(analysis.isoelectric_point()),gravy=gravy,
        instability_index=instability,aliphatic_index=aliphatic,score=score,tool='C1(ProtParam)',
        status='computed_unreviewed',method=dict(biopython=Bio.__version__,molecular_weight_unit='kDa',
            molecular_weight_conversion='ProteinAnalysis Da / 1000',aliphatic_formula='Ikai 1980 / ExPASy ProtParam',
            score_formula='SOP v10.5 S-36a'))


def _classification(value):
    if value>=.40:return 'exposed'
    if value>=.20:return 'partial'
    return 'buried'


def _unknown(reason,warnings=None):
    return dict(status='unknown',reliable=False,reason_code=reason,n_term=None,c_term=None,preferred_end=None,
        tool='C34(FreeSASA)',warnings=warnings or [reason],source_qualification=None)


def tag_exposure(structure):
    if structure is None:return _unknown('STRUCTURE_NOT_AVAILABLE')
    report=structure.get('analysis')
    if not isinstance(report,dict):return _unknown('STRUCTURE_ANALYSIS_NOT_AVAILABLE')
    quality=report.get('quality') or {};quality_value=quality.get('quality')
    if not isinstance(quality_value,dict):return _unknown('STRUCTURE_QUALITY_REVIEW_REQUIRED')
    if quality_value.get('confidence')=='low' or quality.get('s11_quality_condition') is False:
        return _unknown('STRUCTURE_QUALITY_LOW')
    if quality.get('s11_quality_condition') is not True:return _unknown('STRUCTURE_QUALITY_REVIEW_REQUIRED')
    mapping=report.get('mapping')
    if not isinstance(mapping,dict) or mapping.get('target_chain_id') is None:
        return _unknown('STRUCTURE_MAPPING_NOT_UNIQUE')
    rsa=report.get('rsa')
    if not isinstance(rsa,dict):return _unknown('RSA_NOT_AVAILABLE')
    if rsa.get('out_of_domain') or rsa.get('status')!='computed_unverified' or rsa.get('development_result') is None:
        return _unknown(rsa.get('error_code') or 'RSA_NOT_RELIABLE')
    values=rsa['development_result'].get('per_residue')
    ensure(isinstance(values,list) and len(values)==len(mapping.get('sequence','')) and values,
        'OUTPUT_INVALID','RSA/mapping length differs for S-39')
    width=min(10,len(values));n_values=values[:width];c_values=values[-width:]
    if any(type(x) not in (int,float) or not math.isfinite(x) for x in n_values+c_values):
        return _unknown('TERMINAL_RSA_INCOMPLETE')
    n=math.fsum(n_values)/width;c=math.fsum(c_values)/width
    warnings=[]
    for name,value in (('N_TERM',n),('C_TERM',c)):
        if value<.40:warnings.append(name+'_'+('PARTIAL' if value>=.20 else 'BURIED'))
    if n<.20 and c<.20:warnings.append('BOTH_TERMINI_BURIED_CONSIDER_INTERNAL_LOOP_OR_TAGLESS_PURIFICATION')
    signed=structure.get('scientific_signoff') is not None and rsa.get('scientific_signoff') is not None
    if not signed:warnings.append('RSA_SCIENTIFIC_SIGNOFF_MISSING')
    return dict(status='computed' if signed else 'computed_unreviewed',reliable=signed,
        reason_code=None if signed else 'RSA_SCIENTIFIC_SIGNOFF_MISSING',
        n_term=dict(mean_rsa=n,classification=_classification(n)),c_term=dict(mean_rsa=c,classification=_classification(c)),
        preferred_end='N-term' if n>c else 'C-term' if c>n else 'neither',tool='C34(FreeSASA)',warnings=warnings,
        source_qualification=structure.get('qualification'),terminal_width=width,coordinate_space='mature_1_based')


def _dimension(status,reliable,value,normalized,reason,source):
    return dict(status=status,reliable=reliable,value=value,normalized_score=normalized,
        exclusion_reason=reason,source=source,included_in_overall=False)


def summarize(body,expr,tag,ph,aggregation=None):
    aggregation=aggregation or dict(status='unavailable',reliable=False,reason_code='AGGRESCAN3D_NOT_RUN',global_score=None)
    dimensions={
        'solubility':_dimension('unavailable',False,None,None,'OI_025_CAMSOL_PARAMETERS_INCOMPLETE','C44 CamSol-reimpl'),
        'aggregation':_dimension(aggregation['status'],aggregation['reliable'],
            aggregation if aggregation.get('global_score') is not None else None,
            None if not aggregation['reliable'] else 1.0-min(1.0,max(0.0,(aggregation['global_score']+10.0)/20.0)),
            None if aggregation['reliable'] else aggregation['reason_code'],'C45 AGGRESCAN3D/AGGRESCAN'),
        'ph_stability':_dimension(ph['status'],ph['reliable'],ph if ph['dg_curve'] is not None else None,
            None if not ph['reliable'] else min(1.0,max(0.0,(ph['stable_range'][1]-ph['stable_range'][0])/8.0)),
            None if ph['reliable'] else ph['reason_code'],'C24 PROPKA 3.5.1'),
        'tag_exposure':_dimension(tag['status'],tag['reliable'],tag if tag['n_term'] is not None else None,None if not tag['reliable'] else max(
            tag['n_term']['mean_rsa'],tag['c_term']['mean_rsa'])/.6,None if tag['reliable'] else tag['reason_code'],'S-39'),
        'expressibility':_dimension(expr['status'],True,expr,expr['score'],None,'S-36a / C1 ProtParam'),
        'stability_ddg':_dimension('not_computed',False,None,None,'STABILITY_DDG_NOT_COMPUTED','S-31/FoldX future backfill')}
    if dimensions['tag_exposure']['normalized_score'] is not None:
        dimensions['tag_exposure']['normalized_score']=min(1.0,max(0.0,dimensions['tag_exposure']['normalized_score']))
    available=[name for name,row in dimensions.items() if row['value'] is not None]
    usable=[name for name,row in dimensions.items() if row['reliable'] and row['normalized_score'] is not None]
    missing=[name for name in DIMENSIONS if name not in available]
    exclusions={name:row['exclusion_reason'] for name,row in dimensions.items() if not row['reliable']}
    overall=None;classification=None;overall_status='incomplete_required_solubility'
    weights=body['dimension_weights']
    if dimensions['solubility']['reliable']:
        if weights is None:overall_status='review_required_weights_not_provided'
        else:
            selected=[name for name in usable if weights[name]>0]
            total=sum(weights[name] for name in selected)
            if selected and total>0:
                overall=sum(dimensions[name]['normalized_score']*weights[name] for name in selected)/total
                for name in selected:dimensions[name]['included_in_overall']=True
                classification='excellent' if overall>=.75 else 'good' if overall>=.50 else 'moderate' if overall>=.30 else 'poor'
                overall_status='computed_unreviewed'
            else:overall_status='review_required_no_reliable_weighted_dimension'
    risk_flags=[f'{name}: {reason}' for name,reason in exclusions.items()]
    mitigations=[f'{name}: complete or scientifically sign off the excluded dimension before relying on the overall assessment'
        for name in exclusions]
    return dict(dimensions=dimensions,dev_dims_available=len(available),dev_dims_reliable=len(usable),dimensions_total=6,
        missing_dimensions=missing,excluded_dimensions=exclusions,overall_score=overall,classification=classification,
        overall_status=overall_status,stability_ddg=None,risk_flags=risk_flags,mitigation_suggestions=mitigations,
        dimension_weights=weights,n10_complete=False,design_gate='NOT_EVALUATED',automatic_design_release=False)


def compute(body,structure=None,propka_raw=None,propka_execution=None,a3d_csv=None,a3d_stats=None,a3d_pdb=None,a3d_execution=None):
    expr=expressibility(body['protein_sequence']);tag=tag_exposure(structure)
    ph=assess_propka(propka_raw,body,structure or {},propka_execution or dict(status='not_run',reason_code='STRUCTURE_NOT_AVAILABLE'))
    aggregation=assess_a3d(a3d_csv,a3d_stats,a3d_pdb,body,structure or {},
        a3d_execution or dict(status='not_run',reason_code='STRUCTURE_NOT_AVAILABLE_SEQUENCE_AGGRESCAN_ASSET_NOT_REGISTERED'))
    completed=['S-36a','S-39','S-38-development','S-40-partial']
    pending=['S-36','S-37-sequence','S-38-GUI-benchmark']
    if aggregation['status']=='computed_unreviewed':
        completed.insert(1,'S-37-structure-development');pending.insert(2,'S-37-spatial-signoff')
    else:pending.insert(1,'S-37-structure-development')
    return dict(expressibility=expr,aggregation=aggregation,tag_exposure=tag,ph_stability=ph,
        developability=summarize(body,expr,tag,ph,aggregation),completed_steps=completed,pending_steps=pending,
        n10_status='PARTIAL_DEVELOPMENT_UNREVIEWED')
