import importlib.metadata as md
from pathlib import Path
import sys
import sysconfig
import platform
from ...common import REPO,decode,encode,ensure,sha,RuntimeFault

TOOL='t01.real.optimize_codons'
NODE='N16'
HERE=Path(__file__).parent
ASSETS=HERE/'assets'
PROFILE='ecoli-k12-w3110-kazusa-316407-v1'
MANIFEST_SHA256='b72cafa76edf117e5deb53fe014afe0d4c24bdbc5d9fbb9d47c6b7581789c6ae'
LINUX_MANIFEST_SHA256='d390f72037457cb6d730b8caa11e1b206c2d4d5814d5141149b0095c09cee5d1'
CODING='standard_fragment_no_added_start_or_stop'
PARAMETERS=dict(genetic_table=1,coding_policy=CODING,method='use_best_codon',
    initial_codons='highest_frequency_then_lexicographic',gc_min=.40,gc_max=.60,gc_scope='whole_fragment',
    avoid_sites=['BsaI','BpiI'],both_strands=True,seed=1601,max_random_iters=1000,
    additional_sites=None,cai_method=None,scientific_signoff=None)

def request(raw):
    b=decode(raw)
    required={'protein_sequence','user_sequence_id','expression_host','host_profile','coding_policy','input_kind','timeout_seconds'}
    ensure(isinstance(b,dict) and set(b)-{'candidate_source'}==required,'INVALID_REQUEST','Exact N16 engineering request required')
    seq=b['protein_sequence']
    ensure(isinstance(seq,str) and 1<=len(seq)<=1000 and set(seq)<=set('ACDEFGHIKLMNPQRSTVWY'),
        'INVALID_REQUEST','Protein must contain 1..1000 unambiguous uppercase amino acids, no stop or padding')
    ensure(isinstance(b['user_sequence_id'],str) and 1<=len(b['user_sequence_id'])<=128,'INVALID_REQUEST','Explicit input label required')
    ensure(b['input_kind'] in ('INDEPENDENT_ENGINEERING_SEQUENCE','VERIFIED_N15_ENGINEERING_CANDIDATE') and b['coding_policy']==CODING,
        'INVALID_REQUEST','Explicit engineering input kind required')
    if b['input_kind']=='VERIFIED_N15_ENGINEERING_CANDIDATE':
        from ..epitope_protection.policy import source
        binding=b.get('candidate_source')
        ensure(isinstance(binding,dict) and set(binding)=={'source','candidate_id'} and
            isinstance(binding['candidate_id'],str) and binding['source'] is not None,'INVALID_REQUEST','Exact N15 candidate lineage required')
        source(binding['source'])
    else:ensure('candidate_source' not in b,'INVALID_REQUEST','Independent DNA cannot claim candidate lineage')
    for key in ('expression_host','host_profile'):
        ensure(b[key] is None or isinstance(b[key],str) and 0<len(b[key])<=128,'INVALID_REQUEST','Use null for absent host/profile')
    ensure(b['expression_host'] is not None or b['host_profile'] is None,'INVALID_REQUEST','Missing host cannot select a profile')
    ensure(type(b['timeout_seconds']) is int and 1<=b['timeout_seconds']<=60,'INVALID_REQUEST','Deadline must be 1..60 seconds')
    return b

def sequence_id(seq):return 't01n16_'+sha(seq.encode())[:16]

def registered_rules():
    sop=REPO/'工作流设计/01-业务依据/抗原智能体_v10.5_修订版_20260902/AgentA_SOP_v10.5_20260902.md'
    return dict(id='w7-n16-explicit-fragment-rules',version='0.1.0',sha256=sha(encode(dict(parameters=PARAMETERS,authority=sha(sop.read_bytes())))))

def registered_profile():
    paths=list(HERE.glob('*.py'))+[ASSETS/'manifest.json']
    if sys.platform=='linux':paths.append(ASSETS/'manifest-linux.json')
    paths.extend(HERE.parent/n for n in ('runtime.py','registry.py','contracts.py','cli.py'))
    return dict(id='w7-n16-offline-chisel'+('-linux-x86_64' if sys.platform=='linux' else ''),version='0.1.0',sha256=sha(encode({p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths})))

def source_files(body):
    """Host absence is a real conditional skip, independent of tool installation."""
    if body['expression_host'] is None:return {},dict(state='SKIPPED_MISSING_EXPRESSION_HOST',table=None)
    ensure(body['expression_host']=='E.coli','UNSUPPORTED_EXPRESSION_HOST','Host not registered; an approved custom table/profile is required')
    ensure(body['host_profile']==PROFILE,'HOST_PROFILE_REQUIRED','Explicit supported strain/table profile required')
    try:
        linux=sys.platform=='linux'
        raw=(ASSETS/('manifest-linux.json' if linux else 'manifest.json')).read_bytes()
        ensure(sha(raw)==(LINUX_MANIFEST_SHA256 if linux else MANIFEST_SHA256),'HASH_MISMATCH','Registered dependency/table manifest changed')
        m=decode(raw);table=m['table']
        if linux:
            ensure(platform.machine()=='x86_64' and m['platform']=='linux-x86_64' and m['python']==[3,11],
                'DEPENDENCY_MISMATCH','Registered Linux x86_64 Python 3.11 environment required')
            ensure(m['windows_manifest_sha256']==MANIFEST_SHA256 and sha((ASSETS/'manifest.json').read_bytes())==MANIFEST_SHA256,
                'HASH_MISMATCH','Original codon table provenance changed')
        table_raw=(ASSETS/table['file']).read_bytes()
    except FileNotFoundError as exc:raise RuntimeFault('CODON_TABLE_MISSING','Registered local table/manifest missing') from exc
    ensure(len(table_raw)==table['size_bytes'] and sha(table_raw)==table['sha256'],'HASH_MISMATCH','Local codon table changed')
    ensure(sys.version_info[:2]==(3,11),'DEPENDENCY_MISMATCH','N16 requires Python 3.11')
    site=Path(sysconfig.get_paths()['purelib']).resolve()
    for name,entry in m['packages'].items():
        try:version=md.version(name)
        except md.PackageNotFoundError as exc:raise RuntimeFault('DEPENDENCY_MISSING',name) from exc
        ensure(version==entry['version'],'DEPENDENCY_MISMATCH',name+' version changed')
        for item in entry['files']:
            path=(site/item['path']).resolve()
            ensure(path.is_relative_to(site),'FORBIDDEN','Dependency path escapes installation')
            try:data=path.read_bytes()
            except OSError as exc:raise RuntimeFault('DEPENDENCY_MISSING',item['path']) from exc
            ensure(len(data)==item['size_bytes'] and sha(data)==item['sha256'],'DEPENDENCY_MISMATCH','Dependency content changed: '+item['path'])
    return {'input/codon-table.csv':table_raw,'input/dependency-manifest.json':raw},dict(state='VERIFIED_LOCAL_TABLE_AND_DEPENDENCIES',
        table=table,dependency_manifest_sha256=sha(raw),versions={k:v['version'] for k,v in m['packages'].items()})
