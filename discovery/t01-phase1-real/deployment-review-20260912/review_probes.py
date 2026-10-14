"""Read-only review probes. API objects are fixtures, not cluster evidence."""
from pathlib import Path
import ast
import copy
import hashlib
import importlib.util
import itertools
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from t01_phase1_real.deployment.kubernetes import scientific_network_policy, scientific_job_spec, control_plane_documents
from t01_phase1_real.deployment.launcher import Launcher, ClusterError

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

out = {'evidence_kind': 'READ_ONLY_SOURCE_AUDIT_AND_API_CONTRACT_FIXTURES', 'cluster_contacted': False}
manifest = json.loads((ROOT / 'legacy/project-history/expert/EXPERT_V10_5_REVISION_MANIFEST_20260902.json').read_text(encoding='utf-8'))
expert = ROOT / manifest['revised_root']
out['expert_files'] = [{'name': row['Name'], 'match': sha(expert / row['Name']).lower() == row['NewSHA256'].lower()} for row in manifest['files']]
params = json.loads((expert / 'camsol_params.json').read_text(encoding='utf-8'))
out['camsol'] = {'sidecar_matches': sha(expert / 'camsol_params.json') == (expert / 'camsol_params.json.sha256').read_text().split()[0].lower(),
                 'mu': params['random_normalization']['mu_random'], 'sigma': params['random_normalization']['sigma_random'], 'roseman_values': params['roseman_scale']['values']}

policy = scientific_network_policy()
del policy['spec']['ingress']
del policy['spec']['egress']
try:
    Launcher(lambda *args: (200, policy), 't01-phase1-real').offline_policy()
    out['omitted_empty_network_rules'] = 'ACCEPTED'
except ClusterError as exc:
    out['omitted_empty_network_rules'] = {'observed': 'REJECTED', 'code': exc.code, 'expected': 'accept semantically identical deny-all policy'}

image = 'review.invalid/control@sha256:' + 'a' * 64
docs = control_plane_documents(image)
pod = next(d for d in docs if d['kind'] == 'Deployment')['spec']['template']['spec']
out['control_plane'] = {'env': [v['name'] for v in pod['containers'][0]['env']],
                        'mounts': [v['mountPath'] for v in pod['containers'][0]['volumeMounts']],
                        'has_launcher_config': any(v['name'] == 'T01_KUBERNETES_CONFIG_FILE' for v in pod['containers'][0]['env']),
                        'generated_resource_kinds': [v['kind'] for v in docs]}
job = scientific_job_spec('structure', 'review', scientific_image=image, control_image=image, asset_claim='review-assets')
mounts = job['spec']['template']['spec']['containers'][0]['volumeMounts']
out['structure_worker_mount'] = {'reads': '/worker/sources.json', 'mounted_paths': [v['mountPath'] for v in mounts],
                                'worker_directory_mounted': any(v['mountPath'] == '/worker' for v in mounts)}

# A realistic omission in an API response must not strand an execution forever.
# This is a narrow launcher fixture; no live Kubernetes calls occur.
out['target_success_profile'] = {'source': 'src/t01_phase1_real/deployment/execution.py',
    'succeeded_maps_to_profile_not_approved': "error='PROFILE_NOT_APPROVED' if observation['state']=='succeeded'" in (ROOT / 'src/t01_phase1_real/deployment/execution.py').read_text()}

candidate = ROOT / 'deploy/t01-phase1-real-target-v0.1'
source_index = json.loads((candidate / 'metadata/source-index.json').read_text(encoding='utf-8'))
out['candidate_source_drift'] = [row['path'] for row in source_index['files'] if not (ROOT / row['path']).is_file() or sha(ROOT / row['path']) != row['sha256']]

# Exercise the verifier against the current generator with tiny inert files.
spec = importlib.util.spec_from_file_location('review_candidate_verifier', ROOT / 'scripts/verify_target_linux_candidate.py')
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
import yaml
with tempfile.TemporaryDirectory(prefix='t01-review-verifier-') as directory:
    scratch = Path(directory)
    (scratch / 'metadata').mkdir()
    (scratch / 'kubernetes/scientific-jobs').mkdir(parents=True)
    (scratch / 'image.tar').write_bytes(b'inert fixture, not an image')
    (scratch / 'metadata/image.json').write_text(json.dumps({'archive': {'path': 'image.tar', 'size_bytes': (scratch/'image.tar').stat().st_size, 'sha256': sha(scratch/'image.tar')}, 'sbom': {'packages': 0}}))
    (scratch / 'metadata/sbom.spdx.json').write_text(json.dumps({'spdxVersion': 'SPDX-2.3', 'packages': []}))
    (scratch / 'kubernetes/control-plane.yaml').write_text(yaml.safe_dump_all(docs))
    for index in range(10):
        (scratch / f'kubernetes/scientific-jobs/{index}.yaml').write_text(yaml.safe_dump({'metadata': {'annotations': {'t01.openai/not-submitted': 'true'}}}))
    rows = [{'path': p.relative_to(scratch).as_posix(), 'size_bytes': p.stat().st_size, 'sha256': sha(p)} for p in scratch.rglob('*') if p.is_file()]
    (scratch / 'index.json').write_text(json.dumps({'files': rows, 'indexed_files': len(rows), 'completion_boundary': 'LOCAL_RELEASE_CANDIDATE_ONLY', 'production_status': 'NOT_DEPLOYED'}))
    try:
        verifier.verify(scratch)
        out['current_generator_verifier'] = 'PASS'
    except ValueError as exc:
        out['current_generator_verifier'] = {'observed': 'FAIL', 'message': str(exc)}

out['hotspot_default_bound'] = {'assumptions': 'B E1 only; T E2 max; highest grade per interval; normalized score <=1; no IEDB/DiscoTope',
    'both_channels_upper_bound': 0.5*0.2 + 0.5*0.5, 'b_only_renormalized_bound': 0.2,
    't_only_renormalized_bound': 0.5, 'strict_threshold': '>0.5', 'positive_hotspot_possible_with_defaults': False}

def windows(s):
    return [i for i in range(len(s)-4) if s[i:i+5] in ('HPHPH', 'PHPHP')]
patterns = [''.join(s) for n in range(5,10) for s in itertools.product('HPN', repeat=n)]
out['camsol_global_hp_swap'] = {'cases': len(patterns), 'all_invariant': all(windows(s) == windows(s.translate(str.maketrans('HP','PH'))) for s in patterns),
    'scope': 'pure global H/P relabeling only; not approval of numeric parameters or other transformations'}

# Check syntax of every JSON Schema block in the expert source without editing it.
import re
from jsonschema import Draft202012Validator
schema_text = (expert / 'AgentA_Schema_v10.5_20260902.md').read_text(encoding='utf-8')
out['expert_schema_blocks'] = []
for n, raw in enumerate(re.findall(r'```json\s*\n(.*?)\n```', schema_text, re.S), 1):
    try:
        value = json.loads(raw)
        Draft202012Validator.check_schema(value)
        out['expert_schema_blocks'].append({'block': n, 'title': value.get('title'), 'status': 'PASS_SYNTAX_ONLY'})
    except Exception as exc:
        out['expert_schema_blocks'].append({'block': n, 'status': 'FAIL', 'error': str(exc)[:500]})

out['source_hashes'] = {p.relative_to(ROOT).as_posix(): sha(p) for folder in ('src', 'scripts') for p in (ROOT/folder).rglob('*.py') if '__pycache__' not in p.parts}
destination = Path(__file__).with_name('probes.json')
with destination.open('x', encoding='utf-8') as stream:
    json.dump(out, stream, ensure_ascii=False, indent=2)
print(json.dumps({k:v for k,v in out.items() if k != 'source_hashes'}, ensure_ascii=False, indent=2))
