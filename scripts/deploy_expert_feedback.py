"""Release the tested 10-09 expert adoption; no model or workflow submission."""
import base64
import concurrent.futures
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import deploy_n15_selection as release
from version_bundle import build, encode, sha

ROOT = release.common.ROOT
EVIDENCE = ROOT / 'reports/expert-feedback-20261009'
OUT = ROOT / 'deploy/expert-feedback/r02'
BASE = ROOT / 'deploy/workflow-gaps/r01/preflight.json'

# Pure synthetic checks also run under the installed engineering interpreter.
# They produce no candidate, registered artifact, or scientific model task.
CHECK = r'''
from t01_phase1_real.development.expert_feedback import authority, functional_regions
from t01_phase1_real.development.developability.camsol import assess, registered_parameters
from t01_phase1_real.development.bepipred.postprocessing import project
from t01_phase1_real.development.design_backend import permissions, policy as dp
from t01_phase1_real.common import decode
assert authority()['version'] == 'expert-feedback-20261009-v1'
params, identity = registered_parameters()
sol = assess('ACDEFGHIKLMNPQRSTVWY')
assert sol['parameter_completeness'] == 'COMPLETE' and len(sol['per_residue']) == 20
assert sol['reliable'] is False and sol['consistency_status'] == 'NOT_ASSESSED'
assert sol['scientific_consumption'] is False
assert assess('ACDEFGHIKLMNPQRSTVWY', 7.0)['mode'] == 'ph_mvp'
rows = [dict(sequence_position=i, residue='A', ensemble_probability=v,
             linear_epitope_score=v) for i,v in enumerate([.4]*3+[.1]*2+[.4]*3,1)]
peaks = project(rows)
assert peaks['linear_peaks_threshold'][0]['bridge_count'] == 2
assert peaks['linear_peaks_threshold'][0]['positive_count'] == 6
assert peaks['top20_audit']['count'] == 1
assert peaks['status'] == 'computed_pending_calibration'
domains = [dict(type='mature_chain',start=1,end=5,confidence='high',source='uniprot'),
           dict(type='active_site',start=2,end=2,confidence='high',source='uniprot')]
assert len(functional_regions(domains)) == 1 and len(domains) == 2
body = dict(protein_sequence='AAAAA',user_sequence_id='synthetic-import-check',
    upstream={n:None for n in dp.PRODUCERS},user_regions=[],objective='general',
    epitope_policy='PRESERVE',epitope_mode='both',membrane_design_confirm=False,
    sample_numbers=[],timeout_seconds=30)
values = dict(domains=dict(analysis=dict(functional_domains=domains,core_map=None)))
receipts = {n:dict(state='available' if n in values else 'missing',artifact=None)
            for n in dp.PRODUCERS}
audit = permissions.assemble(body,values,receipts,decode((dp.HERE/'scales.json').read_bytes()))
assert audit['fixed_positions'] == [2] and len(audit['annotation_exclusions']) == 1
assert len(audit['restricted_positions']) == 4 and not audit['open_positions']
'''

# Use the actual registered asset path after rollout. Temporary compatibility
# staging has deliberate repository symlinks, which the native asset guard rejects.
PIG_CHECK = r'''
from t01_phase1_real.development.netmhc.host_panel import readiness
panel = readiness('猪')
assert panel['channels']['mhc_i']['allele_count'] == 76
assert panel['channels']['mhc_ii']['assessment_status'] == 'NOT_ASSESSED'
assert panel['channels']['mhc_ii']['package_sla_supported_count'] == 0
assert panel['pig_mhc_ii_degraded'] is False and panel['degradation_factor_applied'] is False
assert panel['breed_coverage'] == 'NOT_ASSESSED'
'''


def regression():
    tested = json.loads((EVIDENCE/'verification.json').read_bytes())
    entry = json.loads((EVIDENCE/'entry-version-source.json').read_bytes())
    packaging = json.loads((EVIDENCE/'packaging-source.json').read_bytes())
    for path, digest in packaging['source_hashes'].items():
        if sha((ROOT/path).read_bytes()) != digest:
            raise RuntimeError('Tested deployment packaging changed')
    archive, manifest = build(ROOT/'src')
    expected = dict(tested['source_hashes'])
    path = 't01_phase1_real/service_api/himat.py'
    if (entry['baseline_source_sha256'] != tested['source_bundle']['manifest_sha256']
            or entry['baseline_file_sha256'] != expected[path]):
        raise RuntimeError('HiMat version-isolation baseline changed')
    expected[path] = entry['current_file_sha256']
    if (manifest != expected or manifest != entry['source_hashes']
            or sha(encode(manifest)) != entry['source_bundle']['manifest_sha256']
            or sha(archive) != entry['source_bundle']['archive_sha256']):
        raise RuntimeError('Sources differ from final tested expert-adoption snapshot')
    closeout = json.loads((EVIDENCE/'closeout.json').read_bytes())
    names = ('full-r01.xml','final-affected-r07.xml','final-report-r08.xml','docker-recheck-r09.xml',
             'entry-version-r10.xml','entry-version-r11-http.xml','packaging-r12.xml')
    bound = {row['path'].rsplit('/',1)[-1]:row['sha256'] for row in (
        closeout['tests']['full_initial'],closeout['tests']['final_affected'],
        closeout['tests']['final_report'],closeout['tests']['docker_recheck'])}
    bound.update(entry['test_receipts'])
    bound['packaging-r12.xml'] = packaging['test_receipt_sha256']
    latest = {}; receipts = {}
    for name in names:
        raw = (EVIDENCE/name).read_bytes()
        if sha(raw) != bound[name]:
            raise RuntimeError('Final regression receipt changed')
        cases = list(ET.fromstring(raw).iter('testcase'))
        if name not in ('full-r01.xml','entry-version-r10.xml') and (not cases or any(
                any(c.find(k) is not None for k in ('failure','error','skipped')) for c in cases)):
            raise RuntimeError('Final affected/recovery checks must all pass')
        for case in cases:
            latest[(case.get('classname'),case.get('name'))] = case
        receipts[name] = sha(raw)
    cases = list(latest.values())
    if len(cases) < 3200 or any(any(c.find(k) is not None for k in ('failure','error')) for c in cases):
        raise RuntimeError('Complete initial collection plus final/recovery checks must pass')
    return dict(total=len(cases),passed=sum(c.find('skipped') is None for c in cases),
        skipped=sum(c.find('skipped') is not None for c in cases),
        single_final_full_run=False,method='full initial + final affected + exact environment rechecks + entry/packaging; deduplicated',
        source_sha256=sha(encode(manifest)),receipts=receipts,
        verification_sha256=sha((EVIDENCE/'verification.json').read_bytes()),
        entry_version_source_sha256=sha((EVIDENCE/'entry-version-source.json').read_bytes()),
        packaging_source_sha256=sha((EVIDENCE/'packaging-source.json').read_bytes()))


def baseline():
    live = json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
    expected = json.loads(BASE.read_bytes())['source_sha256']
    if live['spec']['template']['metadata']['annotations']['antigen-design/source-sha256'] != expected:
        raise RuntimeError('Live deployment changed since the reviewed generation-146 baseline')


def invoke(container, code, payload=None):
    # Keep exec's URL short for the cluster's nginx gateway; code travels on stdin.
    bootstrap = "import json,sys;p=json.load(sys.stdin);exec(compile(p.pop('code'),'expert-release-check','exec'))"
    python = 'python' if container == 'service' else '/opt/t01/supervisor/bin/python3.11'
    return subprocess.run(release.common.K+['exec','-i','deployment/antigen-design','-c',container,
        '--',python,'-B','-c',bootstrap],input=encode(dict(payload or {},code=code)),
        capture_output=True,timeout=150)


def compatibility_probe():
    import probe_version_unification as probe
    from t01_phase1_mock.dify.campaign import verify_freeze_manifest
    release.deploy.idle()
    (EVIDENCE/'frozen.json').write_bytes(encode(verify_freeze_manifest()))
    remote = probe.REMOTE.replace('p=json.load(sys.stdin)','')
    remote = remote.replace('    checked=[]',
        "    if p['container']=='service':\n        exec("+repr(CHECK)+")\n    checked=[]")
    remote = remote.replace('        done=subprocess.run(',
        "        if command.tool=='engineering':code+='\\n'+"+repr(CHECK)+
        '\n        done=subprocess.run(')
    compile(remote,'compatibility','exec')
    archive, manifest = build(ROOT/'src')
    from pathlib import Path
    payload = {k:base64.b64encode(v).decode() for k,v in dict(archive=archive,
        manifest=encode(manifest),installer=Path(__file__).with_name('version_bundle.py').read_bytes()).items()}
    payload['sha256'] = sha(encode(manifest))
    live = json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
    def check(container):
        name = container['name']
        done = invoke(name,remote,dict(payload,container=name))
        if done.returncode:
            return dict(container=name,status='FAIL',error=done.stderr.decode(errors='replace')[-2200:])
        return json.loads(next(line[6:] for line in done.stdout.decode().splitlines() if line.startswith('PROBE=')))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(check,live['spec']['template']['spec']['containers']))
    (EVIDENCE/'predeploy-imports.json').write_bytes(encode(rows))
    print(json.dumps(rows))
    if any(row['status'] != 'PASS' for row in rows):
        raise SystemExit(1)


def main():
    action = sys.argv[1]
    if action not in ('probe','prepare','apply','verify','entry'):
        raise ValueError('Unknown deployment action')
    release.EVIDENCE = EVIDENCE
    release.OUT = OUT
    release.regression = regression
    if action in ('probe','prepare','apply'):
        regression()
        baseline()
    if action == 'probe':
        compatibility_probe()
    elif action == 'entry':
        import verify_workflow_gaps_entry as entry
        code = entry.REMOTE.replace('print(json.dumps(dict(status=',CHECK+PIG_CHECK+'\nprint(json.dumps(dict(status=')
        code = code.replace("cfg=accepted['revision_config']",
            "cfg=accepted['revision_config']\nassert cfg['calculation_config_id']=='himat-expert-v2-20261009-v1'")
        done = invoke('service',code)
        if done.returncode:
            raise RuntimeError(done.stderr.decode(errors='replace')[-2200:])
        value = json.loads(done.stdout)
        value.update(expert_authority_version='expert-feedback-20261009-v1',
            expert_checks='SYNTHETIC_FORMULA_AND_BOUNDARY_ONLY',scientific_models_executed=False)
        with (EVIDENCE/'deployed-entry-verification.json').open('xb') as stream:
            stream.write(encode(value))
        print(json.dumps(value,ensure_ascii=False))
    else:
        release.main()


if __name__ == '__main__':
    main()
