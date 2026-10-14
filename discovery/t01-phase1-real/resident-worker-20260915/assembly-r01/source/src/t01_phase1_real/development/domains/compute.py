"""S-16 L1/L2/L3, explicit coordinate conversion and recorded decisions."""
import re
from Bio.Seq import Seq

L1=dict(zip(('Transmembrane','Signal','Active site','Binding site','Repeat','Domain','Region','Topological domain',
    'Site','Disulfide bond','Modified residue','Chain'),('TMhelix','signal_peptide','active_site','binding_site','repeat_region',
    'domain','functional_region','topo_domain','functional_site','disulfide_bond','PTM_site','mature_chain')))
L2={'NLS':('nuclear localization','nls','bipartite nls'),'RBD':('receptor binding','rbd'),
    'VLP_assembly':('vlp','capsid','capsid assembly','virus-like particle')}
MOTIFS={'NLS':r'K[KR].[KR]','Furin':r'R.[KR]R','Sortase':r'LP.TG','RGD':r'RGD','Picornavirus_2A':r'D.E.NPGP'}


def domain(kind,start,end,source,confidence):
    return dict(type=kind,start=start,end=end,source=source,confidence=confidence)


def scan(sequence):
    seq=str(Seq(sequence))
    return [domain(kind,m.start()+1,m.start()+len(m.group(1)),'regex','low')
        for kind,pattern in MOTIFS.items() for m in re.finditer('(?=('+pattern+'))',seq)]


def coordinates(feature,space,body,index,audit):
    start,end=(feature['location'][key] for key in ('start','end'))
    reason=None
    if any(x['modifier']!='EXACT' or type(x['value']) is not int for x in (start,end)):
        reason='UNCERTAIN_FEATURE_COORDINATES'
    elif not 1<=start['value']<=end['value']:reason='INVALID_FEATURE_COORDINATES'
    elif feature['type']=='Chain' and space!='mature':reason='CHAIN_MUST_USE_MATURE_COORDINATES'
    elif space=='parent' and body['parent'] is None:reason='PARENT_COORDINATE_SOURCE_MISSING'
    if reason:
        audit.append(dict(feature_index=index,action='review',reason=reason));return None
    a,b=start['value'],end['value'];original=[a,b];source='uniprot'
    if space=='parent':
        offset=body['parent']['offset']-1;a-=offset;b-=offset;source+='_remapped'
    length=len(body['protein_sequence'])
    if b<1 or a>length:
        audit.append(dict(feature_index=index,action='discard',reason='OUTSIDE_MATURE_SEQUENCE',original=original,mapped=[a,b]));return None
    if space=='mature' and (a<1 or b>length):
        audit.append(dict(feature_index=index,action='review',reason='MATURE_COORDINATE_OUT_OF_RANGE',original=original));return None
    clipped=[max(1,a),min(length,b)]
    audit.append(dict(feature_index=index,action='clip' if clipped!=[a,b] else 'retain',original=original,
        mapped=clipped,coordinate_space=space,source=source))
    return *clipped,source


def compute(body,entries,topology=None,geometry=None):
    query=body['protein_sequence'];audit=[];warnings=[];review=[]
    expected=body['parent']['sequence'] if body['parent'] else query
    candidates=[e for e in entries if e['sequence']['value']==expected and e['organism']['scientificName']==body['organism_name']]
    if body['entry_id'] is not None:
        explicit=[e for e in entries if e['primaryAccession']==body['entry_id']]
        if explicit and explicit[0] not in candidates:
            review.append('EXPLICIT_ENTRY_SEQUENCE_OR_ORGANISM_MISMATCH');candidates=[]
        else:candidates=[e for e in candidates if e['primaryAccession']==body['entry_id']]
    if len(candidates)>1:review.append('MULTIPLE_EXACT_ENTRIES_REQUIRE_SELECTION')
    entry=candidates[0] if len(candidates)==1 else None
    annotations=[]
    if entry:
        reviewed=entry['entryType']=='UniProtKB reviewed (Swiss-Prot)'
        if not reviewed:review.append('UNREVIEWED_CONFIDENCE_DOWNGRADE_UNRESOLVED')
        for index,(feature,space) in enumerate(zip(entry['features'],entry['coordinate_spaces'])):
            coord=coordinates(feature,space,body,index,audit)
            if coord is None:continue
            a,b,source=coord;kind=L1.get(feature['type'])
            if not reviewed:
                audit.append(dict(feature_index=index,action='review',reason='UNREVIEWED_CONFIDENCE_DOWNGRADE_UNRESOLVED'));continue
            if kind:
                annotations.append(domain(kind,a,b,source,'high'))
            else:
                matches=[name for name,terms in L2.items() if any(term in feature['description'].lower() for term in terms)]
                if len(matches)>1:
                    audit.append(dict(feature_index=index,action='review',reason='MULTIPLE_L2_CLASSES'));continue
                if matches:annotations.append(domain(matches[0],a,b,source,'medium'))
                else:audit.append(dict(feature_index=index,action='unmapped',reason='NO_L1_L2_MAPPING'))
    lookup=dict(status='hit' if entry else 'ambiguous' if len(candidates)>1 else 'no_exact_match',
        candidate_ids=[e['primaryAccession'] for e in candidates],selected_entry=entry['primaryAccession'] if entry else None,
        mode='exact_sequence_and_organism',homology_transfer=False)
    if not entry:warnings.append('NO_UNIQUE_EXACT_ANNOTATION_ENTRY')
    motifs=scan(query);retained=[]
    # Resolve the prose's global L1/L2 overlap rule against the sorted-loop
    # asymmetry by closing only hits whose outcome differs between the two.
    for motif in motifs:
        overlaps=[d for d in annotations if max(0,min(d['end'],motif['end'])-max(d['start'],motif['start'])+1)
            /min(d['end']-d['start']+1,motif['end']-motif['start']+1)>=.8]
        prior=[d for d in overlaps if d['start']<=motif['start']]
        if overlaps:
            audit.append(dict(motif=motif,action='suppress' if prior else 'review',reason=
                'L1_L2_OVERLAP_AT_LEAST_80_PERCENT' if prior else 'OVERLAP_SORT_ORDER_UNRESOLVED'))
        else:retained.append(motif)
    topo=[]
    if topology is None:warnings.append('TOPOLOGY_UNAVAILABLE')
    else:
        for segment in topology['segments']:
            if segment['type'] in ('TMhelix','signal'):
                # Confidence for reused DeepTMHMM is not assigned by S-16.
                # Preserve verified regions as observations instead of inventing it.
                topo.append(dict(type='signal_peptide' if segment['type']=='signal' else 'TMhelix',start=segment['start'],
                    end=segment['end'],source='deepTMHMM',confidence=None,coordinate_space='mature'))
        if topo:review.append('REUSED_TOPOLOGY_CONFIDENCE_UNRESOLVED')
    users=[domain(row['type'],row['start'],row['end'],'user_annotation','user_high') for row in body['user_annotations']]
    structural=geometry.get('functional_domains',[]) if geometry else []
    for d in structural:
        if d['type']=='disulfide_bond' and any(x['type']==d['type'] and x['start']==d['start'] and x['end']==d['end'] for x in annotations):
            audit.append(dict(domain=d,action='suppress',reason='EXACT_UNIPROT_DISULFIDE_DUPLICATE'))
        else:annotations.append(d)
    values=sorted(annotations+retained+users,key=lambda d:d['start'])
    review.extend(row['reason'] for row in audit if row['action']=='review')
    if any(d['type'] in ('TMhelix','signal_peptide') for d in annotations) and topology is None:
        review.append('L1_TM_SIGNAL_VS_NULL_TOPOLOGY_FALLBACK_CONFLICT')
    return dict(functional_domains=values,lookup=lookup,topology_observation=topo,
        topology_status='not_available' if topology is None else 'verified_available',user_annotations=body['user_annotations'],
        motif_observations=motifs,coordinate_and_merge_audit=audit,review_reasons=sorted(set(review)),warnings=warnings,
        core_map=None,structure_assessment=geometry or dict(status='not_provided',core_map=None),
        functional_domains_qualification='DEVELOPMENT_UNREVIEWED',scientific_consumption=False)
