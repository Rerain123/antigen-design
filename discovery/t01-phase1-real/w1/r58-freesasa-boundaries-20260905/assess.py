"""Check independent case identities and metamorphic raw-output relations; no scientific release."""
import json
from pathlib import Path
import sys

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]
sys.path.insert(0,str(ROOT/'src'))
from t01_structure_mapping.probe import parse_local, propose, read_sequence
from t01_structure_mapping.sasa_probe import align_absolute_sasa


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def require(value,message):
    if not value:raise ValueError(message)


def assess():
    specs=read(BATCH/'prepared/case_spec.json')
    prepared={r['id']:r for r in read(BATCH/'prepared/preparation_results.json')}
    campaign=read(BATCH/'raw-run/result/campaign.json')
    runs={r['id']:r for r in campaign['results']}
    execution=read(BATCH/'raw-run/execution.json')
    require(execution['exit_code']==0 and not execution['timed_out'],'Worker failed/timed out')
    require(campaign['network_interfaces']==['lo'],'Runtime was not offline')
    require(execution['command'][execution['command'].index('--network')+1]=='none','Network flag missing')
    for case in specs:
        recorded=prepared[case['id']]
        require(recorded['mapping_status']==case['mapping_expected'],'Unexpected mapping: '+case['id'])
        require(recorded.get('missing_positions',[])==case['missing_positions_expected'],'Unexpected null mask')
        if case['schedule_raw']:
            require(runs[case['id']]['status']==case['raw_expected'],'Unexpected raw outcome: '+case['id'])
        else:require(case['id'] not in runs,'Unscheduled calculation')
        if case['mapping_expected']=='PARSE_REJECTED':continue
        inputs=BATCH/'prepared/inputs'/case['id']
        mapping=read(inputs/'mapping.json')
        fresh=propose(read_sequence(inputs/'input.fasta'),parse_local(inputs/'input.cif'),evidence_kind=case['evidence_kind'])
        require(mapping==fresh,'Saved mapping differs from current explicit input facts')
        require(mapping['review_required'] and not mapping['usable_for_pipeline'],'Unapproved mapping was promoted')
        if case['schedule_raw'] and runs[case['id']]['status']=='SUCCESS':
            raw=read(BATCH/'raw-run/result'/case['id']/'raw.json')
            aligned=read(BATCH/'raw-run/result'/case['id']/'aligned_diagnostic.json')
            recomputed=align_absolute_sasa(mapping,raw['residues'])
            require(all(aligned[k]==v for k,v in recomputed.items()),'Address join mismatch')
            require(aligned['normal_rsa_result'] is None and aligned['buried_fraction'] is None and not aligned['usable_for_pipeline'],'Diagnostic turned into scientific output')
            require(abs(sum(raw['atom_areas_a2'])-raw['total_sasa_a2'])<1e-8,'Atom areas do not sum to total')
            require(abs(sum(r['absolute_sasa_a2'] for r in raw['residues'])-raw['total_sasa_a2'])<1e-8,'Residue areas do not sum to total')
    original=read(BATCH/'raw-run/result/original/aligned_diagnostic.json')
    renumbered={}
    for name in ['insertion-42A','negative-author']:
        changed=read(BATCH/'raw-run/result'/name/'aligned_diagnostic.json')
        require(changed['aligned_absolute_sasa_a2']==original['aligned_absolute_sasa_a2'],'Pure renumbering changed position-aligned SASA')
        renumbered[name]='EXACT_POSITION_ARRAY_EQUALITY'
    missing=read(BATCH/'raw-run/result/missing-repeat-75/aligned_diagnostic.json')['aligned_absolute_sasa_a2']
    require(len(missing)==76 and missing[74] is None and missing[75] is not None and sum(v is None for v in missing)==1,'Partial positions shifted or invented')
    multi=read(BATCH/'raw-run/result/multichain-unique/aligned_diagnostic.json')['aligned_absolute_sasa_a2']
    delta=[a-b for a,b in zip(multi,original['aligned_absolute_sasa_a2'])]
    require(max(delta)<=0 and min(delta)<0,'Declared occluding chain did not produce expected occlusion relation')
    require(runs['multichain-ambiguous']['alignment_status']=='NO_UNIQUE_MAPPING','Ambiguous design chain auto-selected')
    require('FREE_RESIDUE_TOKEN_COLLISION' in runs['numeric-icode-collision']['error'],'Missing numeric insertion-code collision guard')
    require('UNKNOWN_PROTOR_RADIUS' in runs['unknown-atom']['error'],'Missing unknown radius guard')
    classifier=read(BATCH/'raw-run/result/unknown-atom/classifier.json')
    require(any(a['atom_name']=='ZZZ' and a['protor_radius']<=0 for a in classifier),'No original classifier rejection value')
    require(original['out_of_domain_positions']==[76],'G76 out-of-domain finding was lost')
    return {'status':'PASS','scope':'DEVELOPMENT_FORMAT_MAPPING_AND_RAW_TOOL_RELATIONS',
            'declared_cases':len(specs),'actual_calculations':sum(r['status']=='SUCCESS' for r in runs.values()),
            'tool_boundary_rejections':sum(r['status']=='REJECTED' for r in runs.values()),
            'renumbering':renumbered,'missing_input_positions':[75],
            'multichain_affected_target_residues':sum(d<0 for d in delta),
            'original_target_area_a2':sum(original['aligned_absolute_sasa_a2']),
            'synthetic_context_target_area_a2':sum(multi),
            'scientific_acceptance':'NOT_RUN','production_status':'NOT_DEPLOYED',
            'limitations':['Synthetic derivatives are not independent biological hold-out samples.',
                           'No new numerical error tolerance or scientific mapping approval.',
                           'Noninteger author IDs, general substitutions/insertions, altloc selection and complete atom templates still need dedicated treatment.']}


if __name__=='__main__':
    result=assess();target=BATCH/'assessment.json'
    if target.exists():raise SystemExit('Use read-only verifier after recording assessment')
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
