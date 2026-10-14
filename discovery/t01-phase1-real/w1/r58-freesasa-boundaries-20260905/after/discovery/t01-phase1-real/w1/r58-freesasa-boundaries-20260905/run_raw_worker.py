"""Actual FreeSASA calls on declared synthetic/development contexts; no production results."""
from collections import defaultdict
from importlib import metadata
import json
import math
import os
from pathlib import Path
import sys
import time

import freesasa

sys.path.insert(0,'/code/src')
from t01_structure_mapping.probe import AA, ProbeError, sha
from t01_structure_mapping.sasa_probe import address, align_absolute_sasa


def read(path):return json.loads(path.read_text())
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run_case(case, profile, output):
    folder=Path('/cases/inputs')/case['id']
    prep=read(folder/'preparation.json');mapping=read(folder/'mapping.json')
    source=folder/'prepared.pdb'
    if sha(source.read_bytes())!=prep['derived_pdb_sha256'] or sha((folder/'input.cif').read_bytes())!=mapping['structure_sha256']:
        raise ProbeError('Input or mapping source binding differs')
    token_addresses={}
    expected={}
    for atom in prep['atoms']:
        token=(atom['chain_id'],str(atom['res_seq'])+atom['insertion_code'])
        if token in token_addresses and token_addresses[token]!=address(atom):
            raise ProbeError('FREE_RESIDUE_TOKEN_COLLISION: distinct resSeq/iCode become the same FreeSASA residue token')
        token_addresses[token]=address(atom)
        key=token+(atom['residue_name'],atom['atom_name'])
        if key in expected:raise ProbeError('Duplicate expected atom key')
        expected[key]=atom
    classifier=freesasa.Classifier.getStandardClassifier(profile['calculation']['classifier'])
    radii=[{'address':list(address(a)),'atom_name':a['atom_name'],
            'protor_radius':classifier.radius(a['residue_name'],a['atom_name'])} for a in prep['atoms']]
    write(output/'classifier.json',radii)
    if any(not math.isfinite(a['protor_radius']) or a['protor_radius']<=0 for a in radii):
        raise ProbeError('UNKNOWN_PROTOR_RADIUS: raw classifier values retained; no radius guessing')
    structure=freesasa.Structure(str(source),classifier=classifier,options=profile['calculation']['structure_options'])
    actual=[]
    for i in range(structure.nAtoms()):
        key=(structure.chainLabel(i),structure.residueNumber(i).strip(),structure.residueName(i).strip(),structure.atomName(i).strip())
        if key not in expected:raise ProbeError('FreeSASA atom identity differs from prepared PDB')
        bound=expected[key]
        coords=list(structure.coord(i))
        if [f'{v:.3f}' for v in coords]!=[f'{v:.3f}' for v in bound['coordinate_pdb']]:
            raise ProbeError('FreeSASA coordinates differ from prepared PDB')
        actual.append({**{k:bound[k] for k in ['chain_id','res_seq','insertion_code','hetero_flag','residue_name','atom_name']},
                       'coordinate':coords,'radius':structure.radius(i),'tool_residue_token':key[1]})
    if len(actual)!=len(expected) or len({address(a)+(a['atom_name'],) for a in actual})!=len(expected):
        raise ProbeError('FreeSASA lost/duplicated atoms')
    write(output/'tool_atoms.json',actual)
    params=profile['calculation']['parameters']
    started=time.perf_counter();calculated=freesasa.calc(structure,freesasa.Parameters(params));elapsed=time.perf_counter()-started
    areas=[calculated.atomArea(i) for i in range(calculated.nAtoms())]
    total=calculated.totalArea()
    if any(not math.isfinite(v) or v<0 for v in areas+[total]):
        (output/'nonfinite_raw.json').write_text(json.dumps({'atoms':areas,'total':total},allow_nan=True))
        raise ProbeError('INVALID_NUMERIC_OUTPUT: nonfinite raw values retained')
    grouped=defaultdict(float)
    for atom,area in zip(actual,areas):grouped[address(atom)]+=area
    fields=['chain_id','res_seq','insertion_code','hetero_flag','residue_name']
    residues=[{**dict(zip(fields,key)),'absolute_sasa_a2':value} for key,value in grouped.items()]
    raw={'freesasa_version':metadata.version('freesasa'),'parameters':params,'atom_areas_a2':areas,
         'residues':residues,'total_sasa_a2':total,'calculation_seconds':elapsed,
         'source_pdb_sha256':sha(source.read_bytes()),'mapping_sha256':sha((folder/'mapping.json').read_bytes())}
    write(output/'raw.json',raw)
    aligned=align_absolute_sasa(mapping,residues)
    if aligned['aligned_absolute_sasa_a2'] is not None:
        ratios=[area/profile['normalization']['max_asa_a2'][letter] if area is not None else None
                for area,letter in zip(aligned['aligned_absolute_sasa_a2'],mapping['sequence'])]
        aligned['raw_ratio_diagnostics']=ratios
        aligned['out_of_domain_positions']=[i for i,v in enumerate(ratios,1) if v is not None and not 0<=v<=1]
    aligned.update(normal_rsa_result=None,buried_fraction=None,scientific_approval=None,
                   production_status='NOT_DEPLOYED',source_mapping_status=mapping['mapping_status'])
    write(output/'aligned_diagnostic.json',aligned)
    return {'atom_count':len(actual),'residue_count':len(residues),'total_sasa_a2':total,
            'alignment_status':aligned['status'],'out_of_domain_positions':aligned.get('out_of_domain_positions',[])}


def main():
    output=Path('/out/result');output.mkdir(exist_ok=False)
    profile=read(Path('/profile.json'))
    if metadata.version('freesasa')!=profile['runtime']['freesasa']:raise RuntimeError('Wrong FreeSASA version')
    cases=read(Path('/cases/case_spec.json'))
    results=[]
    for case in cases:
        if not case['schedule_raw']:continue
        folder=output/case['id'];folder.mkdir()
        record={'id':case['id'],'evidence_kind':case['evidence_kind'],'status':None,'error':None,
                'usable_for_pipeline':False}
        try:
            record.update(run_case(case,profile,folder));record['status']='SUCCESS'
        except Exception as error:
            record.update(status='REJECTED',error=str(error))
        write(folder/'result.json',record);results.append(record)
        print(json.dumps(record),flush=True)
    write(output/'campaign.json',{'scope':'LOCAL_R58_SASA_DEVELOPMENT_BOUNDARIES',
          'network_interfaces':os.listdir('/sys/class/net'),'freesasa_version':metadata.version('freesasa'),
          'profile_sha256':sha(Path('/profile.json').read_bytes()),'results':results,'production_status':'NOT_DEPLOYED'})


if __name__=='__main__':main()
