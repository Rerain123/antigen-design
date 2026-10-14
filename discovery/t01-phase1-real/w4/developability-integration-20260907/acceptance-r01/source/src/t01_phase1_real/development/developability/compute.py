"""S-36a, S-39 and guarded S-40 partial aggregation."""
import math

import Bio
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from ...common import ensure
from .policy import DIMENSIONS


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


def summarize(body,expr,tag):
    dimensions={
        'solubility':_dimension('unavailable',False,None,None,'OI_025_CAMSOL_PARAMETERS_INCOMPLETE','C44 CamSol-reimpl'),
        'aggregation':_dimension('unavailable',False,None,None,'AGGREGATION_ASSET_NOT_REGISTERED','C45 AGGRESCAN3D/AGGRESCAN'),
        'ph_stability':_dimension('unavailable',False,None,None,'PROPKA_ASSET_NOT_REGISTERED','C24 PROPKA'),
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


def compute(body,structure=None):
    expr=expressibility(body['protein_sequence']);tag=tag_exposure(structure)
    return dict(expressibility=expr,tag_exposure=tag,developability=summarize(body,expr,tag),
        completed_steps=['S-36a','S-39','S-40-partial'],pending_steps=['S-36','S-37','S-38'],
        n10_status='PARTIAL_DEVELOPMENT_UNREVIEWED')
