"""Offline IEDB evidence retrieval and conservative HSP coordinate transfer.

Pure stdlib so the pinned native BLAST interpreter and control plane share it.
"""
from pathlib import Path
import hashlib
import math
import re
import sqlite3


def qualifying_subjects(raw):
    """Limit metadata retrieval to C20 hits using exact interval coverage."""
    subjects=set()
    for line in raw.splitlines():
        row=line.split('\t')
        if len(row)!=18:raise ValueError('Invalid native HSP columns')
        if float(row[2])>=70 and (int(row[7])-int(row[6])+1)*100/int(row[12])>=80:
            subjects.add(row[1])
    return subjects


def read_evidence(database, subject_ids, manifest):
    path = Path(database) / manifest['iedb']['metadata_path']
    db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    proteins = []; regions = []; structures = []
    try:
        for subject in sorted(set(subject_ids)):
            if not re.fullmatch(r'iedb_[0-9]+', subject):
                raise ValueError('Unexpected IEDB subject ID')
            row = db.execute('SELECT * FROM proteins WHERE subject_id=?', (subject,)).fetchone()
            if row is None: raise ValueError('BLAST subject absent from IEDB mirror')
            proteins.append(dict(row))
            for row in db.execute('SELECT * FROM regions WHERE subject_id=? ORDER BY curated_epitope_id,epitope_id', (subject,)):
                regions.append(dict(row))
                if len(regions)>100000:raise ValueError('IEDB evidence exceeds bounded result envelope')
            for row in db.execute('SELECT * FROM structures WHERE subject_id=? ORDER BY complex_id', (subject,)):
                structures.append(dict(row))
                if len(structures)>20000:raise ValueError('IEDB structure references exceed result envelope')
        coordinates=[]
        for entry in manifest['iedb'].get('complex_coordinates',[]):
            if entry['subject_id'] not in subject_ids:continue
            relative=Path(entry['path'])
            if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe local complex path')
            target=Path(database)/relative
            if target.is_symlink() or not target.resolve().is_relative_to(Path(database).resolve()):
                raise ValueError('Local complex path escapes the database')
            listed=next((f for f in manifest['files'] if f['path']==entry['path']),None)
            if not listed or target.stat().st_size>4*1024**2:raise ValueError('Unregistered or oversized local complex')
            raw=target.read_bytes()
            if len(raw)!=listed['bytes'] or hashlib.sha256(raw).hexdigest()!=listed['sha256']:
                raise ValueError('Local complex coordinate hash differs')
            coordinates.append(dict(entry,pdb_text=raw.decode('ascii'),coordinate_sha256=listed['sha256']))
        return dict(schema_version='0.1.0', database_id=manifest['database_id'],
                    metadata_sha256=next(e['sha256'] for e in manifest['files'] if e['path']==manifest['iedb']['metadata_path']),
                    proteins=proteins, regions=regions, structures=structures,
                    source_sql_sha256=manifest['iedb']['source_sql_sha256'],complex_coordinates=coordinates)
    finally:db.close()


def alignment_map(hsp, sequence, subject_sequence):
    """Only identically aligned residues are transferable; gaps/mismatches fail."""
    if hsp['query_length'] != len(sequence) or hsp['subject_length'] != len(subject_sequence):
        raise ValueError('IEDB HSP sequence length differs')
    if len(hsp['query_alignment'])!=len(hsp['subject_alignment']):raise ValueError('Alignment columns differ')
    if not (1<=hsp['query_start']<=hsp['query_end']<=len(sequence) and
            1<=hsp['subject_start']<=hsp['subject_end']<=len(subject_sequence)):
        raise ValueError('Alignment bounds differ')
    q=hsp['query_start']-1;s=hsp['subject_start']-1;mapping={}
    for qa,sa in zip(hsp['query_alignment'],hsp['subject_alignment']):
        if qa!='-':
            q+=1
            if sequence[q-1]!=qa:raise ValueError('Query alignment differs')
        if sa!='-':
            s+=1
            if subject_sequence[s-1]!=sa:raise ValueError('Subject alignment differs')
        if qa==sa and qa!='-':mapping[s]=q
    if q!=hsp['query_end'] or s!=hsp['subject_end']:raise ValueError('Alignment coordinates differ')
    return mapping


def map_evidence(sequence, hsps, evidence):
    proteins={r['subject_id']:r for r in evidence['proteins']}
    grouped={};warnings=[];regions=[];seen=set()
    for hsp in hsps:
        if not hsp['passes_registered_thresholds']:continue
        if hsp['percent_identity']<70 or hsp['query_coverage_percent']<80:continue
        actual_coverage=(hsp['query_end']-hsp['query_start']+1)*100/len(sequence)
        if actual_coverage<80:continue
        subject=hsp['subject_id']
        if subject not in proteins:raise ValueError('Missing IEDB protein evidence')
        mapping=alignment_map(hsp,sequence,proteins[subject]['sequence'])
        grouped.setdefault(subject,[]).append((hsp,mapping))
    for row in evidence['regions']:
        subject=row['subject_id']
        if subject not in grouped:continue
        if row['mapping_status']!='VALIDATED_SOURCE_INTERVAL':
            warnings.append(dict(code=row['mapping_status'],source_iedb_id=row['epitope_id'],subject_id=subject))
            continue
        candidates=[]
        for hsp,mapping in grouped[subject]:
            ps=[mapping.get(p) for p in range(row['start'],row['end']+1)]
            if not ps or None in ps or ps!=list(range(ps[0],ps[0]+len(ps))):continue
            candidates.append((ps[0],ps[-1],hsp['hsp_index'],hsp['percent_identity']))
        intervals={(r[0],r[1]) for r in candidates}
        if len(intervals)!=1:
            warnings.append(dict(code='IEDB_INTERVAL_UNMAPPABLE' if not intervals else 'IEDB_INTERVAL_AMBIGUOUS',
                                 source_iedb_id=row['epitope_id'],subject_id=subject))
            continue
        first=candidates[0];key=(row['epitope_id'],row['curated_epitope_id'],subject,first[0],first[1])
        if key in seen:continue
        seen.add(key)
        regions.append(dict(start=first[0],end=first[1],e_level='E3-region',
            source_iedb_id=row['epitope_id'],curated_epitope_id=row['curated_epitope_id'],
            epitope_type=row['epitope_type'],reference_id=row['reference_id'],pubmed_id=row['pubmed_id'],
            source_subject_id=subject,source_start=row['start'],source_end=row['end'],
            hsp_indices=[r[2] for r in candidates],transfer='identical_ungapped_residues',
            residue_mapping=[dict(subject_position=s,query_position=q) for s,q in
                zip(range(row['start'],row['end']+1),range(first[0],first[1]+1))],
            mapping_coverage=dict(mapped_residues=row['end']-row['start']+1,source_residues=row['end']-row['start']+1),
            evidence_note='基于同源蛋白表位数据' if max(r[3] for r in candidates)<95 else '匹配蛋白的已有表位数据'))
    structures=[r for r in evidence['structures'] if r['subject_id'] in grouped]
    contacts=[];coordinate_ids=set()
    for package in evidence.get('complex_coordinates',[]):
        if package['subject_id'] not in grouped:continue
        related=[r for r in structures if r['subject_id']==package['subject_id']
                 and r['complex_id']==package['complex_id'] and r.get('reference_id')==package['reference_id']]
        source=[r for r in evidence['regions'] if r['subject_id']==package['subject_id']
                and r['epitope_id']==package['source_iedb_id'] and r['reference_id']==package['reference_id']]
        if not related or not source:raise ValueError('Complex source is not bound to the IEDB metadata')
        coordinate_ids.add((package['subject_id'],package['complex_id']))
        extracted,notes=complex_contacts(package,related[0],proteins[package['subject_id']]['sequence'])
        warnings.extend(notes)
        for contact in extracted:
            positions={mapping.get(contact['subject_position']) for _,mapping in grouped[package['subject_id']]}
            positions.discard(None)
            if len(positions)!=1:
                warnings.append(dict(code='IEDB_CONTACT_UNMAPPABLE',source_iedb_id=package['source_iedb_id']))
                continue
            position=next(iter(positions))
            contacts.append(dict(contact,sequence_position=position,source_subject_id=package['subject_id'],
                source_iedb_id=package['source_iedb_id'],reference_id=package['reference_id'],epitope_type=source[0]['epitope_type']))
    missing=[r for r in structures if (r['subject_id'],r['complex_id']) not in coordinate_ids]
    if missing:
        warnings.append(dict(code='IEDB_COMPLEX_COORDINATES_UNAVAILABLE',
            message='本地镜像含复合物关联记录；未具备可核验的原子坐标，不从 PDB 编号或历史接触列表推定 E4。',
            count=len(missing)))
    return dict(iedb_hit=bool(grouped),evidence_level='literature_supported' if grouped else 'computational_prediction',
                matched_proteins=[dict(subject_id=subject,hsp_indices=[h['hsp_index'] for h,_ in hits],
                    maximum_identity_percent=max(h['percent_identity'] for h,_ in hits),
                    evidence_note='基于同源蛋白表位数据' if max(h['percent_identity'] for h,_ in hits)<95 else '匹配蛋白的已有表位数据')
                    for subject,hits in grouped.items()],
                epitope_regions=regions,contact_residues=contacts,structure_references=structures,
                e4_status='partial' if contacts and missing else 'computed' if contacts else 'unavailable' if structures else 'not_applicable',warnings=warnings,
                database_id=evidence['database_id'],metadata_sha256=evidence['metadata_sha256'],
                source_sql_sha256=evidence['source_sql_sha256'])


AA3=dict(zip(('ALA','CYS','ASP','GLU','PHE','GLY','HIS','ILE','LYS','LEU','MET','ASN','PRO','GLN','ARG','SER','THR','VAL','TRP','TYR'),
             'ACDEFGHIKLMNPQRSTVWY'))


def complex_contacts(package, metadata, subject_sequence):
    """C20 heavy-atom contacts from a hashed local PDB and explicit residue map.

    Ambiguous conformations/chain roles remain unassessed. No PDB identifier is
    fetched online and no source numbering is guessed from array positions.
    """
    raw=package['pdb_text'].encode('ascii')
    if hashlib.sha256(raw).hexdigest()!=package['coordinate_sha256']:raise ValueError('Complex coordinate digest differs')
    chains={};atoms=set();models=0
    for line in package['pdb_text'].splitlines():
        if line.startswith('MODEL '):models+=1
        if models>1: return [],[dict(code='IEDB_COMPLEX_MULTIPLE_MODELS_UNRESOLVED')]
        if not line.startswith('ATOM  ') or line[17:20].strip() not in AA3:continue
        if len(line)<78:raise ValueError('Truncated local PDB atom')
        if line[16].strip():return [],[dict(code='IEDB_COMPLEX_ALTLOC_UNRESOLVED')]
        element=line[76:78].strip().upper()
        if not element:raise ValueError('PDB element is required for heavy-atom contacts')
        if element in ('H','D'):continue
        chain=line[21];key=(int(line[22:26]),line[26].strip());residue=AA3[line[17:20].strip()]
        atom=(chain,key,line[12:16].strip())
        if atom in atoms:raise ValueError('Duplicate PDB atom')
        atoms.add(atom)
        xyz=tuple(float(line[i:i+8]) for i in (30,38,46))
        if not all(math.isfinite(x) for x in xyz):raise ValueError('Nonfinite local PDB coordinate')
        row=chains.setdefault(chain,{}).setdefault(key,dict(residue=residue,atoms=[]))
        if row['residue']!=residue:raise ValueError('Conflicting PDB residue identity')
        row['atoms'].append(xyz)
    notes=[];antigen=(metadata.get('ant_pdb_chain') or '').strip()
    if antigen:
        if antigen not in chains:return [],[dict(code='IEDB_ANTIGEN_CHAIN_UNAVAILABLE')]
        partners=[c for c in chains if c!=antigen]
    elif len(chains)==2 and len({len(v) for v in chains.values()})==2:
        antibody=min(chains,key=lambda c:len(chains[c]));antigen=next(c for c in chains if c!=antibody)
        partners=[antibody];notes.append(dict(code='IEDB_SHORTER_CHAIN_ANTIBODY_ASSUMPTION',severity='WARNING'))
    else:return [],[dict(code='IEDB_COMPLEX_CHAIN_ROLE_UNRESOLVED')]
    if not partners:return [],[dict(code='IEDB_COMPLEX_PARTNER_UNAVAILABLE')]
    mapping={}
    for row in package['residue_map']:
        key=(row['chain'],row['resseq'],row['icode'])
        position=row['subject_position']
        if key in mapping or type(position) is not int or not 1<=position<=len(subject_sequence):
            raise ValueError('Invalid complex residue mapping')
        source=chains.get(row['chain'],{}).get((row['resseq'],row['icode']))
        if source is None or source['residue']!=row['residue'] or subject_sequence[position-1]!=row['residue']:
            raise ValueError('Complex residue map identity differs')
        mapping[key]=position
    # Spatial bins avoid quadratic all-atom comparisons for large complexes.
    grid={}
    for chain in partners:
        for row in chains[chain].values():
            for xyz in row['atoms']:grid.setdefault(tuple(math.floor(v/4) for v in xyz),[]).append(xyz)
    contacts=[]
    for (resseq,icode),row in chains[antigen].items():
        distances=[]
        for xyz in row['atoms']:
            box=tuple(math.floor(v/4) for v in xyz)
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for dz in (-1,0,1):
                        for other in grid.get((box[0]+dx,box[1]+dy,box[2]+dz),[]):
                            distance=sum((a-b)**2 for a,b in zip(xyz,other))
                            if distance<=16:distances.append(math.sqrt(distance))
        if not distances:continue
        position=mapping.get((antigen,resseq,icode))
        if position is None:
            notes.append(dict(code='IEDB_CONTACT_SOURCE_MAPPING_UNAVAILABLE',chain=antigen,resseq=resseq,icode=icode));continue
        contacts.append(dict(chain=antigen,resseq=resseq,icode=icode,residue=row['residue'],
            evidence_source=package['source_iedb_id'],subject_position=position,
            coordinate_sha256=package['coordinate_sha256'],minimum_heavy_atom_distance_angstrom=min(distances)))
    return contacts,notes
