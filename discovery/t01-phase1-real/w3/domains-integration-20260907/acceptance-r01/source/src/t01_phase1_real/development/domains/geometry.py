"""Bound structure observations; all geometry remains development-unreviewed."""
import io
import math
from Bio.PDB import PDBParser, MMCIFParser, NeighborSearch
from .compute import domain


def geometry(report,raw):
    mapping=report.get('mapping')
    if not mapping or not mapping.get('target_chain_id') or any(e['structure_residue'] is None for e in mapping['entries']):
        return dict(status='review_required',reason='STRUCTURE_MAPPING_INCOMPLETE',core_map=None,functional_domains=[])
    if len(mapping['entries'])>2000:
        return dict(status='review_required',reason='GEOMETRY_DEVELOPMENT_SIZE_LIMIT',core_map=None,functional_domains=[])
    kind=report['input']['declared_format']
    parser=PDBParser(QUIET=True) if kind=='PDB' else MMCIFParser(QUIET=True)
    structure=parser.get_structure('N09',io.StringIO(raw.decode()))
    model=list(structure.get_models())[mapping['model_index']]
    chain=model[mapping['target_chain_id']];target=[]
    for entry in mapping['entries']:
        address=entry['structure_residue']
        key=(address['hetero_flag'],address['res_seq'],address['insertion_code'])
        residue=chain[key]
        if residue.get_resname()!=address['residue_name'] or any(a.is_disordered() for a in residue):
            return dict(status='review_required',reason='AMBIGUOUS_STRUCTURE_ATOMS',core_map=None,functional_domains=[])
        target.append(residue)
    atoms=[a for r in target for a in r if a.element not in ('H','D')]
    if any(not all(math.isfinite(float(x)) for x in a.coord) for a in atoms):raise ValueError('Nonfinite geometry')
    if len(atoms)>40000:raise ValueError('Geometry atom bound exceeded')
    index={r:i for i,r in enumerate(target)};contacts=[0]*len(target);neighbors=[set() for r in target]
    for a,b in NeighborSearch(atoms).search_all(4.5):
        i,j=index[a.parent],index[b.parent]
        if i!=j and float(a-b)<4.5:
            contacts[i]+=1;contacts[j]+=1;neighbors[i].add(j);neighbors[j].add(i)
    cb=[r['CB'] if 'CB' in r else None for r in target]
    packing=[sum(other is not None and j!=i and float(atom-other)<6 for j,other in enumerate(cb)) if atom is not None else None
        for i,atom in enumerate(cb)]
    maxpack=max((x for x in packing if x is not None),default=0);maxcontacts=max(contacts,default=0)
    pairs=[]
    for i,r in enumerate(target):
        if r.resname!='CYS' or cb[i] is None:continue
        for j in range(i+1,len(target)):
            if target[j].resname=='CYS' and cb[j] is not None and float(cb[i]-cb[j])<6:
                pairs.append(dict(start=i+1,end=j+1,cb_distance_a=float(cb[i]-cb[j])))
    other=[a for ch in model if ch.id!=chain.id for r in ch if r.id[0]==' ' for a in r if a.element not in ('H','D')]
    interface=[]
    if other:
        search=NeighborSearch(other)
        interface=[i+1 for i,r in enumerate(target) if any(any(float(a-b)<4.5 for b in search.search(a.coord,4.5))
            for a in r if a.element not in ('H','D'))]
    rsa=report.get('rsa');ratios=rsa.get('development_result',{}).get('per_residue') if rsa and rsa.get('development_result') else None
    components=[]
    for i in range(len(target)):
        ratio=ratios[i] if ratios is not None else None
        if ratio is not None and (not math.isfinite(ratio) or not 0<=ratio<=1):raise ValueError('RSA out of domain')
        components.append(dict(position=i+1,burial_score=None if ratio is None else 1-ratio,
            packing_score=packing[i]/maxpack if packing[i] is not None and maxpack else None,
            contact_density=contacts[i]/maxcontacts if maxcontacts else None,
            network_criticality=None,core_state=None,heavy_atom_contact_pairs=contacts[i],
            contacting_residue_count=len(neighbors[i]),cb_neighbor_count=packing[i]))
    return dict(status='geometry_computed_unreviewed',core_map=None,
        functional_domains=[domain('disulfide_bond',p['start'],p['end'],'structure','high') for p in pairs]
            +[domain('oligomer_interface',p,p,'structure','medium') for p in interface],
        disulfide_pairs=pairs,interface_positions=interface,components=components,
        coordinate_space='mature_sequence_via_verified_mapping_no_second_offset',
        conventions=dict(distance_unit='angstrom',packing_self_excluded=True,contact_atoms='heavy_atoms',
            glycine_cb='missing_not_replaced',packing_max_scope='mapped_target_chain',interface_output='individual_residues'),
        review_reasons=['OI_006_CORE_MAP_SCHEMA_UNSIGNED','OI_031_NETWORK_CONTACT_COUNT_AND_GEOMETRY_CONVENTIONS',
            'STRUCTURE_MAPPING_SCIENTIFICALLY_UNREVIEWED']+([] if ratios is not None else ['RSA_UNAVAILABLE_NO_BURIAL_OR_CORE_STATE']),
        scientific_consumption=False)
