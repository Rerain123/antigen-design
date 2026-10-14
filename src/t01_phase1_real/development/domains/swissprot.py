"""Versioned Swiss-Prot DAT projection; source coordinates are never guessed."""
import io
from Bio import SwissProt
from Bio.SeqFeature import ExactPosition, UnknownPosition

TYPES=dict(zip(('TRANSMEM','SIGNAL','ACT_SITE','BINDING','REPEAT','DOMAIN','REGION','TOPO_DOM',
    'SITE','DISULFID','MOD_RES','CHAIN'),('Transmembrane','Signal','Active site','Binding site','Repeat',
    'Domain','Region','Topological domain','Site','Disulfide bond','Modified residue','Chain')))

def project(raw,body):
    record=SwissProt.read(io.StringIO(raw.decode('utf8')))
    features=[];spaces=[];audit=[]
    for i,f in enumerate(record.features):
        loc=f.location
        if loc.ref:
            audit.append(dict(feature_index=i,reason='ISOFORM_COORDINATES_NOT_CANONICAL',isoform=loc.ref));continue
        def pos(p,offset):
            return dict(value=None if isinstance(p,UnknownPosition) else int(p)+offset,
                modifier='EXACT' if type(p) is ExactPosition else 'UNKNOWN' if isinstance(p,UnknownPosition) else 'UNSURE')
        start,end=pos(loc.start,1),pos(loc.end,0)
        kind=TYPES.get(f.type,f.type)
        space='parent' if body['parent'] else 'mature'
        if kind=='Chain' and body['parent']:
            parent=body['parent'];offset=parent['offset']
            if start!=dict(value=offset,modifier='EXACT') or end!=dict(value=offset+len(body['protein_sequence'])-1,modifier='EXACT'):
                audit.append(dict(feature_index=i,reason='CHAIN_NOT_EXACT_DECLARED_MATURE_SLICE'));continue
            start=dict(value=1,modifier='EXACT');end=dict(value=len(body['protein_sequence']),modifier='EXACT');space='mature'
        features.append(dict(type=kind,description=f.qualifiers.get('note',f.qualifiers.get('description','')),
            location=dict(start=start,end=end)));spaces.append(space)
    # Swiss-Prot OS includes optional common names after the scientific name.
    organism=record.organism.rstrip('.').split(' (',1)[0]
    entry=dict(primaryAccession=record.accessions[0],entryType='UniProtKB reviewed (Swiss-Prot)',
        organism=dict(scientificName=organism),sequence=dict(value=record.sequence),features=features,coordinate_spaces=spaces)
    return entry,audit
