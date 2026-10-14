"""N05 admission and asset readiness without inventing an unobserved CLI."""
import hashlib
import re
from functools import lru_cache
from pathlib import Path

from ...common import REPO, decode, encode, ensure, profile as base_profile, sha
from ...files import no_links, read_locked

TOOL='t01.real.netmhc'
NODE='N05'
SLOT='t01p1r-netmhc-development-slot'
LIMITS=dict(memory=4*1024**3,cpus=4,cpuset='0-3',pids=128)
MIN_AA=15
MAX_AA=20000
MHC_I_LENGTHS=(8,9,10,11,12,13,14)
MHC_II_LENGTHS=(15,)
MAX_CHANNEL_ROWS=150000
HERE=Path(__file__).parent
ASSETS=HERE/'assets.json'
PACKAGE=REPO/'var/t01-phase1-real/tool-assets/netmhc-pinned'
IMAGE=decode(ASSETS.read_bytes())['image_id']
ALLELE=re.compile(r'[A-Za-z0-9][A-Za-z0-9*_.:-]{0,127}')


@lru_cache(maxsize=2)
def allele_inventory(kind):
    """Return package CLI names and the corresponding native output names."""
    ensure(kind in ('mhc_i','mhc_ii'),'INVALID_REQUEST','Unknown MHC channel')
    relative=('metadata/netMHCpan-4.2/data/allelenames' if kind=='mhc_i'
        else 'metadata/netMHCIIpan-4.3/data/allele.list')
    lines=read_locked(no_links(PACKAGE/relative),1024*1024).decode('ascii').splitlines()
    pairs={}
    for line in lines:
        fields=line.split()
        ensure(len(fields)==(2 if kind=='mhc_i' else 1),'HASH_MISMATCH','Malformed package allele inventory')
        cli,native=fields[0],fields[-1]
        ensure(cli not in pairs or pairs[cli]==native,'HASH_MISMATCH','Conflicting package allele inventory')
        pairs[cli]=native
    ensure(pairs,'ASSET_MISSING','Empty package allele inventory')
    return pairs


def native_output_alleles(kind,alleles):
    inventory=allele_inventory(kind)
    return {name for allele in alleles for name in (allele,inventory.get(allele)) if name}


def _alleles(value,name,maximum,minimum=1):
    ensure(isinstance(value,list) and minimum<=len(value)<=maximum and all(isinstance(v,str) and ALLELE.fullmatch(v) for v in value),
        'INVALID_REQUEST',f'{name} requires 1..{maximum} explicit bounded allele names')
    ensure(len(set(value))==len(value),'INVALID_REQUEST',f'{name} must not contain duplicates')
    return value


def request(raw):
    value=decode(raw)
    expected={'protein_sequence','user_sequence_id','host_species','mhc_i_alleles','mhc_ii_alleles','timeout_seconds'}
    pan_expected=(expected-{'mhc_i_alleles','mhc_ii_alleles'})|{'panel_mode','panel_manifest_sha256'}
    ensure(isinstance(value,dict) and set(value) in (expected,pan_expected,expected|{'host_panel_sha256'}),'INVALID_REQUEST','Exact N05 explicit allele or registered panel fields required')
    seq=value['protein_sequence']
    ensure(isinstance(seq,str) and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+',seq) and MIN_AA<=len(seq)<=MAX_AA,
        'INVALID_REQUEST','NetMHC development requires exact uppercase AA20, 15..20000 aa; no normalization')
    ensure(isinstance(value['user_sequence_id'],str) and len(value['user_sequence_id'])<=512,
        'INVALID_REQUEST','User sequence ID must be bounded metadata')
    ensure(isinstance(value['host_species'],str) and 1<=len(value['host_species'])<=200 and value['host_species']==value['host_species'].strip(),
        'INVALID_REQUEST','Host species must be nonempty bounded metadata')
    if set(value)==pan_expected:
        from .pan import MODE, manifest, batches
        from . import host_panel
        ensure(value['panel_mode'] in (MODE,host_panel.MODE),'INVALID_REQUEST','Unknown panel mode')
        panel=host_panel.manifest(value['host_species']) if value['panel_mode']==host_panel.MODE else manifest()
        ensure(value['panel_manifest_sha256']==panel['sha256'],
            'HASH_MISMATCH','Pan fallback must bind the full pinned package inventory')
        ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=28800,
            'INVALID_REQUEST','Pan controller deadline must be 1..28800 seconds')
        batches(seq,panel)
        return value
    host_panel_value=None
    if 'host_panel_sha256' in value:
        from .host_panel import manifest as host_manifest
        host_panel_value=host_manifest(value['host_species'])
        ensure(value['host_panel_sha256']==host_panel_value['sha256'],'HASH_MISMATCH','Host child panel changed')
        for kind in ('mhc_i','mhc_ii'):
            names=value[kind+'_alleles'];allowed=host_panel_value['channels'][kind]['alleles']
            ensure(isinstance(names,list) and set(names)<=set(allowed) and (bool(names) or not allowed),
                   'INVALID_REQUEST','Host child allele subset or missing channel differs')
    mhc_i=_alleles(value['mhc_i_alleles'],'mhc_i_alleles',20,0 if host_panel_value else 1)
    mhc_ii=_alleles(value['mhc_ii_alleles'],'mhc_ii_alleles',15,0 if host_panel_value else 1)
    ensure(mhc_i or mhc_ii,'INVALID_REQUEST','At least one channel is required')
    ensure(all(name in allele_inventory('mhc_i') for name in mhc_i),'INVALID_REQUEST',
        'mhc_i_alleles contains a name absent from the package-local NetMHCpan inventory')
    ensure(all(name in allele_inventory('mhc_ii') for name in mhc_ii),'INVALID_REQUEST',
        'mhc_ii_alleles contains a name absent from the package-local NetMHCIIpan inventory')
    i_rows=len(mhc_i)*sum(max(0,len(seq)-length+1) for length in MHC_I_LENGTHS)
    ii_rows=len(mhc_ii)*sum(max(0,len(seq)-length+1) for length in MHC_II_LENGTHS)
    ensure(i_rows<=MAX_CHANNEL_ROWS and ii_rows<=MAX_CHANNEL_ROWS,'INVALID_REQUEST',
        'Requested sequence/allele workload exceeds the bounded native output envelope')
    ensure(type(value['timeout_seconds']) is int and 1<=value['timeout_seconds']<=900,
        'INVALID_REQUEST','Execution deadline must be 1..900 seconds')
    return value


def sequence_id(seq):
    """Short ID avoids native Identity truncation while full SHA remains in binding."""
    return 't01s_'+sha(seq.encode())[:10]


def asset_receipt():
    return decode(read_locked(ASSETS,65536))


def verify_assets():
    receipt=asset_receipt()
    ensure(receipt.get('status')=='READY' and receipt.get('qualification')=='LOCAL_ACADEMIC_DEVELOPMENT'
        and isinstance(receipt.get('image_id'),str) and re.fullmatch(r'sha256:[0-9a-f]{64}',receipt['image_id'])
        and receipt.get('files'),'ASSET_MISSING',
        'NetMHCpan 4.2 and NetMHCIIpan 4.3 licensed local packages/image are not registered; see netmhc/assets.json')
    ensure(IMAGE==receipt['image_id'],'HASH_MISMATCH','NetMHC image identity changed after code import')
    ensure(receipt.get('package_root')==PACKAGE.relative_to(REPO).as_posix(),'HASH_MISMATCH','NetMHC package root changed')
    archives=receipt.get('archive_sha256')
    ensure(isinstance(archives,dict) and set(archives)=={'mhc_i','mhc_ii'}
        and all(isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) for value in archives.values()),
        'ASSET_MISSING','Both original NetMHC archive hashes are required')
    original=receipt.get('original_archives')
    ensure(isinstance(original,list) and len(original)==2,'ASSET_MISSING','Both original archive receipts are required')
    for entry in original:
        ensure(isinstance(entry,dict) and set(entry)=={'path','bytes','sha256'} and entry['sha256'] in archives.values(),
            'HASH_MISMATCH','Invalid original archive receipt')
        path=no_links(PACKAGE/entry['path'])
        ensure(path.is_file() and path.stat().st_size==entry['bytes'],'ASSET_MISSING','Missing original NetMHC archive')
    license_record=receipt.get('license_record')
    ensure(isinstance(license_record,dict) and license_record.get('kind')=='DTU_ACADEMIC'
        and isinstance(license_record.get('reference'),str) and license_record['reference'],
        'ASSET_MISSING','NetMHC academic licence record is missing')
    components=receipt.get('components')
    ensure(isinstance(components,dict) and set(components)=={'mhc_i','mhc_ii'},'HASH_MISMATCH','NetMHC component receipt is incomplete')
    expected={'mhc_i':r'4\.2(?:\D|$)','mhc_ii':r'4\.3(?:\D|$)'}
    listed={entry.get('path') for entry in receipt['files'] if isinstance(entry,dict)}
    for name,pattern in expected.items():
        item=components[name]
        ensure(isinstance(item,dict) and re.search(pattern,str(item.get('observed_version','')))
            and isinstance(item.get('executable_path'),str) and item['executable_path'].startswith('/tools/src/')
            and re.fullmatch('[0-9a-f]{64}',str(item.get('executable_sha256','')))
            and item.get('allele_inventory_path') in listed
            and item.get('full_fasta_verified') is True and item.get('position_base')==1,
            'ASSET_MISSING',f'{name} package-local CLI/allele/FASTA/Pos verification is incomplete')
    for entry in receipt['files']:
        ensure(isinstance(entry,dict) and set(entry)=={'path','bytes','sha256'} and isinstance(entry['path'],str)
            and entry['path'] and not Path(entry['path']).is_absolute() and '..' not in Path(entry['path']).parts
            and type(entry['bytes']) is int and entry['bytes']>=0 and re.fullmatch('[0-9a-f]{64}',entry['sha256']),
            'HASH_MISMATCH','Invalid NetMHC asset manifest entry')
        path=no_links(PACKAGE/entry['path'])
        ensure(path.is_file() and path.stat().st_size==entry['bytes'],'ASSET_MISSING','Missing pinned NetMHC asset: '+entry['path'])
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            while block:=stream.read(8*1024**2):digest.update(block)
        ensure(digest.hexdigest()==entry['sha256'],'HASH_MISMATCH','Changed pinned NetMHC asset: '+entry['path'])
    return receipt


def registered_profile():
    from ..expert_feedback import authority
    shared=HERE.parent
    paths=[p for p in HERE.rglob('*') if p.suffix in ('.py','.json')]
    paths += [shared/name for name in ['registry.py','runtime.py','supervisor.py','docker.py','contracts.py','cli.py']]
    paths += [REPO/'scripts/t01_runtime.py',REPO/'scripts/t01_development_supervisor.py']
    receipt=decode(ASSETS.read_bytes())
    return dict(id='w2-netmhc42-netmhciipan43-local-development',version='20261009-v1',sha256=sha(encode(dict(
        expert_feedback=authority(),
        files={p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in sorted(paths)},base_runtime=base_profile(),
        asset_status=receipt['status'],image=receipt['image_id'],limits=LIMITS,aa_min=MIN_AA,aa_max=MAX_AA,
        mhc_i_lengths=MHC_I_LENGTHS,mhc_ii_lengths=MHC_II_LENGTHS,max_channel_rows=MAX_CHANNEL_ROWS,
        allele_mode='explicit_or_A1_section7_complete_package_pan_batches',
        scientific_consumption=False))))
