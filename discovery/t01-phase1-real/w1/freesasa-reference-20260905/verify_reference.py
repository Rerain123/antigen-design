"""Read-only numerical evidence verification. A numerical check never grants scientific approval."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]
PROFILE='docs/project/phase1/PHASE1_REAL_W1_FREESASA_PROFILE.json'
PROPOSAL='docs/project/phase1/PHASE1_REAL_W1_S09_DECISION_PROPOSAL.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'),parse_constant=lambda value: (_ for _ in ()).throw(ValueError(f'Nonfinite JSON: {value}')))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def address(row):
    return row['chain'], row['residue_number'], row['residue_name']


def compare_runs(left, right, maxima):
    require(len(left['residues'])==len(right['residues']), 'Residue count mismatch')
    areas=[]; ratios=[]; flips=[]
    for a,b in zip(left['residues'],right['residues']):
        require(address(a)==address(b), 'Residue address mismatch')
        x=a['absolute_sasa_a2']/maxima[a['residue_name']]
        y=b['absolute_sasa_a2']/maxima[b['residue_name']]
        areas.append(abs(a['absolute_sasa_a2']-b['absolute_sasa_a2'])); ratios.append(abs(x-y))
        if (x<.2)!=(y<.2): flips.append(a['residue_number'])
    return {'total_delta_a2':left['total_sasa_a2']-right['total_sasa_a2'],
            'total_relative_error':abs(left['total_sasa_a2']-right['total_sasa_a2'])/right['total_sasa_a2'],
            'max_abs_residue_sasa_delta_a2':max(areas),'max_abs_rsa_delta':max(ratios),
            'buried_classification_differences':flips}


def assess():
    spec=read(BATCH/'reference_spec.json'); profile=read(ROOT/PROFILE); proposal=read(ROOT/PROPOSAL)
    targets=spec['screening_targets']; maxima=spec['tien_theoretical_by_three_letter']
    initial=BATCH/'run/result'; follow=BATCH/'refinement/result'
    geometries=read(initial/'shared_geometry.json')
    require(len(geometries)==602, 'Expected 602 selected atoms')
    require(len({(address(a),a['atom_name']) for a in geometries})==602, 'Duplicate atom addresses')
    for atom in geometries:
        require(math.isfinite(atom['radius']) and atom['radius']>0,'Invalid radius')
        require(all(math.isfinite(v) for v in atom['coordinate']),'Invalid coordinate')
    require(profile['scientific_approval'] is None and not profile['production_approved'],'Cannot infer scientific approval from numerical evidence')
    require(proposal['scientific_approval'] is None and not proposal['production_approved'],'S-09 proposal is not an approval')
    require(len(maxima)==len(profile['normalization']['max_asa_a2'])==20,'Incomplete Tien table')
    authority=(ROOT/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/ToolSpec_C34_FreeSASA_v10.5.md').read_text(encoding='utf-8')
    source_table={letter:float(area) for letter,area in re.findall(r'^\| [A-Za-z]+ \| ([A-Z]) \| ([0-9.]+) \|',authority,re.M)}
    require(source_table==profile['normalization']['max_asa_a2'],'Full Tien table differs from expert original')
    source=read(BATCH/'inputs/SOURCE_MANIFEST.json')
    require((ROOT/source['copied_from']).read_bytes()==(BATCH/'inputs/1UBQ.pdb').read_bytes(),'Input copy differs from prior evidence')
    # Literal authority values plus complete three-letter/one-letter crosswalk.
    crosswalk=dict(zip('ALA ARG ASN ASP CYS GLU GLN GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL'.split(),'ARNDCEQGHILKMFPSTWYV'))
    require(all(maxima[k]==profile['normalization']['max_asa_a2'][v] for k,v in crosswalk.items()),'Tien table drift')
    require((maxima['ALA'],maxima['ARG'],maxima['GLY'])==(129,274,104),'Locked A/R/G references changed')
    for key in ['total_relative_error_max','per_residue_absolute_rsa_error_max','reference_convergence_max_absolute_rsa_delta']:
        require(targets[key]==profile['numerical_acceptance_proposal'][key],'Predeclared target changed')
    runs={}
    for path in sorted(initial.glob('FreeSASA-LR-*.json'))+sorted(initial.glob('Biopython-SR-*.json'))+list(follow.glob('Biopython-SR-*.json')):
        run=read(path); runs[run['id']]=run
        require(len(run['atoms_sasa_a2'])==602 and len(run['residues'])==76,'Incomplete numerical run')
        require(len({address(r) for r in run['residues']})==76,'Duplicate residue addresses')
        require(all(math.isfinite(v) and v>=0 for v in run['atoms_sasa_a2']),'Invalid atom area')
        require(math.isclose(sum(run['atoms_sasa_a2']),run['total_sasa_a2'],rel_tol=0,abs_tol=1e-8),'Atom sum mismatch')
        require(math.isclose(sum(r['absolute_sasa_a2'] for r in run['residues']),run['total_sasa_a2'],rel_tol=0,abs_tol=1e-8),'Residue sum mismatch')
        require(run['parameters']['probe-radius']==1.4,'Probe radius changed')
    require(len(runs)==8,'Missing parameter sweep or reference refinement')
    selected=runs['FreeSASA-LR-200']; reference=runs['Biopython-SR-61440']
    require(profile['calculation']['parameters']==selected['parameters'],'Candidate differs from tested parameters')
    # Published values are an independent external source, but the same algorithm at 20 slices.
    published=spec['sources']['published_freesasa']; baseline=runs['FreeSASA-LR-20']
    rounding=.5*10**(-published['display_decimals'])
    require(abs(baseline['total_sasa_a2']-published['total_sasa_a2'])<=rounding,'Published total regression differs')
    require(abs(baseline['residues'][0]['absolute_sasa_a2']-published['met1_total_sasa_a2'])<=rounding,'Published MET1 regression differs')
    for folder in ['run','refinement']:
        execution=read(BATCH/folder/'execution.json'); calculation=read(BATCH/folder/'result/comparison.json')
        require(execution['exit_code']==0 and not execution['timed_out'],'Numerical execution failed')
        require(execution['image_id']==profile['runtime']['image_id'],'Image mismatch')
        require(calculation['network_interfaces']==['lo'],'Unexpected runtime network')
        command=execution['command']; require(command[command.index('--network')+1]=='none','Network not disabled')
        for comparison in calculation['comparisons']:
            actual=compare_runs(runs[comparison['left']],runs[comparison['right']],maxima)
            for key,value in actual.items():
                require(value==comparison[key],f'Saved comparison differs: {key}')
    analytic=read(initial/'comparison.json')['analytic_cases']
    require(len(analytic)==4,'Missing analytic cases')
    for case in analytic:
        for field in ['freesasa_lr200_a2','biopython_sr15360_a2']:
            for expected,actual in zip(case['expected_analytic_a2'],case[field]):
                require(abs(actual-expected)<=max(1e-9,abs(expected)*.001),'Analytic geometry regression failed')
    require(math.isclose(analytic[0]['expected_analytic_a2'][0],4*math.pi*2.9**2,abs_tol=1e-10),'Analytic isolated sphere reference invalid')
    convergence=compare_runs(runs['Biopython-SR-15360'],reference,maxima)
    require(convergence['max_abs_rsa_delta']<=targets['reference_convergence_max_absolute_rsa_delta'],'Independent reference not converged')
    selected_comparison=compare_runs(selected,reference,maxima)
    require(selected_comparison['total_relative_error']<=targets['total_relative_error_max'],'Total error budget failed')
    require(selected_comparison['max_abs_rsa_delta']<=targets['per_residue_absolute_rsa_error_max'],'Residue error budget failed')
    require(not selected_comparison['buried_classification_differences'],'Burial classification changed')
    out_of_domain=[]
    for a,b in zip(selected['residues'],reference['residues']):
        x=a['absolute_sasa_a2']/maxima[a['residue_name']]; y=b['absolute_sasa_a2']/maxima[b['residue_name']]
        if not 0<=x<=1 or not 0<=y<=1:
            out_of_domain.append({'chain':a['chain'],'residue_number':a['residue_number'],'residue_name':a['residue_name'],
                                  'selected_absolute_sasa_a2':a['absolute_sasa_a2'],'reference_absolute_sasa_a2':b['absolute_sasa_a2'],
                                  'selected_raw_ratio':x,'reference_raw_ratio':y,'normalization_denominator_a2':maxima[a['residue_name']]})
    require(len(out_of_domain)==1 and out_of_domain[0]['residue_number']=='76','Observed out-of-domain case must be preserved')
    # Downstream comparisons are diagnostic because G76 violates the accepted RSA domain.
    terminal=[]
    for name,positions in [('N',slice(0,10)),('C',slice(-10,None))]:
        means=[sum(r['absolute_sasa_a2']/maxima[r['residue_name']] for r in run['residues'][positions])/10 for run in [selected,reference]]
        classes=['buried' if v<.2 else 'partial' if v<.4 else 'exposed' for v in means]
        require(classes[0]==classes[1],'S-39 diagnostic classification differs')
        terminal.append({'terminus':name,'selected_raw_mean':means[0],'reference_raw_mean':means[1],
                         'diagnostic_classification':classes[0],'is_valid_s39_result':False})
    catalog=read(ROOT/proposal['source_catalog']['path'])
    pending={c['case_id']:c for c in catalog['cases'] if c['kind']=='DECISION_REQUIRED'}
    require(set(pending)=={d['case_id'] for d in proposal['decisions']} and len(proposal['decisions'])==6,'S-09 coverage mismatch')
    for decision in proposal['decisions']:
        require(decision['input']==pending[decision['case_id']]['input'],'S-09 input changed')
        require(decision['decided_by'] is None and decision['decided_at'] is None and decision['execution_status']=='NOT_RUN','Fabricated S-09 decision or execution')
        if decision['case_id'].startswith('S09-D03'):
            require(decision['proposed_expected']['quality_result'] is None and decision['proposed_expected']['requires_review'] and decision['proposed_expected']['unreliable'],'Uncovered branch gained invented confidence')
    return {'scope':'READ_ONLY_ENGINEERING_EVIDENCE_CHECK','numeric_delta_checks':'PASS','reference_convergence':'PASS',
            'analytic_geometry_cases':4,'published_reference_rounding_abs_a2':rounding,
            'selected_parameters':selected['parameters'],'selected_total_sasa_a2':selected['total_sasa_a2'],
            'independent_reference_total_sasa_a2':reference['total_sasa_a2'],'selected_vs_reference':selected_comparison,
            'independent_reference_convergence':convergence,'out_of_domain':out_of_domain,'terminal_diagnostics':terminal,
            'accepted_project_rsa':False,'mapping_status':'unverified','scientific_acceptance':'NOT_APPROVED',
            's09_decision_status':'AWAITING_NAMED_DECISION','production_status':'NOT_DEPLOYED'}


def verify():
    manifest=read(BATCH/'manifest.json')
    for entry in manifest['files']:
        path=(ROOT/entry['path']).resolve()
        require(path.is_relative_to(ROOT),'Manifest path escaped project')
        data=path.read_bytes()
        require(len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256'],f'Fingerprint mismatch: {entry["path"]}')
    for path,sha in manifest['expert_originals_before'].items():
        require(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha,f'Expert source modified: {path}')
    result=assess()
    require(result==read(BATCH/'assessment.json'),'Assessment drift')
    return {'status':'PASS','files_checked':len(manifest['files']),'expert_originals_checked':len(manifest['expert_originals_before']),**result}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-assessment',action='store_true')
    args=parser.parse_args()
    if args.write_assessment:
        result=assess()
        with (BATCH/'assessment.json').open('x',encoding='utf-8') as stream:
            stream.write(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    else:
        result=verify()
    print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False))
