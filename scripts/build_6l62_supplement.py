"""Build an auditable offline 6L62 supplement; never modify an existing database."""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB.MMCIF2Dict import MMCIF2Dict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from t01_phase1_real.development.blast.iedb import AA3,complex_contacts

OUT=ROOT/'reports/iedb-6l62-20261013'
SOURCE=OUT/'source'
NEW_ID='iedb-20261013-6l62-r01'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
encode=lambda v:(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def write_once(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes()!=raw:raise ValueError('Refusing to replace existing asset: '+str(path))
    else:
        with path.open('xb') as f:f.write(raw)

def build():
    downloads=json.loads((SOURCE/'download-receipt.json').read_bytes())
    for row in downloads:
        raw=(SOURCE/row['file']).read_bytes()
        assert sha(raw)==row['sha256'] and len(raw)==row['bytes']
    c=MMCIF2Dict(str(SOURCE/'6L62.cif'))
    metadata=json.loads((SOURCE/'iedb-source-records.json').read_bytes())
    subject=metadata['proteins'][0]['sequence']
    assert metadata['proteins'][0]['subject_id']=='iedb_410863'
    record=next(r for r in metadata['structures'] if r['pdb_id']=='6L62')
    assert (record['ant_pdb_chain'],record['ab_c1_pdb_chain'],record['ab_c2_pdb_chain'])==('A','H','L')
    assert any(r['epitope_id']=='1065884' and r['reference_id']==record['reference_id'] for r in metadata['regions'])
    roles=dict(zip(c['_entity_poly.pdbx_strand_id'],c['_entity_poly.entity_id']))
    assert roles=={'L':'1','H':'2','A':'3'}
    source_seq=c['_entity_poly.pdbx_seq_one_letter_code_can'][2].replace('\n','')
    aligner=PairwiseAligner(scoring='blastp')
    alignments=aligner.align(subject,source_seq)
    assert len(alignments)==1,'Ambiguous sequence alignment'
    alignment=alignments[0]
    corresponding={int(q)+1:int(s)+1 for s,q in zip(*alignment.indices) if s>=0 and q>=0}
    # Resolve author numbering through the official mmCIF scheme, never array offsets.
    scheme={}
    for i,chain in enumerate(c['_pdbx_poly_seq_scheme.pdb_strand_id']):
        if chain!='A':continue
        author=c['_pdbx_poly_seq_scheme.auth_seq_num'][i]
        if author in ('?','.'):continue
        ins=c['_pdbx_poly_seq_scheme.pdb_ins_code'][i]
        key=(int(author),'' if ins in ('.','?') else ins)
        label=int(c['_pdbx_poly_seq_scheme.seq_id'][i])
        assert key not in scheme
        scheme[key]=label
    original=(SOURCE/'6L62.pdb').read_bytes()
    atoms=[l for l in original.decode('ascii').splitlines() if l.startswith('ATOM  ')]
    assert len(atoms)==len(c['_atom_site.id']) and set(l[21] for l in atoms)=={'A','H','L'}
    # Verify all PDB atom identities/coordinates against the independent mmCIF format.
    for i,l in enumerate(atoms):
        assert l[21]==c['_atom_site.auth_asym_id'][i]
        assert int(l[22:26])==int(c['_atom_site.auth_seq_id'][i])
        assert l[17:20].strip()==c['_atom_site.auth_comp_id'][i]
        assert l[12:16].strip()==c['_atom_site.auth_atom_id'][i]
        assert not l[16].strip()
        assert [float(l[n:n+8]) for n in (30,38,46)]==[float(c[k][i]) for k in ('_atom_site.Cartn_x','_atom_site.Cartn_y','_atom_site.Cartn_z')]
    observed={}
    for l in atoms:
        if l[21]=='A':observed[(int(l[22:26]),l[26].strip())]=AA3[l[17:20]]
    mapping=[];excluded=[]
    for (number,ins),aa in observed.items():
        label=scheme[(number,ins)];position=corresponding.get(label)
        assert source_seq[label-1]==aa
        if position is not None and subject[position-1]==aa:
            mapping.append(dict(chain='A',resseq=number,icode=ins,residue=aa,subject_position=position))
        else:excluded.append(dict(author_position=number,label_position=label,source_residue=aa,subject_position=position,subject_residue=subject[position-1] if position else None,reason='NONIDENTICAL_SOURCE_RESIDUE'))
    # Official biological assembly 1: enumerate all 60 deposited transforms.
    assemblies=list(zip(c['_pdbx_struct_assembly_gen.assembly_id'],c['_pdbx_struct_assembly_gen.oper_expression'],c['_pdbx_struct_assembly_gen.asym_id_list']))
    assert ('1','(1-60)','A,B,C') in assemblies
    coords=np.array([[float(l[n:n+8]) for n in (30,38,46)] for l in atoms])
    antigen_mask=np.array([l[21]=='A' and l[76:78].strip() not in ('H','D') for l in atoms])
    antibody_mask=np.array([l[21] in ('H','L') and l[76:78].strip() not in ('H','D') for l in atoms])
    ax=coords[antigen_mask];positions=np.array([int(l[22:26]) for l in atoms])[antigen_mask]
    operators={};contact_ops=[]
    for i,op in enumerate(c['_pdbx_struct_oper_list.id']):
        if not op.isdigit() or not 1<=int(op)<=60:continue
        mat=np.array([[float(c[f'_pdbx_struct_oper_list.matrix[{a}][{b}]'][i]) for b in range(1,4)] for a in range(1,4)])
        tr=np.array([float(c[f'_pdbx_struct_oper_list.vector[{a}]'][i]) for a in range(1,4)])
        assert np.allclose(mat@mat.T,np.eye(3),atol=1e-6) and abs(np.linalg.det(mat)-1)<1e-6
        operators[op]=(mat,tr)
        bx=coords[antibody_mask]@mat.T+tr
        bx=bx[np.all((bx>=ax.min(axis=0)-4)&(bx<=ax.max(axis=0)+4),axis=1)]
        if not len(bx):continue
        dist=np.concatenate([np.sqrt(((a[:,None,:]-bx[None,:,:])**2).sum(axis=2).min(axis=1)) for a in np.array_split(ax,16)])
        ps=sorted(set(map(int,positions[dist<=4])))
        if ps:contact_ops.append(dict(operator=op,contact_author_positions=ps))
    assert len(operators)==60
    # This explicit fragment contains the fixed antigen and only antibody images.
    # Including neighboring antigen copies would mislabel capsid contacts as antibody contacts.
    assert [x['operator'] for x in contact_ops]==['1','10']
    selected={'1':{'H':'H','L':'L'},'10':{'H':'B','L':'C'}}
    lines=['HEADER    DERIVED 6L62 ASSEMBLY 1 ANTIBODY CONTACT NEIGHBORHOOD',
           'REMARK 950 A: ANTIGEN; H/L: FAB OPERATOR 1; B/C: FAB OPERATOR 10',
           'REMARK 950 ORIGINAL PDB/MMCIF AND TRANSFORMS RETAINED IN PROVENANCE']
    for l in atoms:
        if l[21]=='A':lines.append(l)
    max_rounding=0.0
    for op,chain_names in selected.items():
        mat,tr=operators[op]
        for i,l in enumerate(atoms):
            if l[21] not in chain_names:continue
            xyz=coords[i]@mat.T+tr
            text=''.join(f'{v:8.3f}' for v in xyz)
            assert len(text)==24
            max_rounding=max(max_rounding,max(abs(float(text[n:n+8])-xyz[n//8]) for n in (0,8,16)))
            lines.append(l[:21]+chain_names[l[21]]+l[22:30]+text+l[54:])
    # Give derived atoms unique serials, retaining source numbering via explicit chain lineage.
    serial=0
    for i,l in enumerate(lines):
        if l.startswith('ATOM  '):serial+=1;lines[i]=l[:6]+f'{serial:5d}'+l[11:]
    lines.append('END')
    derived=('\n'.join(lines)+'\n').encode('ascii')
    assert max_rounding<=0.00050001
    package=dict(pdb_text=derived.decode('ascii'),coordinate_sha256=sha(derived),residue_map=mapping,source_iedb_id='1065884')
    contacts,notes=complex_contacts(package,record,subject)
    assert not notes,notes
    expected=sorted({p for x in contact_ops for p in x['contact_author_positions']})
    assert sorted(x['resseq'] for x in contacts)==expected,'Projection changed contact classification or lost a source mapping'
    assert len(contacts)==23
    entry=dict(path='complexes/6L62-assembly1-antibody-neighborhood.pdb',subject_id='iedb_410863',complex_id=record['complex_id'],source_iedb_id='1065884',reference_id=record['reference_id'],residue_map=mapping)
    provenance=dict(database_id=NEW_ID,parent_database_id='iedb-20260924-r01',parent_manifest_sha256='96be17e60c108013d320558817037d081edbf8e3c0ed2f9facf83a2d818b6e12',
        source_downloads=downloads,source_records_sha256=sha((SOURCE/'iedb-source-records.json').read_bytes()),
        pdb_doi='10.2210/pdb6L62/pdb',publication_doi='10.1128/JVI.01836-19',pubmed_id='32075932',
        resolution_angstrom=7.2,method='ELECTRON MICROSCOPY',qualification='TARGET_DATABASE_UNREVIEWED',
        coordinate_license='CC0 1.0',license_source='https://www.rcsb.org/pages/policies',
        chain_roles=dict(author=dict(antigen='A',heavy='H',light='L'),label=dict(antigen='C',heavy='B',light='A')),
        source_sequence_length=len(source_seq),iedb_sequence_length=len(subject),alignment=str(alignment),
        alignment_method='Biopython PairwiseAligner blastp, unique global optimum; mmCIF scheme author-to-label mapping; identical residues only',
        observed_antigen_residues=len(observed),mapped_identical_residues=len(mapping),excluded_nonidentical=excluded,
        missing_antigen_label_positions=sorted(set(range(1,len(source_seq)+1))-set(scheme.values())),
        assembly_id='1',checked_operators=60,contact_operators=contact_ops,
        chain_lineage=[dict(derived_chain=dst,source_author_chain=src,operator=op,matrix=operators[op][0].tolist(),translation=operators[op][1].tolist()) for op,names in selected.items() for src,dst in names.items()],
        antigen_coordinates_unchanged=True,max_coordinate_rounding_angstrom=max_rounding,
        contact_boundary_classification_unchanged=True,contact_count=len(contacts),contacts=contacts,
        cautions=['7.2 angstrom experimental model; contact extraction is geometric evidence, not scientific signoff.',
                  'Unresolved source residues and nonidentical mappings are explicitly retained, never modeled or guessed.',
                  'Database registration does not modify historical workflow targets or reports.'])
    dest=OUT/'supplement'
    write_once(dest/entry['path'],derived)
    for f in SOURCE.iterdir():
        if f.is_file():write_once(dest/'provenance/6L62'/f.name,f.read_bytes())
    write_once(dest/'provenance/6L62/mapping-and-assembly.json',encode(provenance))
    write_once(OUT/'coordinate-entry.json',encode(entry))
    write_once(OUT/'local-validation.json',encode(provenance))
    return dict(database_id=NEW_ID,mapped_residues=len(mapping),contact_count=len(contacts),contacts=expected,coordinate_sha256=sha(derived),supplement_files=len(list(dest.rglob('*.*'))))

if __name__=='__main__':print(json.dumps(build(),ensure_ascii=False,indent=2))
