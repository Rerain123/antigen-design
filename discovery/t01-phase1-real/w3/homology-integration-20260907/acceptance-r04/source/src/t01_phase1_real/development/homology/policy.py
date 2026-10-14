"""N08 exact request, fixed assets and operator-owned local data registration."""
from pathlib import Path
import re

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked
from ..blast.policy import _safe_database_root, _hash_file
from .compute import ANCHOR, fasta

TOOL = 't01.real.homology'
NODE = 'N08'
SLOT = 't01p1r-homology-development-slot'
LIMITS = dict(memory=4*1024**3, cpus=2, cpuset='0-1', pids=128)
HERE = Path(__file__).parent
ASSETS = HERE/'assets.json'
IMAGE = decode(ASSETS.read_bytes())['image_id']
SOURCES = [REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902'/name for name in
           ('AgentA_SOP_v10.5_20260902.md','AgentA_SKILL_v10.5_20260902.md','AgentA_Schema_v10.5_20260902.md')]


def request(raw):
    value = decode(raw)
    expected = {'protein_sequence','user_sequence_id','organism_name','protein_name','database_id',
                'database_manifest_sha256','source_filter','group_by','sequence_weighting','query_range','timeout_seconds'}
    ensure(isinstance(value,dict) and set(value)==expected,'INVALID_REQUEST','Exact N08 request fields required')
    seq = value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]{9,20000}',seq),
           'INVALID_REQUEST','N08 requires exact uppercase AA20, 9..20000 aa')
    for key in ('user_sequence_id','organism_name','protein_name'):
        ensure(isinstance(value[key],str) and 0<len(value[key])<=512,'INVALID_REQUEST','Bounded nonempty '+key+' required')
    ensure(isinstance(value['database_id'],str) and re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',value['database_id']),
           'INVALID_REQUEST','Registered data ID required, never a path')
    ensure(isinstance(value['database_manifest_sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['database_manifest_sha256']),
           'INVALID_REQUEST','Exact manifest hash required')
    ensure(value['source_filter']=='wild_type' and value['group_by'] in ('subtype','host_species','both')
           and value['sequence_weighting']=='off','INVALID_REQUEST','N08 supports wild_type and unweighted confirmed rules only')
    span = value['query_range']
    ensure(span is None or isinstance(span,list) and len(span)==2 and all(type(x) is int for x in span)
           and 1<=span[0]<=span[1]<=len(seq),'INVALID_REQUEST','Invalid query range')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=900,
           'INVALID_REQUEST','Timeout must be 1..900 seconds')
    return value


def sequence_id(seq):
    return ANCHOR


def asset_receipt():
    return decode(read_locked(ASSETS,65536))


def verify_assets():
    receipt = asset_receipt()
    ensure(receipt['status']=='READY' and receipt['image_id']==IMAGE and receipt['platform']=={'os':'linux','architecture':'amd64'},
           'ASSET_MISSING','N08 assets not ready')
    for row in receipt['files']:
        raw = read_locked(REPO/row['path'],4*1024**2)
        ensure(sha(raw)==row['sha256'],'HASH_MISMATCH','N08 asset changed')
    return receipt


def registered_rules():
    return dict(id='w3-n08-s13-s15-v105-development',version='0.1.0',sha256=sha(encode(dict(
        sources={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in SOURCES},
        clauses=['S-13','S-14','S-15','R-06..R-11'],compute=sha((HERE/'compute.py').read_bytes()),
        unresolved='OI-030',scientific_consumption=False))))


def registered_profile():
    paths = [p for p in HERE.iterdir() if p.suffix in ('.py','.json') or p.name=='Dockerfile']
    paths += [HERE.parent/name for name in ('runtime.py','supervisor.py','docker.py','registry.py','contracts.py','cli.py')]
    return dict(id='w3-homology-local-development',version='0.1.0',sha256=sha(encode(dict(
        files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths},
        base_runtime=base_profile(),rules=registered_rules(),image=IMAGE,limits=LIMITS))))


def verify_database(root, body):
    root = _safe_database_root(root)
    folder = no_links(root/body['database_id'])
    ensure(folder.is_dir() and folder.resolve().parent==root,'ASSET_MISSING','N08 registered data directory missing')
    raw = read_locked(folder/'manifest.json',1024*1024)
    ensure(sha(raw)==body['database_manifest_sha256'],'HASH_MISMATCH','N08 manifest hash differs')
    manifest = decode(raw)
    ensure(isinstance(manifest,dict) and set(manifest)=={'schema_version','database_id','qualification','purpose','source','files'}
           and manifest['schema_version']=='0.1.0' and manifest['database_id']==body['database_id']
           and manifest['qualification'] in ('ENGINEERING_FIXTURE','TARGET_DATABASE_UNREVIEWED')
           and manifest['purpose']=='N08_HOMOLOG_COLLECTION','HASH_MISMATCH','N08 data purpose/identity differs')
    source = manifest['source']
    ensure(isinstance(source,dict) and set(source)=={'name','version','release_date','license','reference'}
           and all(isinstance(x,str) and x for x in source.values()),'HASH_MISMATCH','N08 data provenance incomplete')
    entries = manifest['files']
    ensure(isinstance(entries,list) and len(entries)==2,'HASH_MISMATCH','N08 requires FASTA plus annotation inventory')
    ensure({x.get('path') for x in entries}=={'sequences.fasta','annotations.json'},'HASH_MISMATCH','N08 inventory differs')
    for row in entries:
        ensure(set(row)=={'path','bytes','sha256'} and type(row['bytes']) is int and 0<row['bytes']<=16*1024**2,
               'HASH_MISMATCH','Invalid N08 file receipt')
        size,digest = _hash_file(folder/row['path'])
        ensure(size==row['bytes'] and digest==row['sha256'],'HASH_MISMATCH','N08 data bytes changed')
    for path in folder.rglob('*'): no_links(path)
    ensure({p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}==
           {'manifest.json','sequences.fasta','annotations.json'},'HASH_MISMATCH','Unregistered N08 files')
    try:
        seqs = fasta(read_locked(folder/'sequences.fasta',16*1024**2).decode('utf-8'))
    except (ValueError,UnicodeError) as exc:
        ensure(False,'OUTPUT_INVALID',str(exc))
    ensure(ANCHOR not in seqs and len(seqs)<=500 and all(len(s)<=20000 for s in seqs.values()),
           'OUTPUT_INVALID','N08 development data bound exceeded or reserved ID used')
    annotations = decode(read_locked(folder/'annotations.json',16*1024**2))
    required = {'id','organism_name','protein_name','source_label','header','serotype','subtype','genotype','host_species','independent_stratum'}
    ensure(isinstance(annotations,list) and len(annotations)==len(seqs),'OUTPUT_INVALID','Annotation count mismatch')
    ids = []
    for row in annotations:
        ensure(isinstance(row,dict) and set(row)==required and row['id'] in seqs
               and row['source_label'] in ('wild','vaccine','lab','unknown'),'OUTPUT_INVALID','Invalid N08 annotation')
        for key in required-{'id','source_label'}:
            ensure(row[key] is None and key in ('serotype','subtype','genotype','host_species','independent_stratum')
                   or isinstance(row[key],str) and 0<len(row[key])<=512,'OUTPUT_INVALID','Invalid annotation '+key)
        ids.append(row['id'])
    ensure(len(set(ids))==len(ids),'OUTPUT_INVALID','Duplicate annotation ID')
    return dict(mount_path=str(folder),database_id=manifest['database_id'],manifest_sha256=sha(raw),
                qualification=manifest['qualification'],purpose=manifest['purpose'],source=source,files=entries)
