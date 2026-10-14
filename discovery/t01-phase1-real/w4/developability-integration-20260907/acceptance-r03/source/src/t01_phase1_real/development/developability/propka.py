"""Pinned PROPKA execution parsing and C24 relative pH-stability post-processing."""
import math
import re

import propka

from ...common import RuntimeFault, ensure

VERSION=propka.__version__
ACIDIC={'ASP','GLU','C-','CYS','TYR'}
BASIC={'HIS','LYS','ARG','N+'}
SUMMARY=re.compile(
    r'^\s*(ASP|GLU|C-|CYS|TYR|HIS|LYS|ARG|N\+)\s+(\d+)\s+(\S)\s+'
    r'([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*$')


def parameters(ph_range):
    start,end=ph_range
    step=round((end-start)/8.0,1);grid_step=round((end-start)/40.0,1)
    ensure(step>0 and grid_step>0,'INVALID_REQUEST','PROPKA pH parameters must be positive')
    return dict(start=float(start),end=float(end),step=step,grid_step=grid_step,pH_ref=7.0)


def parse_pka(raw):
    """Parse only the authoritative summary pKa/model-pKa columns, never CLI energy tables."""
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError as exc:raise RuntimeFault('OUTPUT_INVALID','PROPKA .pka is not UTF-8') from exc
    marker='SUMMARY OF THIS PREDICTION'
    ensure(marker in text,'OUTPUT_INVALID','PROPKA summary marker missing')
    section=text.split(marker,1)[1]
    rows=[];seen=set()
    for line in section.splitlines():
        match=SUMMARY.match(line)
        if not match:continue
        group,number,chain,folded,model=match.groups();identity=(group,int(number),chain)
        ensure(identity not in seen,'OUTPUT_INVALID','Duplicate PROPKA titratable group')
        seen.add(identity);folded=float(folded);model=float(model)
        ensure(math.isfinite(folded) and math.isfinite(model),'OUTPUT_INVALID','Non-finite PROPKA pKa')
        rows.append(dict(group=group,residue_number=int(number),chain_id=chain,
            folded_pka=folded,model_pka=model,charge_class='acidic' if group in ACIDIC else 'basic'))
    ensure(rows,'OUTPUT_INVALID','No PROPKA pKa/model-pKa rows found')
    return rows


def _charge(ph,pka,kind):
    if kind=='acidic':return -1.0/(1.0+10.0**(pka-ph))
    return 1.0/(1.0+10.0**(ph-pka))


def charge_difference(ph,groups):
    return math.fsum(_charge(ph,row['model_pka'],row['charge_class'])-
        _charge(ph,row['folded_pka'],row['charge_class']) for row in groups)


def integrate(function,start,end,max_step):
    """Signed trapezoid integration; exposed for the C24 constant-integrand regression."""
    if start==end:return 0.0
    sign=1.0
    if end<start:start,end,sign=end,start,-1.0
    count=max(1,math.ceil((end-start)/max_step));width=(end-start)/count
    total=0.0;left=start;left_value=function(left)
    for index in range(count):
        right=end if index==count-1 else start+(index+1)*width
        right_value=function(right);total+=(left_value+right_value)*(right-left)/2.0
        left=right;left_value=right_value
    return sign*total


def _grid(start,end,step):
    count=round((end-start)/step)
    ensure(count>0 and abs(start+count*step-end)<1e-7,'INVALID_REQUEST','PROPKA grid does not close exactly')
    return [round(start+i*step,10) for i in range(count+1)]


def relative_curve(groups,ph_range):
    params=parameters(ph_range);ref=params['pH_ref'];grid=params['grid_step']
    points=[]
    for ph in _grid(params['start'],params['end'],grid):
        delta=1.36*integrate(lambda value:charge_difference(value,groups),ref,ph,grid)
        points.append(dict(pH=ph,dG_kcal_mol=delta))
    return points,params


def _stable_component(curve,threshold,optimal_index):
    included=[row['dG_kcal_mol']>=threshold-1e-12 for row in curve]
    low=optimal_index;high=optimal_index
    while low>0 and included[low-1]:low-=1
    while high+1<len(curve) and included[high+1]:high+=1
    return [curve[low]['pH'],curve[high]['pH']]


def assess(raw,body,source,execution):
    if raw is None:
        reason=execution.get('reason_code') or 'PROPKA_NOT_RUN'
        return dict(status='unavailable',reliable=False,reason_code=reason,execution=execution,pka_groups=None,
            dg_curve=None,optimal_ph=None,stable_range=None,unstable_at_target=None,method=None,warnings=[reason])
    groups=parse_pka(raw);curve,params=relative_curve(groups,body['target_ph_range'])
    values=[row['dG_kcal_mol'] for row in curve];maximum=max(values);minimum=min(values)
    warnings=['PROPKA_GUI_BENCHMARK_PENDING','RELATIVE_DG_ONLY_NO_ABSOLUTE_CALIBRATION']
    optimal_index=values.index(maximum);optimal=curve[optimal_index]['pH'];reason='PROPKA_GUI_BENCHMARK_PENDING'
    if maximum-minimum<1.0:
        optimal=None;reason='FLAT_CURVE_WEIGHTING_UNRESOLVED';warnings.append(reason)
    stable=_stable_component(curve,maximum-2.0,optimal_index)
    target_range=body['target_ph_range'];unstable=target_range[0]<stable[0] or target_range[1]>stable[1]
    if unstable:warnings.append('TARGET_PH_RANGE_OUTSIDE_STABLE_RANGE')
    report=source.get('analysis') or {};quality=(report.get('quality') or {}).get('quality') or {}
    if quality.get('confidence')=='low':warnings.append('STRUCTURE_QUALITY_LOW')
    if (report.get('mapping') or {}).get('mapping_status')!='verified':warnings.append('STRUCTURE_MAPPING_SCIENTIFIC_SIGNOFF_MISSING')
    return dict(status='unreliable',reliable=False,reason_code=reason,execution=execution,pka_groups=groups,
        dg_curve=curve,optimal_ph=optimal,stable_range=stable,unstable_at_target=unstable,
        method=dict(tool='C24(PROPKA)',propka_version=VERSION,postprocess='C24 Tanford Eq.2 trapezoid',
            sign_convention='relative_delta_G_unfolding_positive_is_more_stable',absolute_calibration=False,
            coefficient_kcal_mol=1.36,**params),warnings=list(dict.fromkeys(warnings)))
