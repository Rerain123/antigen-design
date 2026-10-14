from pathlib import Path
from ...common import REPO, decode, encode, ensure, sha

TOOL = 't01.real.local_workflow'
NODE = 'N18'
OPTIONS = ('topology', 'blast', 'bepipred', 'netmhc', 'homology', 'domains', 'developability')
ORDER = ('structure', 'topology', 'blast', 'bepipred', 'netmhc', 'epitope_map',
         'glycosylation', 'homology', 'domains', 'developability', 'wt_draft',
         'design', 'rescore', 'protection', 'stability', 'variant_report', 'codon',
         'wt_reference', 'local_delivery')
NODES = dict(zip(ORDER, ('N01','N02','N03','N04','N05','N06','N07','N08','N09','N10',
                        'N18','N11','N12','N13','N14','N15','N16','N17','N18')))

def request(raw):
    ensure(isinstance(raw, bytes) and len(raw) <= 65536, 'INVALID_REQUEST', 'Bounded workflow JSON required')
    b = decode(raw)
    required = {'protein_sequence','user_sequence_id','host_species','expression_host','organism',
                'structure','analysis','reuse_jobs','timeout_seconds'}
    ensure(isinstance(b, dict) and set(b) in (required, required | {'structure_artifact','configuration'}),
           'INVALID_REQUEST', 'Exact workflow fields required')
    s = b['protein_sequence']
    ensure(isinstance(s,str) and 9 <= len(s) <= 2000 and set(s) <= set('ACDEFGHIKLMNPQRSTVWY'),
           'INVALID_REQUEST', 'Workflow requires an exact 9..2000 AA20 sequence')
    for name in ('user_sequence_id','host_species'):
        ensure(isinstance(b[name],str) and 0 < len(b[name]) <= 128, 'INVALID_REQUEST', 'Explicit sequence label and host required')
    for name in ('expression_host','organism'):
        ensure(b[name] is None or isinstance(b[name],str) and 0 < len(b[name]) <= 128,
               'INVALID_REQUEST', 'Explicit name or null required')
    ensure(type(b['timeout_seconds']) is int and 1 <= b['timeout_seconds'] <= 7200,
           'INVALID_REQUEST', 'Workflow deadline must be 1..7200 seconds')
    ensure(isinstance(b['analysis'],dict) and set(b['analysis']) == set(OPTIONS),
           'INVALID_REQUEST', 'All analysis options required; null explicitly disables a branch')
    forbidden = {'protein_sequence','user_sequence_id','host_species','upstream','structure_input','topology_input'}
    for option in b['analysis'].values():
        ensure(option is None or isinstance(option,dict) and not (set(option) & forbidden),
               'INVALID_REQUEST', 'Analysis parameters cannot override workflow identity or upstream bindings')
    from .. import policy as topology
    from ..bepipred import policy as bepipred
    for name,maximum in [('topology',topology.MAX_AA),('bepipred',bepipred.MAX_AA)]:
        if b['analysis'][name] is not None:
            ensure(len(s)<=maximum,'INVALID_REQUEST',
                   f'Workflow {name} input exceeds its current verified support cap of {maximum} aa; no truncation is performed')
    ensure(isinstance(b['reuse_jobs'],dict) and set(b['reuse_jobs']) <= {'structure','variant_report','wt_reference'},
           'INVALID_REQUEST', 'Only explicit historical structure/report/reference reuse is supported')
    import re
    ensure(all(isinstance(j,str) and re.fullmatch('t01p1r-job-[0-9a-f]{32}',j) for j in b['reuse_jobs'].values()),
           'INVALID_REQUEST', 'Registered historical job IDs required')
    ensure(not (b['structure'] is not None and 'structure' in b['reuse_jobs']),
           'INVALID_REQUEST', 'New structure and reused structure are mutually exclusive')
    if b['structure'] is not None:
        from ..structure import policy
        ensure(isinstance(b['structure'],dict),'INVALID_REQUEST','Structure metadata must be an object')
        policy.metadata(encode(dict(b['structure'],protein_sequence=s,host_species=b['host_species'])))
        ensure(not (set(b['structure']) & {'protein_sequence','host_species','structure_artifact'}),
               'INVALID_REQUEST', 'Structure identity belongs to workflow')
    return b

def sequence_id(s): return 't01flow_' + sha(s.encode())[:16]

def registered_rules():
    return dict(id='local-workflow-closed-gate',version='0.1.0',sha256=sha(encode(dict(order=ORDER,gate='CLOSED',md='EXCLUDED'))))

def registered_profile():
    paths = sorted((Path(__file__).parent.parent).rglob('*.py'))
    return dict(id='local-workflow-controller',version='0.1.0',sha256=sha(encode(
        {p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths})))
