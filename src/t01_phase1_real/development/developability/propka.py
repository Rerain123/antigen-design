"""Pinned PROPKA execution parsing and C24 relative pH-stability post-processing."""
import io
import math
import re

import propka
from Bio.PDB import PDBParser

from ...common import RuntimeFault, ensure

VERSION=propka.__version__
ACIDIC={'ASP','GLU','C-','CYS','TYR'}
BASIC={'HIS','LYS','ARG','N+'}
GUI_SOURCE_URL='https://github.com/thatchristoph/vmd-cvs-github/blob/master/plugins/propka/propka.tcl'
GUI_GIT_BLOB='c417a01fafd2da93a5abc59f957b22d3ff266dc1'
GUI_SOURCE_SHA256='55cf9b44805e1697f0eb730223e5652f0caf7616af1fe729c3fe04b1d723548b'
GUI_FORMULA_LINES='propka.tcl:3324-3352'
GUI_BENCHMARK_TOLERANCE_KCAL_MOL=0.01
SUMMARY=re.compile(
    r'^\s*(ASP|GLU|C-|CYS|TYR|HIS|LYS|ARG|N\+)\s+(\d+)\s+(\S)\s+'
    r'([-+]?\d+(?:\.\d+)?)\s+([-+]?\d+(?:\.\d+)?)\s*$')


def parameters(ph_range):
    start,end=ph_range
    step=round((end-start)/8.0,1);grid_step=round((end-start)/40.0,1)
    ensure(step>0 and grid_step>0,'INVALID_REQUEST','PROPKA pH parameters must be positive')
    return dict(start=float(start),end=float(end),step=step,grid_step=grid_step,pH_ref=7.0)


def project_preparation_pdb(preparation,chain):
    """Project a verified N02 atom ledger only when every target-chain field round-trips in PDB."""
    ensure(preparation.get('preparation_status')=='READY_FOR_TOOL_PROBE' and preparation.get('structure_sha256'),
        'OUTPUT_INVALID','N02 preparation is not eligible for PROPKA projection')
    atoms=[row for row in preparation.get('atoms',[]) if row.get('chain_id')==chain]
    ensure(atoms and len(atoms)<=99999,'OUTPUT_INVALID','No bounded target-chain atoms for PROPKA projection')
    lines=[];expected={}
    for serial,atom in enumerate(atoms,1):
        author=atom.get('author_seq_id');insertion=atom.get('insertion_code') or ''
        try:number=int(author)
        except (TypeError,ValueError) as exc:raise RuntimeFault('OUTPUT_INVALID','Non-integer residue address cannot project to PDB') from exc
        ensure(str(number)==author and len(f'{number:4d}')==4 and len(insertion)<=1 and
            (not insertion or insertion.isascii() and insertion.isalnum()),'OUTPUT_INVALID','Residue address cannot project losslessly to PDB')
        coords=atom.get('coordinate_tool');occupancy=atom.get('occupancy');bfactor=atom.get('bfactor')
        ensure(isinstance(coords,list) and len(coords)==3 and all(type(value) in (int,float) and math.isfinite(value) for value in coords)
            and type(occupancy) in (int,float) and math.isfinite(occupancy) and type(bfactor) in (int,float) and math.isfinite(bfactor),
            'OUTPUT_INVALID','Invalid N02 coordinate ledger')
        ensure(all(len(f'{value:8.3f}')==8 for value in coords) and len(f'{occupancy:6.2f}')==6 and len(f'{bfactor:6.2f}')==6,
            'OUTPUT_INVALID','N02 coordinates cannot project to PDB fixed columns')
        name=atom.get('atom_name');tool_name=atom.get('tool_atom_name');residue=atom.get('residue_name');element=atom.get('element')
        ensure(isinstance(name,str) and isinstance(tool_name,str) and len(tool_name)==4 and isinstance(residue,str) and len(residue)==3
            and isinstance(element,str) and 1<=len(element)<=2,'OUTPUT_INVALID','N02 atom identity cannot project to PDB')
        line=f"ATOM  {serial:5d} {tool_name} {residue:>3} {chain}{number:4d}{insertion or ' '}   "+\
            ''.join(f'{value:8.3f}' for value in coords)+f"{occupancy:6.2f}{bfactor:6.2f}          {element:>2}  "
        lines.append(line);key=(chain,number,insertion,residue,name)
        ensure(key not in expected,'OUTPUT_INVALID','Duplicate N02 atom identity during PDB projection');expected[key]=atom
    text='\n'.join(lines+['END'])+'\n'
    try:parsed=PDBParser(PERMISSIVE=False,QUIET=True).get_structure('propka-input',io.StringIO(text))
    except Exception as exc:raise RuntimeFault('OUTPUT_INVALID','Projected PROPKA PDB cannot be parsed') from exc
    seen=set()
    for residue in parsed.get_residues():
        for atom in residue.get_unpacked_list():
            key=(residue.parent.id,residue.id[1],residue.id[2].strip(),residue.resname,atom.name)
            ensure(key in expected and key not in seen,'OUTPUT_INVALID','Projected PROPKA PDB changed atom identity')
            target=expected[key]
            ensure(atom.element==target['element'] and [f'{float(value):.3f}' for value in atom.coord]==
                [f'{value:.3f}' for value in target['coordinate_tool']],'OUTPUT_INVALID','Projected PROPKA PDB changed coordinates')
            seen.add(key)
    ensure(len(seen)==len(expected),'OUTPUT_INVALID','Projected PROPKA PDB lost target-chain atoms')
    return text.encode('ascii')


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
    exponent=pka-ph if kind=='acidic' else ph-pka
    if exponent>300:return 0.0
    if exponent<-300:return -1.0 if kind=='acidic' else 1.0
    value=1.0/(1.0+10.0**exponent)
    return -value if kind=='acidic' else value


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
    count=math.floor((end-start)/step+1e-10)
    ensure(0<count<=10000,'INVALID_REQUEST','PROPKA grid size is outside the bounded implementation')
    points=[round(start+i*step,10) for i in range(count+1)]
    if points[-1]<end-1e-9:points.append(float(end))
    else:points[-1]=float(end)
    return points


def relative_curve(groups,ph_range):
    params=parameters(ph_range);ref=params['pH_ref'];grid=params['grid_step']
    points=[]
    for ph in _grid(params['start'],params['end'],grid):
        delta=1.36*integrate(lambda value:charge_difference(value,groups),ref,ph,grid)
        points.append(dict(pH=ph,dG_kcal_mol=delta))
    return points,params


def _log10_one_plus_pow10(value):
    """Stable form of the VMD PROPKA GUI's log10(1 + 10**value)."""
    if value>300:return value
    if value<-300:return 0.0
    return math.log10(1.0+10.0**value)


def gui_relative_curve(groups,ph_range):
    """Independent closed-form transcription of VMD PROPKA GUI propka_calc_delg.

    The GUI returns an unanchored pH-dependent contribution. C24 only permits a
    relative curve, so the GUI expression is translated vertically to zero at
    pH 7.0 before comparison. That translation cannot change curve shape,
    optimum, stable range, or sign of the pH-dependent change.
    """
    params=parameters(ph_range);ref=params['pH_ref']
    def value(ph):
        return 1.36*math.fsum(
            _log10_one_plus_pow10(ph-row['folded_pka'])-
            _log10_one_plus_pow10(ph-row['model_pka']) for row in groups)
    reference=value(ref)
    return [dict(pH=ph,dG_kcal_mol=value(ph)-reference)
        for ph in _grid(params['start'],params['end'],params['grid_step'])]


def gui_benchmark(groups,curve,ph_range):
    reference=gui_relative_curve(groups,ph_range)
    ensure(len(reference)==len(curve) and all(left['pH']==right['pH'] for left,right in zip(curve,reference)),
        'OUTPUT_INVALID','PROPKA GUI benchmark grid mismatch')
    differences=[abs(left['dG_kcal_mol']-right['dG_kcal_mol']) for left,right in zip(curve,reference)]
    maximum=max(differences,default=0.0)
    return dict(status='PASS' if maximum<=GUI_BENCHMARK_TOLERANCE_KCAL_MOL else 'FAIL',
        comparison='C24_TANFORD_TRAPEZOID_VS_VMD_PROPKA_GUI_CLOSED_FORM_RELATIVE_AT_PH7',
        max_abs_difference_kcal_mol=maximum,tolerance_kcal_mol=GUI_BENCHMARK_TOLERANCE_KCAL_MOL,
        point_count=len(curve),reference_curve=reference,
        source=dict(url=GUI_SOURCE_URL,git_blob=GUI_GIT_BLOB,sha256=GUI_SOURCE_SHA256,
            formula_lines=GUI_FORMULA_LINES,license='GPL'))


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
            dg_curve=None,optimal_ph=None,stable_range=None,unstable_at_target=None,benchmark=None,method=None,warnings=[reason])
    groups=parse_pka(raw);curve,params=relative_curve(groups,body['target_ph_range'])
    benchmark=gui_benchmark(groups,curve,body['target_ph_range'])
    values=[row['dG_kcal_mol'] for row in curve];maximum=max(values);minimum=min(values)
    warnings=['RELATIVE_DG_ONLY_NO_ABSOLUTE_CALIBRATION']
    optimal_index=values.index(maximum);optimal=curve[optimal_index]['pH'];reason=None
    if benchmark['status']!='PASS':
        reason='PROPKA_GUI_BENCHMARK_FAILED';warnings.append(reason)
    if maximum-minimum<1.0:
        optimal=None;reason='FLAT_CURVE_WEIGHTING_UNRESOLVED';warnings.append(reason)
    stable=_stable_component(curve,maximum-2.0,optimal_index)
    target_range=body['target_ph_range'];unstable=target_range[0]<stable[0] or target_range[1]>stable[1]
    if unstable:warnings.append('TARGET_PH_RANGE_OUTSIDE_STABLE_RANGE')
    report=source.get('analysis') or {};quality=(report.get('quality') or {}).get('quality') or {}
    if quality.get('confidence')=='low':
        warnings.append('STRUCTURE_QUALITY_LOW');reason=reason or 'STRUCTURE_QUALITY_LOW'
    if (report.get('mapping') or {}).get('mapping_status')!='verified':
        warnings.append('STRUCTURE_MAPPING_SCIENTIFIC_SIGNOFF_MISSING');reason=reason or 'STRUCTURE_MAPPING_SCIENTIFIC_SIGNOFF_MISSING'
    reliable=reason is None
    return dict(status=('unstable' if unstable else 'stable') if reliable else 'unreliable',reliable=reliable,
        reason_code=reason,execution=execution,pka_groups=groups,benchmark=benchmark,
        dg_curve=curve,optimal_ph=optimal,stable_range=stable,unstable_at_target=unstable,
        method=dict(tool='C24(PROPKA)',propka_version=VERSION,postprocess='C24 Tanford Eq.2 trapezoid',
            sign_convention='relative_delta_G_unfolding_positive_is_more_stable',absolute_calibration=False,
            coefficient_kcal_mol=1.36,gui_benchmark='PASS' if benchmark['status']=='PASS' else 'FAIL',**params),
        warnings=list(dict.fromkeys(warnings)))
