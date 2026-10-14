"""Predeclared local chain cases. Synthetic geometry and real originals are distinct."""
from pathlib import Path
import hashlib
import json

from b1_engineering_cases import cif
from b1_freesasa_cases import alanines

ROOT=Path(__file__).resolve().parents[1]
SEQUENCE='RKDEQLIVF'
UBQ='MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG'
NAMES=dict(zip('RKDEQLIVF',['ARG','LYS','ASP','GLU','GLN','LEU','ILE','VAL','PHE']))


def metadata(sequence=SEQUENCE,fmt='MMCIF',source='experimental',context=None,**changes):
    value=dict(protein_sequence=sequence,host_species='Escherichia coli',structure_name='local-input',declared_format=fmt,
        source_declaration=dict(kind=source,note='CONTROLLED_ENGINEERING_FIXTURE; minimal standard backbone/CB geometry, not a scientific reference'),
        selection=dict(model_index=0,chain_selector='AUTO'),context_chain_ids=context or ['A'],timeout_seconds=60)
    value.update(changes);return value


def geometry():
    rows=alanines([str(42+i) for i in range(len(SEQUENCE))])
    for row in rows:
        aa=SEQUENCE[int(row['label_seq_id'])-1]
        row.update(label_comp_id=NAMES[aa],auth_comp_id=NAMES[aa])
    return rows


def cases():
    rows=geometry();meta="_exptl.method 'X-RAY DIFFRACTION'\n_refine.ls_d_res_high 2.0\n"
    result=[]
    def add(name,data,body,**expected):
        result.append(dict(name=name,data=data,request=body,expected=expected))
    add('normal-cif',cif(rows,metadata=meta),metadata(),sasa='executed',rsa='computed_unverified')
    pdb=['EXPDTA    X-RAY DIFFRACTION','REMARK   2 RESOLUTION.    2.00 ANGSTROMS.']
    for i,r in enumerate(rows,1):
        atom=r['label_atom_id'];pdb.append(f"ATOM  {i:5d} {(' '+atom).ljust(4)} {r['label_comp_id']:>3} A{int(r['auth_seq_id']):4d}    "
            +''.join(f'{float(r[k]):8.3f}' for k in ['Cartn_x','Cartn_y','Cartn_z'])+f"{1.:6.2f}{10.:6.2f}          {r['type_symbol']:>2}  ")
    pdb_data=('\n'.join(pdb+['END'])+'\n').encode()
    add('normal-pdb',pdb_data,metadata(fmt='PDB'),sasa='executed',rsa='computed_unverified')
    partial=[r for r in rows if r['label_seq_id']!='5']
    add('missing-residue',cif(partial,metadata=meta),metadata(),sasa='executed',rsa='computed_unverified',missing=[5])
    other=[dict(r,auth_asym_id='B',label_asym_id='LABEL_B',Cartn_y=str(float(r['Cartn_y'])+30)) for r in rows]
    add('ambiguous-chains',cif(rows+other,metadata=meta),metadata(context=['A','B']),sasa='blocked',reason='MAPPING_NOT_UNIQUE')
    add('quality-low',cif(rows,metadata=meta.replace('2.0','4.0001')),metadata(),sasa='skipped',reason='QUALITY_LOW',confidence='low')
    add('quality-unknown-source',cif(rows,metadata=meta),metadata(source='unknown'),sasa='skipped',reason='QUALITY_LOW',confidence='low')
    add('quality-resolution-null',cif(rows,metadata="_exptl.method 'X-RAY DIFFRACTION'\n"),metadata(),sasa='executed',rsa='computed_unverified',confidence='medium')
    add('quality-nmr-review',cif(rows,metadata="_exptl.method 'SOLUTION NMR'\n_refine.ls_d_res_high 3.0\n"),metadata(),sasa='blocked',reason='QUALITY_REVIEW_REQUIRED')
    add('quality-conflict',cif(rows,metadata=meta+"_em_3d_reconstruction.resolution 5.0\n"),metadata(),sasa='blocked',reason='QUALITY_REVIEW_REQUIRED')
    add('predicted-unverified',cif(rows,metadata=meta),metadata(source='predicted'),sasa='blocked',reason='QUALITY_REVIEW_REQUIRED')
    add('unknown-author-spelling',cif([dict(r,auth_seq_id='042') if r['auth_seq_id']=='42' else r for r in rows],metadata=meta),metadata(),sasa='review_required',reason='MAPPING_ADDRESS_REVIEW')
    add('malformed-input',b'not a structure\n',metadata(),job='failed',reason='INPUT_UNSUPPORTED')
    add('format-mismatch',pdb_data,metadata(),job='failed',reason='FORMAT_MISMATCH')
    original=ROOT/'tests/fixtures/structure_mapping/real/1UBQ.cif'
    body=metadata(sequence=UBQ,source_declaration=dict(kind='experimental',note='UNCHANGED_LOCAL_REAL_INPUT; original 1UBQ.cif'))
    add('original-1ubq-cif',original.read_bytes(),body,sasa='review_required',reason='ICODE_UNKNOWN',reference=original.relative_to(ROOT).as_posix())
    # Coordinate-preserving fixture only. Original occupancy values are never changed in place.
    source=ROOT/'discovery/t01-phase1-real/w1/freesasa-reference-20260905/inputs/1UBQ.pdb'
    lines=['EXPDTA    X-RAY DIFFRACTION','REMARK   2 RESOLUTION.    1.80 ANGSTROMS.'];edits=[]
    for line in source.read_text().splitlines():
        if line.startswith('ATOM'):
            if line[54:60]!='  1.00':edits.append(dict(serial=line[6:11],original_occupancy=line[54:60]))
            lines.append(line[:54]+'  1.00'+line[60:])
        elif line.startswith('HETATM'):lines.append(line)
    derivative=('\n'.join(lines+['END'])+'\n').encode()
    add('rsa-out-of-domain',derivative,metadata(sequence=UBQ,fmt='PDB',source_declaration=dict(kind='experimental',note='CONTROLLED_ENGINEERING_DERIVATIVE: 28 occupancies set to 1, synthetic quality metadata; coordinates unchanged; never scientific reference')),
        sasa='executed',rsa='output_invalid',outlier_position=76,reference=source.relative_to(ROOT).as_posix(),occupancy_changes=edits)
    add('original-1ubq-pdb',source.read_bytes(),metadata(sequence=UBQ,fmt='PDB',source='unknown'),sasa='skipped',reason='QUALITY_LOW',reference=source.relative_to(ROOT).as_posix())
    return result


def write_cases(folder):
    folder.mkdir(parents=True,exist_ok=False);entries=[]
    for case in cases():
        name=case['name'];data=case.pop('data');body=case.pop('request')
        body['structure_name']=name+'.structure'
        (folder/(name+'.structure')).write_bytes(data)
        (folder/(name+'.json')).write_text(json.dumps(body,ensure_ascii=False,sort_keys=True),encoding='utf-8')
        entries.append(dict(case,structure_sha256=hashlib.sha256(data).hexdigest(),request_sha256=hashlib.sha256((folder/(name+'.json')).read_bytes()).hexdigest(),
            reference_kind='UNCHANGED_REAL_LOCAL_INPUT' if name.startswith('original-') else 'CONTROLLED_ENGINEERING_FIXTURE'))
    (folder/'cases.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    return entries


if __name__=='__main__':
    import sys
    write_cases(Path(sys.argv[1]))
