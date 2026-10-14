"""Exact N09 inputs and immutable operator-registered annotation packages."""
from pathlib import Path
import re
import sys
import Bio

from ...common import REPO, decode, encode, ensure, sha, profile as base_profile
from ...files import read_locked, no_links
from ..blast.policy import _safe_database_root, _hash_file
from ..glycosylation.policy import ARTIFACT_FIELDS

TOOL='t01.real.domains'
NODE='N09'
HERE=Path(__file__).parent
AUTHORITY=[REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'/name for name in
    ('AgentA_SOP_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md','AgentA_SKILL_v10.5_20260902.md','ToolSpec_UniProt注释接口_v10.5.md')]


def sequence(value):
    ensure(isinstance(value,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{1,20000}',value),
        'INVALID_REQUEST','Exact uppercase AA20 sequence, 1..20000 aa required')


def source(value):
    ensure(isinstance(value,dict) and set(value)=={'state','artifact','reason_code'},'INVALID_REQUEST','Exact upstream state/ref/reason required')
    ensure(value['state'] in ('not_provided','available','upstream_unavailable'),'INVALID_REQUEST','Invalid source state')
    ref=value['artifact']
    if value['state']=='not_provided':
        ensure(ref is None and value['reason_code'] is None,'INVALID_REQUEST','Absent input must not claim a source')
        return
    ensure(isinstance(ref,dict) and set(ref)==ARTIFACT_FIELDS and ref['role'] in ('result','diagnostic')
        and ref['media_type']=='application/json' and ref['evidence_kind']=='G0_REAL_OUTPUT',
        'INVALID_REQUEST','Registered real upstream ArtifactRef required')
    ensure(isinstance(ref['sha256'],str) and re.fullmatch('[0-9a-f]{64}',ref['sha256']) and type(ref['size_bytes']) is int
        and 0<ref['size_bytes']<=32*1024**2,'INVALID_REQUEST','Invalid upstream digest/size')
    ensure(value['reason_code'] is None if value['state']=='available' else isinstance(value['reason_code'],str)
        and 0<len(value['reason_code'])<=128,'INVALID_REQUEST','Invalid upstream reason')


def request(raw):
    value=decode(raw)
    ensure(isinstance(value,dict) and set(value)=={'protein_sequence','user_sequence_id','organism_name','database_id',
        'database_manifest_sha256','entry_id','parent','topology_input','structure_input','user_annotations','timeout_seconds'},
        'INVALID_REQUEST','Exact N09 request fields required')
    sequence(value['protein_sequence'])
    for key in ('user_sequence_id','organism_name'):
        ensure(isinstance(value[key],str) and 0<len(value[key])<=512,'INVALID_REQUEST','Invalid '+key)
    ensure(isinstance(value['database_id'],str) and re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',value['database_id']),
        'INVALID_REQUEST','Registered local annotation ID required')
    ensure(isinstance(value['database_manifest_sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['database_manifest_sha256']),
        'INVALID_REQUEST','Exact data manifest SHA-256 required')
    ensure(value['entry_id'] is None or isinstance(value['entry_id'],str) and re.fullmatch('[A-Za-z0-9_.-]{1,80}',value['entry_id']),
        'INVALID_REQUEST','Invalid explicit annotation entry')
    parent=value['parent']
    if parent is not None:
        ensure(isinstance(parent,dict) and set(parent)=={'id','offset','sequence'} and isinstance(parent['id'],str)
            and re.fullmatch('[A-Za-z0-9_.-]{1,80}',parent['id']) and type(parent['offset']) is int and parent['offset']>=1,
            'INVALID_REQUEST','Parent requires exact ID, 1-based offset and original sequence')
        sequence(parent['sequence']);start=parent['offset']-1
        ensure(parent['sequence'][start:start+len(value['protein_sequence'])]==value['protein_sequence'],
            'INVALID_REQUEST','Mature sequence must be the exact declared parent slice')
    source(value['topology_input']);source(value['structure_input'])
    annotations=value['user_annotations']
    ensure(isinstance(annotations,list) and len(annotations)<=500,'INVALID_REQUEST','Bounded user annotation list required')
    for row in annotations:
        ensure(isinstance(row,dict) and set(row)=={'type','start','end','note'} and isinstance(row['type'],str)
            and re.fullmatch('[A-Za-z][A-Za-z0-9_]{0,63}',row['type']) and isinstance(row['note'],str) and len(row['note'])<=512
            and type(row['start']) is int and type(row['end']) is int and 1<=row['start']<=row['end']<=len(value['protein_sequence']),
            'INVALID_REQUEST','User annotations must use mature 1-based closed coordinates')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=60,'INVALID_REQUEST','N09 deadline 1..60 seconds required')
    return value


def sequence_id(seq):return 't01d_'+sha(seq.encode())[:16]


def registered_rules():
    return dict(id='w3-n09-s16-v105-development',version='0.1.0',sha256=sha(encode(dict(
        sources={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in AUTHORITY},
        code={p.name:sha(p.read_bytes()) for p in HERE.glob('*.py')},unresolved=['OI-006','OI-031'],scientific_consumption=False))))


def registered_profile():
    paths=list(HERE.glob('*.py'))+[HERE.parent/name for name in ('runtime.py','registry.py','contracts.py','cli.py')]
    return dict(id='w3-n09-local-domains-development',version='0.1.0',sha256=sha(encode(dict(
        code={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},rules=registered_rules(),
        biopython=Bio.__version__,python=sys.version,python_sha256=sha(Path(sys.executable).read_bytes()),base=base_profile(),
        backend='trusted-local-in-process',network=False))))


def database(root,body):
    root=_safe_database_root(root);folder=no_links(root/body['database_id'])
    ensure(folder.is_dir() and folder.resolve().parent==root,'ASSET_MISSING','Registered N09 data package unavailable')
    raw=read_locked(folder/'manifest.json',1024**2)
    ensure(sha(raw)==body['database_manifest_sha256'],'HASH_MISMATCH','N09 data manifest changed')
    manifest=decode(raw)
    ensure(isinstance(manifest,dict) and set(manifest)=={'schema_version','database_id','qualification','purpose','source','files'}
        and manifest['schema_version']=='0.1.0' and manifest['database_id']==body['database_id']
        and manifest['qualification'] in ('ENGINEERING_FIXTURE','TARGET_DATABASE_UNREVIEWED')
        and manifest['purpose']=='N09_LOCAL_ANNOTATIONS','HASH_MISMATCH','N09 package purpose/identity differs')
    ensure(isinstance(manifest['source'],dict) and set(manifest['source'])=={'name','version','release_date','license','reference'}
        and all(isinstance(x,str) and x for x in manifest['source'].values()),'HASH_MISMATCH','Annotation provenance incomplete')
    ensure(isinstance(manifest['files'],list) and len(manifest['files'])==1,'HASH_MISMATCH','Expected single indexed annotation payload')
    row=manifest['files'][0]
    ensure(isinstance(row,dict) and set(row)=={'path','bytes','sha256'} and row['path']=='entries.json'
        and type(row['bytes']) is int and 0<row['bytes']<=16*1024**2,'HASH_MISMATCH','Invalid annotation inventory')
    size,digest=_hash_file(folder/'entries.json')
    ensure(size==row['bytes'] and digest==row['sha256'],'HASH_MISMATCH','Annotation bytes changed')
    for path in folder.rglob('*'):no_links(path)
    ensure({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}=={'entries.json','manifest.json'},
        'HASH_MISMATCH','Unregistered annotation data files')
    data=read_locked(folder/'entries.json',16*1024**2);entries=decode(data)
    ensure(isinstance(entries,list) and len(entries)<=500,'OUTPUT_INVALID','Invalid/big N09 development entry set')
    ids=[]
    for entry in entries:
        ensure(isinstance(entry,dict) and set(entry)=={'primaryAccession','entryType','organism','sequence','features','coordinate_spaces'},
            'OUTPUT_INVALID','Exact local UniProt-shaped entry required')
        ensure(isinstance(entry['primaryAccession'],str) and re.fullmatch('[A-Za-z0-9_.-]{1,80}',entry['primaryAccession']),
            'OUTPUT_INVALID','Invalid accession')
        ensure(entry['entryType'] in ('UniProtKB reviewed (Swiss-Prot)','UniProtKB unreviewed (TrEMBL)')
            and isinstance(entry['organism'],dict) and set(entry['organism'])=={'scientificName'}
            and isinstance(entry['organism']['scientificName'],str),'OUTPUT_INVALID','Invalid entry type/organism')
        ensure(isinstance(entry['sequence'],dict) and set(entry['sequence'])=={'value'},'OUTPUT_INVALID','Invalid sequence field')
        sequence(entry['sequence']['value'])
        ensure(isinstance(entry['features'],list) and len(entry['features'])<=500 and isinstance(entry['coordinate_spaces'],list)
            and len(entry['features'])==len(entry['coordinate_spaces']) and all(x in ('mature','parent') for x in entry['coordinate_spaces']),
            'OUTPUT_INVALID','Per-feature coordinate provenance required')
        for feature in entry['features']:
            ensure(isinstance(feature,dict) and set(feature)=={'type','description','location'} and isinstance(feature['type'],str)
                and isinstance(feature['description'],str) and len(feature['description'])<=2048
                and isinstance(feature['location'],dict) and set(feature['location'])=={'start','end'},'OUTPUT_INVALID','Invalid feature')
            for end in ('start','end'):
                loc=feature['location'][end]
                ensure(isinstance(loc,dict) and set(loc)=={'value','modifier'} and (loc['value'] is None or type(loc['value']) is int)
                    and loc['modifier'] in ('EXACT','UNKNOWN','UNSURE','OUTSIDE'),'OUTPUT_INVALID','Invalid feature location')
        ids.append(entry['primaryAccession'])
    ensure(len(ids)==len(set(ids)),'OUTPUT_INVALID','Duplicate accession in annotation package')
    return dict(database_id=manifest['database_id'],manifest_sha256=sha(raw),qualification=manifest['qualification'],
        source=manifest['source'],files=manifest['files']), {'input/annotation-manifest.json':raw,'input/annotation-entries.json':data}
