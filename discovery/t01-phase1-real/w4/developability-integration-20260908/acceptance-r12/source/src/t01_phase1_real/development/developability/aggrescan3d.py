"""Pinned official AGGRESCAN3D parsing and guarded S-37 structure post-processing."""
import csv
import io
import json
import math

from Bio.PDB import PDBParser

from ...common import RuntimeFault, ensure

IMAGE_REPOSITORY='lcbio/a3d_server'
IMAGE_DIGEST='sha256:c9e5a38b7d7f22c0b76678c5135ec4bf1af47cf77e8c9547a3bb4b9f7f2e938b'
IMAGE=IMAGE_REPOSITORY+'@'+IMAGE_DIGEST
IMAGE_ID=IMAGE_DIGEST
VERSION='0.9.11'
PYTHON_VERSION='2.7.15'
DEFAULT_DISTANCE_ANGSTROM=10.0
CSV_FIELDS=['protein','chain','residue','residue_name','score']


def project_target_chain_pdb(raw,chain):
    """Remove non-coordinate/foreign-chain lines that break legacy A3D's -C parser."""
    ensure(isinstance(chain,str) and len(chain)==1 and chain.isascii(),'OUTPUT_INVALID','A3D requires one ASCII chain ID')
    try:lines=raw.decode('ascii').splitlines()
    except UnicodeDecodeError as exc:raise RuntimeFault('OUTPUT_INVALID','A3D PDB projection requires ASCII input') from exc
    selected=[]
    for line in lines:
        if not line.startswith('ATOM  '):continue
        ensure(len(line)>=54,'OUTPUT_INVALID','A3D source contains a truncated ATOM record')
        if line[21]==chain:selected.append(line)
    ensure(selected,'OUTPUT_INVALID','A3D target-chain PDB projection is empty')
    projected=('\n'.join(selected)+'\n').encode('ascii')
    try:parsed=next(PDBParser(PERMISSIVE=False,QUIET=True).get_structure('a3d-projection',io.StringIO(projected.decode())).get_models())
    except Exception as exc:raise RuntimeFault('OUTPUT_INVALID','A3D target-chain PDB projection cannot be parsed') from exc
    ensure({item.id for item in parsed}=={chain},'OUTPUT_INVALID','A3D target-chain PDB projection changed chain identity')
    return projected


def unavailable(execution,reason=None):
    reason=reason or execution.get('reason_code') or 'AGGRESCAN3D_NOT_RUN'
    return dict(status='unavailable',reliable=False,reason_code=reason,mode=None,tool='AGGRESCAN3D(C45)',
        global_score=None,average_score=None,per_residue=None,hotspots=None,hotspot_count=None,classification=None,
        clusters=None,execution=execution,method=None,warnings=[reason])


def _mapping(source,sequence,chain):
    report=source.get('analysis') or {};mapping=report.get('mapping') or {}
    ensure(mapping.get('target_chain_id')==chain and mapping.get('sequence')==sequence,
        'OUTPUT_INVALID','A3D source mapping differs from N10 sequence/chain')
    positions={}
    for row in mapping.get('entries') or []:
        residue=row.get('structure_residue') or {};position=row.get('sequence_position')
        ensure(type(position) is int and 1<=position<=len(sequence) and row.get('sequence_residue')==sequence[position-1]
            and residue.get('chain_id')==chain and residue.get('hetero_flag')==' '
            and (residue.get('insertion_code') or '')=='' and type(residue.get('res_seq')) is int,
            'OUTPUT_INVALID','A3D requires unambiguous mapped standard residues without insertion codes')
        key=(chain,residue['res_seq'])
        ensure(key not in positions,'OUTPUT_INVALID','A3D residue address is not unique')
        positions[key]=dict(position=position,residue=sequence[position-1],author_residue_number=residue['res_seq'])
    ensure(positions,'OUTPUT_INVALID','A3D source contains no mapped residues')
    return positions


def _scores(raw,positions,chain):
    try:text=raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc:raise RuntimeFault('OUTPUT_INVALID','A3D CSV is not UTF-8') from exc
    reader=csv.DictReader(io.StringIO(text))
    ensure(reader.fieldnames==CSV_FIELDS,'OUTPUT_INVALID','A3D CSV header differs')
    rows=[];seen=set()
    for row in reader:
        ensure(set(row)==set(CSV_FIELDS) and row['chain']==chain,'OUTPUT_INVALID','A3D CSV chain/columns differ')
        try:number=int(row['residue']);score=float(row['score'])
        except (TypeError,ValueError) as exc:raise RuntimeFault('OUTPUT_INVALID','A3D CSV contains an invalid number') from exc
        ensure(math.isfinite(score),'OUTPUT_INVALID','A3D CSV contains a non-finite score')
        key=(chain,number);ensure(key in positions and key not in seen,'OUTPUT_INVALID','A3D CSV residue cannot be mapped uniquely')
        mapped=positions[key]
        ensure(row['residue_name']==mapped['residue'],'OUTPUT_INVALID','A3D CSV residue identity differs from mapping')
        seen.add(key);rows.append(dict(sequence_position=mapped['position'],chain_id=chain,
            author_residue_number=number,residue=mapped['residue'],score=score))
    ensure(rows and seen==set(positions),'OUTPUT_INVALID','A3D CSV does not cover every mapped residue')
    return sorted(rows,key=lambda row:row['sequence_position'])


def _statistics(raw,rows):
    try:value=json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:raise RuntimeFault('OUTPUT_INVALID','A3D folded_stats is invalid JSON') from exc
    stats=value.get('All') if isinstance(value,dict) else None
    ensure(isinstance(stats,dict) and set(stats)=={'max_value','avg_value','min_value','total_value'}
        and all(type(stats[name]) in (int,float) and math.isfinite(stats[name]) for name in stats),
        'OUTPUT_INVALID','A3D folded_stats schema differs')
    scores=[row['score'] for row in rows];total=math.fsum(scores)
    ensure(math.isclose(stats['total_value'],total,abs_tol=1e-3)
        and math.isclose(stats['avg_value'],total/len(scores),abs_tol=1e-3)
        and math.isclose(stats['max_value'],max(scores),abs_tol=1e-4)
        and math.isclose(stats['min_value'],min(scores),abs_tol=1e-4),
        'OUTPUT_INVALID','A3D folded_stats differs from per-residue scores')
    return {name:float(stats[name]) for name in stats}


def _ca_coordinates(raw,positions):
    try:model=next(PDBParser(PERMISSIVE=False,QUIET=True).get_structure('a3d-input',io.StringIO(raw.decode('ascii'))).get_models())
    except Exception as exc:raise RuntimeFault('OUTPUT_INVALID','A3D PDB cannot be parsed for spatial clusters') from exc
    coordinates={}
    for chain in model:
        for residue in chain:
            key=(chain.id,residue.id[1])
            if key not in positions:continue
            ensure(residue.id[0]==' ' and residue.id[2].strip()=='' and 'CA' in residue,
                'OUTPUT_INVALID','A3D mapped residue lacks one unambiguous C-alpha')
            position=positions[key]['position'];ensure(position not in coordinates,'OUTPUT_INVALID','Duplicate A3D C-alpha position')
            coordinates[position]=tuple(float(value) for value in residue['CA'].coord)
    ensure(set(coordinates)=={row['position'] for row in positions.values()},
        'OUTPUT_INVALID','A3D C-alpha coordinates do not cover mapped residues')
    return coordinates


def spatial_clusters(rows,coordinates,distance=DEFAULT_DISTANCE_ANGSTROM):
    """Engineering graph interpretation of the locked positive-score/10 A spatial rule."""
    positive={row['sequence_position'] for row in rows if row['score']>0.0};adjacency={position:set() for position in positive}
    for left in sorted(positive):
        for right in sorted(position for position in positive if position>left):
            distance_sq=math.fsum((a-b)**2 for a,b in zip(coordinates[left],coordinates[right]))
            if distance_sq<=distance**2+1e-9:
                adjacency[left].add(right);adjacency[right].add(left)
    components=[];remaining=set(positive)
    while remaining:
        todo=[min(remaining)];component=set()
        while todo:
            position=todo.pop()
            if position in component:continue
            component.add(position);remaining.discard(position);todo.extend(adjacency[position]-component)
        if len(component)>=3:components.append(sorted(component))
    return sorted(components,key=lambda values:(values[0],values[-1],values))


def assess(csv_raw,stats_raw,pdb_raw,body,source,execution):
    if execution.get('status')!='executed' or csv_raw is None or stats_raw is None or pdb_raw is None:
        return unavailable(execution)
    report=source.get('analysis') or {};mapping=report.get('mapping') or {};chain=mapping.get('target_chain_id')
    ensure(isinstance(chain,str) and len(chain)==1,'OUTPUT_INVALID','A3D target chain is unavailable')
    positions=_mapping(source,body['protein_sequence'],chain);rows=_scores(csv_raw,positions,chain)
    stats=_statistics(stats_raw,rows);coordinates=_ca_coordinates(pdb_raw,positions)
    components=spatial_clusters(rows,coordinates)
    clusters=[dict(cluster_id='a3d-'+str(index),residue_positions=values,
        author_residue_numbers=[next(row['author_residue_number'] for row in rows if row['sequence_position']==position)
            for position in values]) for index,values in enumerate(components,1)]
    hotspots=[dict(start=values[0],end=values[-1],display_envelope_only=True) for values in components]
    count=len(components);classification='high_risk' if count>3 else None
    warnings=['A3D_SPATIAL_CLUSTER_SCIENTIFIC_SIGNOFF_MISSING']
    if classification is None:warnings.append('A3D_NON_HIGH_RISK_CLASSIFICATION_UNRESOLVED')
    quality=((report.get('quality') or {}).get('quality') or {}).get('confidence')
    if quality=='low':warnings.append('STRUCTURE_QUALITY_LOW')
    if mapping.get('mapping_status')!='verified':warnings.append('STRUCTURE_MAPPING_SCIENTIFIC_SIGNOFF_MISSING')
    return dict(status='computed_unreviewed',reliable=False,
        reason_code='A3D_SPATIAL_CLUSTER_SCIENTIFIC_SIGNOFF_MISSING',mode='structure',tool='AGGRESCAN3D(C45)',
        global_score=stats['total_value'],average_score=stats['avg_value'],per_residue=rows,hotspots=hotspots,
        hotspot_count=count,classification=classification,clusters=clusters,execution=execution,
        method=dict(aggrescan3d_version=VERSION,image=IMAGE,image_digest=IMAGE_DIGEST,python=PYTHON_VERSION,
            distance_angstrom=DEFAULT_DISTANCE_ANGSTROM,member_score_threshold='>0',minimum_cluster_residues=3,
            cluster_postprocess='positive-score C-alpha distance graph connected components; engineering interpretation pending signoff',
            hotspot_interval_semantics='display envelope only; clusters retain exact residue positions'),warnings=warnings)
