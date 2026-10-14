"""Fixed local structure chain inside the pinned offline FreeSASA/Biopython image."""
from importlib.metadata import version
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import socket
import sys
import traceback

sys.path.insert(0,'/code')
from t01_structure_mapping.input_facts import inspect_input
from t01_structure_mapping.probe import parse_local, propose, ProbeError
from t01_structure_mapping.freesasa_consumer import prepare, validate_tool_atoms, join_areas, ConsumerError
from quality import assess, warning
from normalization import normalize

OUT=Path('/out/result')
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def write(name,value):
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')
    with (OUT/name).open('xb') as stream:stream.write(raw)
    return sha(raw)


def calculate(prepared,profile):
    import freesasa
    config=profile['calculation']
    classifier=freesasa.Classifier.getStandardClassifier(config['classifier'])
    radii=[dict(raw_row_index=a['raw_row_index'],radius=classifier.radius(a['residue_name'],a['atom_name'])) for a in prepared['atoms']]
    write('classifier.json',radii)
    if any(not math.isfinite(r['radius']) or r['radius']<=0 for r in radii):raise ConsumerError('UNKNOWN_PROTOR_RADIUS','不猜测未知原子的半径')
    structure=freesasa.Structure(classifier=classifier,options=config['structure_options'])
    for atom in prepared['atoms']:
        structure.addAtom(atom['tool_atom_name'],atom['residue_name'],atom['tool_residue_token'],atom['chain_id'],*atom['coordinate_tool'])
    observed=[dict(tool_atom_index=i,chain_id=structure.chainLabel(i),tool_residue_token=structure.residueNumber(i).strip(),
        raw_tool_residue_number=structure.residueNumber(i),residue_name=structure.residueName(i).strip(),atom_name=structure.atomName(i).strip(),
        raw_tool_atom_name=structure.atomName(i),coordinate=list(structure.coord(i)),radius=structure.radius(i)) for i in range(structure.nAtoms())]
    write('tool_atoms.json',observed)
    verified=validate_tool_atoms(prepared,observed)
    expected={r['raw_row_index']:r['radius'] for r in radii}
    if any(r['radius']!=expected[r['raw_row_index']] for r in verified):raise ConsumerError('TOOL_RADIUS_MISMATCH','实际半径与 ProtOr 分类不同')
    write('verified_atoms.json',verified)
    write('calculation-started.json',dict(route='native_atoms',atom_count=structure.nAtoms()))
    result=freesasa.calc(structure,freesasa.Parameters(config['parameters']))
    areas=[dict(tool_atom_index=i,absolute_sasa_a2=result.atomArea(i)) for i in range(result.nAtoms())]
    total=result.totalArea();summed=math.fsum(r['absolute_sasa_a2'] for r in areas)
    if any(not math.isfinite(r['absolute_sasa_a2']) or r['absolute_sasa_a2']<0 for r in areas) or not math.isfinite(total):
        (OUT/'nonfinite_numeric.txt').write_text(repr((total,areas)))
        raise ConsumerError('INVALID_NUMERIC_OUTPUT','非有限原始面积，不用于归一化')
    write('raw_areas.json',dict(total_sasa_a2=total,atom_areas=areas,parameters=config['parameters']))
    if total<0 or abs(total-summed)>math.ulp(max(total,summed))*max(1,len(areas)):raise ConsumerError('TOTAL_AREA_MISMATCH','总面积与逐原子面积之和不一致')
    joined=join_areas(prepared,observed,areas)
    write('raw_residue_areas.json',joined)
    return dict(status='executed',calculation_started=True,atom_count=len(areas),residue_count=len(joined['residues']),
        total_sasa_a2=total,route='native_atoms',raw_residues=joined['residues'],error_code=None)


def run(request,binding,profile):
    data=Path('/input.structure').read_bytes();sequence=request['protein_sequence']
    if sha(data)!=binding['structure_sha256'] or sha(sequence.encode())!=binding['sequence_sha256'] or sha(Path('/input.json').read_bytes())!=binding['input_sha256']:
        raise ValueError('Input does not match durable task binding')
    facts=inspect_input(data,declared_format=request['declared_format'],**request['selection'])
    for name,fact in facts.items():write(name+'.json',dict(fact,binding=binding))
    pf=facts['preflight']
    report=dict(binding=binding,input=dict(protein_sequence=sequence,host_species=request['host_species'],structure_name=request['structure_name'],
        structure_artifact=request['structure_artifact'],source_declaration=request['source_declaration']),mapping=None,quality=None,
        freesasa=dict(status='blocked',calculation_started=False,error_code=None),rsa=None,
        status='review_required',warnings=[],steps=[],scientific_signoff=None,usable_for_pipeline=False,automatic_handoff=False,
        method_summary=dict(profile_id=profile['profile_id'],profile_version=profile['version'],profile_sha256=sha(Path('/profile.json').read_bytes()),
            runtime=profile['runtime'],calculation=profile['calculation'],normalization=profile['normalization'],
            selected_context_chain_ids=request['context_chain_ids'],source_selection=request['selection'],scientific_approval=None,
            completeness_policy='OI-023: no heavy-atom percentage inferred or side-chain repair',
            sources=read('/worker/sources.json')['files']))
    def step(name,status,reason=None):
        report['steps'].append(dict(step=name,status=status,reason=reason));print(name,status,reason or '',flush=True)
    step('input_facts','executed' if pf['status']=='ready_for_review' else 'rejected',pf['error_code'])
    if pf['status']!='ready_for_review':
        report['status']='input_rejected';report['error_code']=pf['error_code']
        report['warnings'] += [warning(d['code'],d['message']) for d in pf['diagnostics']]
        for name in ['parse_and_mapping','S-09','FreeSASA','RSA']:step(name,'blocked','INPUT_PREFLIGHT_REJECTED')
        return report
    try:
        inventory=parse_local('/input.structure');write('inventory.json',dict(inventory,binding=binding))
        mapping=propose(sequence,inventory,evidence_kind='G0_REAL_OUTPUT',model_index=request['selection']['model_index'],
            requested_chain=None if request['selection']['chain_selector']=='AUTO' else request['selection']['chain_selector'])
        mapping['binding']=binding;report['mapping']=mapping;write('mapping.json',mapping)
        step('parse_and_mapping','executed',mapping['mapping_status'])
        report['warnings'] += [warning(i['code'],i['message']) for i in mapping['issues']]
    except (ProbeError,ValueError,KeyError,TypeError) as exc:
        step('parse_and_mapping','review_required','MAPPING_PARSE_REVIEW')
        report['warnings'].append(warning('MAPPING_PARSE_REVIEW',str(exc)));mapping=None
    quality=assess(request['source_declaration'],facts['raw_metadata'])
    quality['structure'].update(quality['quality'] or dict(confidence=None,topology_reliable=None,low_confidence_regions=None))
    quality['binding']=binding;write('quality.json',quality);report['quality']=quality
    report['warnings'] += quality['warnings'];step('S-09',quality['status'])
    blocked=None
    if quality['s11_quality_condition'] is False:
        report['freesasa']['status']='skipped';blocked='QUALITY_LOW'
    elif quality['s11_quality_condition'] is None:blocked='QUALITY_REVIEW_REQUIRED'
    elif not mapping or mapping['target_chain_id'] is None:blocked='MAPPING_NOT_UNIQUE'
    elif any(i['code']=='BACKBONE_ATOMS_ABSENT' for i in mapping['issues']):blocked='BACKBONE_ATOMS_ABSENT'
    if blocked:
        report['freesasa']['error_code']=blocked;step('FreeSASA',report['freesasa']['status'],blocked);step('RSA','blocked',blocked)
        report['warnings'].append(warning(blocked,'结构依赖计算未执行；请查看质量、候选映射或原子完整性信息'))
        return report
    try:
        prepared=prepare(data,facts,route='native_atoms',model_index=pf['ingestion_observation']['model_index'],context_chain_ids=request['context_chain_ids'])
        prepared.pop('pdb_text');prepared['binding']=binding
        # R-58 joins may use integer keys only after the lossless raw projection agrees.
        unsupported=[r for r in facts['raw_addresses']['residues'] if r['model_index']==mapping['model_index'] and r['residue_class']!='nonprotein'
            and r['address']['auth_asym_id'][0]==mapping['target_chain_id'] and not r['consumers']['integer_mapping_v0_1']['representable']]
        if unsupported:raise ConsumerError('MAPPING_ADDRESS_REVIEW','原始作者编号不能无损投影到现有候选映射键',unsupported)
        write('preparation.json',prepared)
        report['freesasa']=calculate(prepared,profile);step('FreeSASA','executed')
        report['rsa']=normalize(mapping,facts['raw_addresses']['residues'],report['freesasa'].pop('raw_residues'),profile['normalization']['max_asa_a2'])
        write('rsa.json',dict(report['rsa'],binding=binding));step('RSA',report['rsa']['status'],report['rsa']['error_code'])
        if report['rsa']['out_of_domain']:report['warnings'].append(warning('RSA_OUT_OF_DOMAIN','保留原始面积和比值；不截断、不输出正常 RSA；OI-027 需要算法确认'))
        if report['rsa']['missing_positions']:report['warnings'].append(warning('MISSING_STRUCTURE_RESIDUES','缺失输入位置保留 null，buried_fraction 的分母仍为完整序列长度'))
    except ConsumerError as exc:
        report['freesasa'].update(status='review_required',error_code=exc.code,calculation_started=(OUT/'calculation-started.json').is_file())
        write('consumer-diagnostic.json',dict(code=exc.code,message=str(exc),details=exc.details,binding=binding))
        report['warnings'].append(warning(exc.code,str(exc)));step('FreeSASA','review_required',exc.code);step('RSA','blocked',exc.code)
    return report


def main():
    started=dict(python=platform.python_version(),freesasa=version('freesasa'),biopython=version('biopython'),numpy=version('numpy'))
    runtime=dict(packages=started,network_interfaces=socket.if_nameindex(),cpu_affinity=sorted(os.sched_getaffinity(0)),
        source_modules_modified=False,tool='LOCAL_STRUCTURE_ANALYSIS',python_exit_code=None)
    Path('/out/runtime_started.json').write_text(json.dumps(runtime))
    OUT.mkdir(exist_ok=False)
    try:
        profile=read('/profile.json')
        if any(v!=profile['runtime'][k] for k,v in started.items()):raise ValueError('Runtime packages differ from pinned FreeSASA profile')
        report=run(read('/input.json'),read('/binding.json'),profile)
        write('analysis.json',report);runtime['python_exit_code']=0
    except BaseException as exc:
        runtime.update(python_exit_code=1,error_type=type(exc).__name__,error=str(exc))
        (OUT/'exception.txt').write_text(traceback.format_exc())
        raise
    finally:
        runtime['native_output_sha256']={p.relative_to(Path('/out')).as_posix():sha(p.read_bytes()) for p in sorted(OUT.rglob('*')) if p.is_file()}
        Path('/out/runtime.json').write_text(json.dumps(runtime))


if __name__=='__main__':main()
