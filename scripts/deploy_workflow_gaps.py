"""Deploy tested expert-v2 gap fixes only while the service is idle."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import deploy_n15_selection as release
from version_bundle import build, encode, sha

ROOT=release.common.ROOT
EVIDENCE=ROOT/'reports/workflow-gaps-20261009'
OUT=ROOT/'deploy/workflow-gaps/r01'
BASE=ROOT/'deploy/controller-recovery/r01/preflight.json'
release.EVIDENCE=EVIDENCE
release.OUT=OUT


def regression():
    current=build(ROOT/'src')[1]
    baseline=json.loads(BASE.read_bytes())['source_hashes']
    tested=json.loads((EVIDENCE/'changed-source-hashes.json').read_bytes())
    expected=dict(baseline)
    for path,row in tested.items():
        name=path.removeprefix('src/')
        if baseline.get(name)!=row['deployed_baseline_sha256']:
            raise RuntimeError('Tested baseline differs')
        expected[name]=row['sha256']
    if len(tested)!=9 or current!=expected:
        raise RuntimeError('Source differs from tested nine-file change')
    names=('full-r01.xml','targeted-r03.xml','full-failure-recheck.xml')
    rows={}
    for name in names:
        cases=list(ET.parse(EVIDENCE/name).iter('testcase'))
        if name!='full-r01.xml' and any(any(c.find(k) is not None for k in ('failure','error','skipped')) for c in cases):
            raise RuntimeError('Final affected checks must pass')
        for c in cases:rows[(c.get('classname'),c.get('name'))]=c
    cases=list(rows.values())
    if len(cases)!=3136 or any(any(c.find(k) is not None for k in ('failure','error')) for c in cases):
        raise RuntimeError('Complete regression with failure rechecks required')
    return dict(passed=sum(c.find('skipped') is None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases),
        single_all_green_full_run=False,source_sha256=sha(encode(current)),
        receipts={name:sha((EVIDENCE/name).read_bytes()) for name in (*names,'changed-source-hashes.json')})


def probe():
    import probe_version_unification as check
    from t01_phase1_mock.dify.campaign import verify_freeze_manifest
    release.deploy.idle()
    regression()
    (EVIDENCE/'frozen.json').write_bytes(encode(verify_freeze_manifest()))
    check.OUT=EVIDENCE
    # Exercise the new pure calculation with the actual service interpreter.
    # This is a local synthetic observation, never a model/job submission.
    check.REMOTE=check.REMOTE.replace("checked=[]", """if p['container']=='service':
        from t01_phase1_real.development.workflow.revision_sequence import _metrics
        from t01_phase1_real.development.workflow.revision_v2 import config,validate,SELECTION
        assert _metrics('ACDEFGHIKLMNPQRSTVWY')['status']=='computed_unreviewed'
        validate(config('compatibility-only')['policies'])
        assert SELECTION.endswith('-id-v2')
    checked=[]""")
    check.main()


def main():
    action=sys.argv[1]
    if action in ('probe','prepare','apply'):
        live=json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
        if live['spec']['template']['metadata']['annotations']['antigen-design/source-sha256']!=json.loads(BASE.read_bytes())['source_sha256']:
            raise RuntimeError('Live deployment no longer matches the reviewed baseline')
    release.regression=regression
    if action=='probe':probe()
    else:release.main()


if __name__=='__main__':main()
