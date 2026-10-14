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
NODES['prediction'] = 'N01'
NODES['wt_msa'] = 'N12'
from .m1 import KINDS, TAIL, FULL_TAIL
NODES.update({name: node for name, (_, node) in KINDS.items()})
NODES['preselection'] = 'N12'
NODES['design_inputs'] = 'N11'
from .design_rounds import NAMES as RETRY_NAMES
NODES.update({n:'N11' if n.endswith('_design') else 'N12' for n in RETRY_NAMES})
from .validation import NAMES as VALIDATION_NAMES, CHILDREN
NODES.update({n:'N12' for n in (*VALIDATION_NAMES,*CHILDREN)})
from .candidate_developability import ORDER as N10_ORDER
NODES.update({n:'N10' for n in N10_ORDER})
from .candidate_dna import ORDER as DNA_ORDER
NODES.update({n:'N16' for n in DNA_ORDER})
from .revision_controller import CHILDREN as REVISION_CHILDREN, STAGE as REVISION_STAGE
NODES[REVISION_STAGE]='N12'
NODES.update({n:'N11' if tool=='proteinmpnn' else 'N14' if tool=='foldx' else 'N12' for n,tool in REVISION_CHILDREN.items()})
from .revision_v2_runtime import CHILDREN as V2_CHILDREN
NODES.update({n:'N14' if tool=='foldx' else 'N10' if tool=='developability' else 'N13' for n,tool in V2_CHILDREN.items()})


def order(body):
    from .engineering import enabled
    from .revision_controller import enabled as revised
    if revised(body):
        nodes=ORDER[:11]+('design_inputs',REVISION_STAGE,'codon','wt_foldx','wt_thermompnn','wt_reference','local_delivery')
        return ('prediction',)+nodes if body.get('prediction') is not None else nodes
    if enabled(body):
        nodes = ORDER[:11] + ('design_inputs', 'design') + FULL_TAIL[:2] + ('validation',) + RETRY_NAMES + FULL_TAIL[2:]
        index=nodes.index('stability');nodes=nodes[:index]+N10_ORDER+nodes[index:]
        index=nodes.index('codon');nodes=nodes[:index]+DNA_ORDER+nodes[index+1:]
        return ('prediction',) + nodes if body.get('prediction') is not None else nodes
    nodes = ORDER[:12] + TAIL if body.get('m1_test') is not None else ORDER
    return ('prediction',) + nodes if body.get('prediction') is not None else nodes

def request(raw):
    ensure(isinstance(raw, bytes) and len(raw) <= 65536, 'INVALID_REQUEST', 'Bounded workflow JSON required')
    b = decode(raw)
    required = {'protein_sequence','user_sequence_id','host_species','expression_host','organism',
                'structure','analysis','reuse_jobs','timeout_seconds'}
    ensure(isinstance(b, dict) and (set(b) - {'prediction','design_context','m1_test','engineering_design','stability_scan','revision_config','interaction_policy'}) in
           (required, required | {'structure_artifact','configuration'}),
           'INVALID_REQUEST', 'Exact workflow fields required')
    from ..wt_draft.policy import design_context
    b['design_context']=design_context(b.get('design_context'))
    s = b['protein_sequence']
    ensure(isinstance(s,str) and 9 <= len(s) <= 2000 and set(s) <= set('ACDEFGHIKLMNPQRSTVWY'),
           'INVALID_REQUEST', 'Workflow requires an exact 9..2000 AA20 sequence')
    if 'stability_scan' in b:
        from .stability_scope import region
        ensure(isinstance(b['stability_scan'],dict) and set(b['stability_scan'])=={'scan_region'},
               'INVALID_REQUEST','Explicit backend scan region required')
        region(b['stability_scan']['scan_region'],len(s))
    for name in ('user_sequence_id','host_species'):
        ensure(isinstance(b[name],str) and 0 < len(b[name]) <= 128, 'INVALID_REQUEST', 'Explicit sequence label and host required')
    for name in ('expression_host','organism'):
        ensure(b[name] is None or isinstance(b[name],str) and 0 < len(b[name]) <= 128,
               'INVALID_REQUEST', 'Explicit name or null required')
    maximum = 28800
    ensure(type(b['timeout_seconds']) is int and 1 <= b['timeout_seconds'] <= maximum,
           'INVALID_REQUEST', f'Workflow deadline must be 1..{maximum} seconds')
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
    if 'engineering_design' in b:
        from .engineering import MODE
        ensure(b['engineering_design'] == MODE and b.get('m1_test') is None and not b['reuse_jobs'] and len(s) <= 999,
               'INVALID_REQUEST', 'Backend evidence mode requires fresh inputs and excludes supplied masks')
    if 'revision_config' in b:
        from .revision_contract import config
        ensure(b.get('engineering_design')=='BACKEND_EVIDENCE_V1','INVALID_REQUEST','Revision requires registered same-run backend permissions')
        config(b['revision_config'])
    if 'interaction_policy' in b:
        ensure(b.get('engineering_design')=='BACKEND_EVIDENCE_V1' and
               b['interaction_policy']=='PREAUTHORIZED_T4_CONTINUE_WITH_WARNING_V1',
               'INVALID_REQUEST','Unknown unattended workflow policy')
    if b.get('m1_test') is not None:
        opt=b['m1_test']
        ensure(len(s)<=1000,'INVALID_REQUEST','M1 ProteinMPNN supports at most 1000 residues')
        ensure(isinstance(opt,dict) and set(opt)=={'constraints','n_designs','sampling_temperature','seed','timeout_seconds'},
               'INVALID_REQUEST','Explicit M1 ProteinMPNN configuration required')
        ensure(not b['reuse_jobs'],'INVALID_REQUEST','M1 requires fresh same-run upstream results')
        from ..proteinmpnn.policy import design_options
        design_options(opt,s)
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
    if b.get('prediction') is not None:
        opt = b['prediction']
        ensure(isinstance(opt,dict) and set(opt)=={'engine','seed','timeout_seconds'}
               and opt['engine'] in ('esmfold2','af3')
               and b['structure'] is None and 'structure' not in b['reuse_jobs'],
               'INVALID_REQUEST', 'Explicit local prediction excludes uploaded/reused structure')
        from .revision_structure import SINGLE_MODEL_POLICY
        roles=b.get('revision_config',{}).get('policies',{}).get('model_roles') or {}
        if roles.get('model_role_policy')==SINGLE_MODEL_POLICY:
            ensure(opt['engine']=='af3','INVALID_REQUEST','Current single-engine policy requires AF3 for WT prediction')
        if opt['engine']=='esmfold2':
            from ..esmfold2 import policy as prediction
        else:
            from ..af3 import policy as prediction
        prediction.request(encode(dict(protein_sequence=s,user_sequence_id=b['user_sequence_id'],host_species=b['host_species'],
                                       seed=opt['seed'],timeout_seconds=opt['timeout_seconds'])))
    return b

def sequence_id(s): return 't01flow_' + sha(s.encode())[:16]

def registered_rules():
    return dict(id='local-workflow-r57-routing-closed-release',version='0.3.0',sha256=sha(encode(dict(
        order=ORDER,optional_prediction=('esmfold2','af3'),business_routing='R57_TRI_STATE',
        internal_test='EXPLICIT_M1_SAME_RUN_P1_P3',m1_order=ORDER[:12]+TAIL,
        engineering_design='BACKEND_EVIDENCE_V1',engineering_order=order(dict(engineering_design='BACKEND_EVIDENCE_V1')),
        automatic_scientific_routing=False,scientific_release_gate='CLOSED',md='EXCLUDED'))))

def registered_profile():
    paths = sorted((Path(__file__).parent.parent).rglob('*.py'))
    return dict(id='local-workflow-controller',version='0.2.0',sha256=sha(encode(
        {p.relative_to(REPO).as_posix():sha(p.read_bytes()) for p in paths})))
