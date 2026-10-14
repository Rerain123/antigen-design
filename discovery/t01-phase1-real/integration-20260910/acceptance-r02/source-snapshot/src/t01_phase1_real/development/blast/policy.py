"""N03 request, engine and operator-configured database identity policy."""
import hashlib
import os
from pathlib import Path
import re

from ...common import REPO, RuntimeFault, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked

TOOL='t01.real.blast'
NODE='N03'
SLOT='t01p1r-blast-development-slot'
LIMITS=dict(memory=2*1024**3,cpus=2,cpuset='0-1',pids=64)
MIN_AA=9
MAX_AA=20000
MAX_HSPS=5000
HERE=Path(__file__).parent
ASSETS=HERE/'assets.json'
IMAGE=decode(ASSETS.read_bytes())['image_id']
DATABASE_ID=re.compile(r'[a-z0-9][a-z0-9._-]{0,63}')
HEX64=re.compile(r'[0-9a-f]{64}')


def request(raw):
    value=decode(raw)
    expected={'protein_sequence','user_sequence_id','database_id','database_manifest_sha256','thresholds','timeout_seconds'}
    ensure(isinstance(value,dict) and set(value)==expected,'INVALID_REQUEST',
        'Exact N03 sequence, alias, database identity, thresholds and timeout fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and MIN_AA<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','BLAST development requires exact uppercase AA20, 9..20000 aa; no normalization')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','User sequence ID must be bounded metadata')
    ensure(isinstance(value['database_id'],str) and DATABASE_ID.fullmatch(value['database_id']),
        'INVALID_REQUEST','Database ID must be a bounded registered identifier, not a path')
    ensure(isinstance(value['database_manifest_sha256'],str) and HEX64.fullmatch(value['database_manifest_sha256']),
        'INVALID_REQUEST','Exact database manifest SHA-256 is required')
    thresholds=value['thresholds']
    ensure(isinstance(thresholds,dict) and set(thresholds)=={'identity_percent_min','query_coverage_percent_min'},
        'INVALID_REQUEST','Exact identity and query coverage thresholds are required')
    for name in ('identity_percent_min','query_coverage_percent_min'):
        number=thresholds[name]
        ensure(type(number) in (int,float) and 0<=number<=100,'INVALID_REQUEST',name+' must be numeric 0..100')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=900,
        'INVALID_REQUEST','Execution deadline must be 1..900 seconds')
    return value


def sequence_id(seq):
    return 't01b_'+sha(seq.encode())[:12]


def asset_receipt():
    return decode(read_locked(ASSETS,65536))


def verify_assets():
    receipt=asset_receipt()
    ensure(receipt.get('status')=='READY' and receipt.get('qualification')=='LOCAL_ENGINE_DEVELOPMENT'
        and receipt.get('image_id')==IMAGE and HEX64.fullmatch(IMAGE.removeprefix('sha256:'))
        and receipt.get('image_reference')=='ncbi/blast:2.17.0'
        and receipt.get('observed_versions')=={'blastp':'blastp: 2.17.0+','makeblastdb':'makeblastdb: 2.17.0+'}
        and receipt.get('platform')=={'os':'linux','architecture':'amd64'} and receipt.get('files')==[],
        'ASSET_MISSING','Pinned NCBI BLAST+ 2.17.0 engine receipt is incomplete')
    ensure(receipt.get('license_record',{}).get('database_licence_inferred') is False,
        'HASH_MISMATCH','Engine receipt must not infer a database licence')
    return receipt


def _safe_database_root(root):
    ensure(root is not None,'ASSET_MISSING','N03 database root is not configured in the execution environment')
    root=Path(root)
    ensure(root.is_absolute() and not str(root).startswith('\\\\'),'FORBIDDEN','BLAST database root must be an absolute local path')
    root=no_links(root)
    ensure(root.is_dir(),'ASSET_MISSING','Configured BLAST database root is unavailable')
    return root.resolve()


def _hash_file(path):
    path=no_links(path);digest=hashlib.sha256();size=0
    try:
        with path.open('rb') as stream:
            ensure(os.fstat(stream.fileno()).st_nlink==1,'FORBIDDEN','Database file has ambiguous or multiple links')
            while block:=stream.read(8*1024**2):digest.update(block);size+=len(block)
    except OSError as exc:
        raise RuntimeFault('ASSET_MISSING','Cannot read registered BLAST database file') from exc
    no_links(path)
    return size,digest.hexdigest()


def verify_database(database_root,body):
    """Verify every declared source/index byte and return a mount receipt without trusting request paths."""
    root=_safe_database_root(database_root);folder=no_links(root/body['database_id'])
    ensure(folder.resolve().parent==root and folder.is_dir(),'ASSET_MISSING','Registered BLAST database ID is unavailable')
    manifest_path=no_links(folder/'manifest.json')
    ensure(manifest_path.is_file(),'ASSET_MISSING','Registered BLAST database manifest is missing')
    raw=read_locked(manifest_path,1024*1024)
    ensure(sha(raw)==body['database_manifest_sha256'],'HASH_MISMATCH','BLAST database manifest identity differs')
    manifest=decode(raw)
    expected={'schema_version','database_id','qualification','purpose','created_at','source','blast','files'}
    ensure(isinstance(manifest,dict) and set(manifest)==expected and manifest['schema_version']=='0.1.0'
        and manifest['database_id']==body['database_id']
        and manifest['qualification'] in ('ENGINEERING_FIXTURE','TARGET_DATABASE_UNREVIEWED'),
        'HASH_MISMATCH','BLAST database manifest contract differs')
    ensure(isinstance(manifest['purpose'],str) and manifest['purpose'] and isinstance(manifest['created_at'],str)
        and manifest['created_at'],'HASH_MISMATCH','Database purpose/time must be recorded')
    source=manifest['source']
    ensure(isinstance(source,dict) and set(source)=={'name','version','release_date','license','reference'}
        and all(isinstance(source[k],str) and source[k] for k in source),
        'HASH_MISMATCH','Database source, version, date, licence and reference are required')
    blast=manifest['blast']
    ensure(isinstance(blast,dict) and set(blast)=={'db_prefix','dbtype','blastdb_version','title','sequence_count',
        'makeblastdb_version','builder_identity'} and isinstance(blast['db_prefix'],str)
        and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}',blast['db_prefix'])
        and '..' not in Path(blast['db_prefix']).parts and not Path(blast['db_prefix']).is_absolute()
        and blast['dbtype']=='prot' and blast['blastdb_version'] in (4,5)
        and isinstance(blast['title'],str) and blast['title'] and type(blast['sequence_count']) is int
        and blast['sequence_count']>=1 and isinstance(blast['makeblastdb_version'],str) and blast['makeblastdb_version']
        and isinstance(blast['builder_identity'],str) and blast['builder_identity'],
        'HASH_MISMATCH','BLAST database build identity differs')
    if manifest['qualification']=='ENGINEERING_FIXTURE':
        ensure(blast['makeblastdb_version']=='makeblastdb: 2.17.0+' and blast['builder_identity']==IMAGE,
            'HASH_MISMATCH','Engineering database must be built by the pinned engine')
    entries=manifest['files']
    ensure(isinstance(entries,list) and 4<=len(entries)<=128,'HASH_MISMATCH','Database file inventory is incomplete or unbounded')
    observed=[];roles=[];paths=[]
    for entry in entries:
        ensure(isinstance(entry,dict) and set(entry)=={'path','role','bytes','sha256'}
            and isinstance(entry['path'],str) and entry['path'] and not Path(entry['path']).is_absolute()
            and '..' not in Path(entry['path']).parts and entry['role'] in ('source_fasta','index')
            and type(entry['bytes']) is int and entry['bytes']>0 and isinstance(entry['sha256'],str)
            and HEX64.fullmatch(entry['sha256']),'HASH_MISMATCH','Invalid database file manifest entry')
        path=no_links(folder/entry['path'])
        ensure(path.resolve().is_relative_to(folder.resolve()) and path.is_file(),'ASSET_MISSING','Database file is missing: '+entry['path'])
        size,digest=_hash_file(path)
        ensure(size==entry['bytes'] and digest==entry['sha256'],'HASH_MISMATCH','Database file changed: '+entry['path'])
        observed.append(dict(entry));roles.append(entry['role']);paths.append(entry['path'])
    ensure(len(paths)==len(set(paths)) and roles.count('source_fasta')==1 and roles.count('index')>=3,
        'HASH_MISMATCH','Database requires one source FASTA and at least three unique index files')
    prefix=blast['db_prefix']
    ensure(all(any(path==prefix+suffix for path in paths) for suffix in ('.phr','.pin','.psq')),
        'HASH_MISMATCH','Protein BLAST core index set (.phr/.pin/.psq) is incomplete')
    actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
    ensure(actual==set(paths)|{'manifest.json'},'HASH_MISMATCH','Database directory inventory differs from its manifest')
    return dict(mount_path=str(folder),database_id=manifest['database_id'],manifest_sha256=sha(raw),
        qualification=manifest['qualification'],purpose=manifest['purpose'],source=source,blast=blast,files=observed)


def registered_profile():
    shared=HERE.parent
    paths=[p for p in HERE.rglob('*') if p.suffix in ('.py','.json')]
    paths += [shared/name for name in ['registry.py','runtime.py','supervisor.py','docker.py','contracts.py','cli.py']]
    paths += [REPO/'scripts/t01_runtime.py',REPO/'scripts/t01_development_supervisor.py']
    receipt=decode(ASSETS.read_bytes())
    return dict(id='w2-blastp217-local-development',version='0.1.0',sha256=sha(encode(dict(
        files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(paths)},base_runtime=base_profile(),
        image=receipt['image_id'],limits=LIMITS,aa_min=MIN_AA,aa_max=MAX_AA,max_hsps=MAX_HSPS,
        database_binding='operator_configured_root_plus_id_plus_manifest_sha256',scientific_consumption=False))))
