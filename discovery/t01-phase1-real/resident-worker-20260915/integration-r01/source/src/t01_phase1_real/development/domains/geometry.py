"""Bound structure observations; all geometry remains development-unreviewed."""
import io
import math
from Bio.PDB import PDBParser, MMCIFParser, NeighborSearch
from .compute import domain


def core_state(burial,packing,contact,network):
    """S-16 numeric tiers; unresolved operands never imply ordinary or deep."""
    if burial is None:return None
    if burial<.50:return 'shallow'
    if packing is None or contact is None or network is None:return None
    return 'deep_critical' if burial>=.80 and packing>=.70 and contact>=.60 and network else 'ordinary'


def contact_components(neighbors,counts):
    remaining={i for i,c in enumerate(counts) if c>=3};groups=[]
    while remaining:
        todo=[min(remaining)];members=set()
        while todo:
            i=todo.pop()
            if i not in remaining:continue
            remaining.remove(i);members.add(i);todo.extend(neighbors[i]&remaining)
        groups.append(sorted(i+1 for i in members))
    return groups


def geometry(report,raw):
    mapping=report.get('mapping')
    if not mapping or not mapping.get('target_chain_id') or any(e['structure_residue'] is None for e in mapping['entries']):
        return dict(status='review_required',reason='STRUCTURE_MAPPING_INCOMPLETE',core_map=None,functional_domains=[])
    if len(mapping['entries'])>2000:
        return dict(status='review_required',reason='GEOMETRY_DEVELOPMENT_SIZE_LIMIT',core_map=None,functional_domains=[])
    kind=report['input']['structure_artifact']['media_type']
    parser=PDBParser(QUIET=True) if kind=='chemical/x-pdb' else MMCIFParser(QUIET=True)
    structure=parser.get_structure('N09',io.StringIO(raw.decode()))
    model=list(structure.get_models())[mapping['model_index']]
    chain=model[mapping['target_chain_id']];target=[]
    for entry in mapping['entries']:
        address=entry['structure_residue']
        key=(address['hetero_flag'],address['res_seq'],address['insertion_code'] or ' ')
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
        burial=None if ratio is None else 1-ratio
        packed=packing[i]/maxpack if packing[i] is not None and maxpack else None
        density=contacts[i]/maxcontacts if maxcontacts else None
        # Both possible contact-count interpretations remain observable; expose
        # a development boolean only where they agree, without choosing a rule.
        network=(contacts[i]>=3) if (contacts[i]>=3)==(len(neighbors[i])>=3) else None
        components.append(dict(position=i+1,burial_score=burial,
            packing_score=packed,contact_density=density,
            network_criticality=network,core_state=core_state(burial,packed,density,network),heavy_atom_contact_pairs=contacts[i],
            contacting_residue_count=len(neighbors[i]),cb_neighbor_count=packing[i]))
    return dict(status='geometry_computed_unreviewed',core_map=None,
        functional_domains=[domain('disulfide_bond',p['start'],p['end'],'structure','high') for p in pairs]
            +[domain('oligomer_interface',p,p,'structure','medium') for p in interface],
        disulfide_pairs=pairs,interface_positions=interface,components=components,
        contact_graph_components=dict(by_residue_neighbors=contact_components(neighbors,[len(x) for x in neighbors]),
            by_heavy_atom_pairs=contact_components(neighbors,contacts)),
        coordinate_space='mature_sequence_via_verified_mapping_no_second_offset',
        conventions=dict(distance_unit='angstrom',packing_self_excluded=True,contact_atoms='heavy_atoms',
            glycine_cb='missing_not_replaced',packing_max_scope='mapped_target_chain',interface_output='individual_residues'),
        review_reasons=['OI_006_CORE_MAP_SCHEMA_UNSIGNED','OI_031_NETWORK_CONTACT_COUNT_AND_GEOMETRY_CONVENTIONS',
            'STRUCTURE_MAPPING_SCIENTIFICALLY_UNREVIEWED']+([] if ratios is not None else ['RSA_UNAVAILABLE_NO_BURIAL_OR_CORE_STATE']),
        scientific_consumption=False)
