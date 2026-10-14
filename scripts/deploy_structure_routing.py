"""Publish the user-confirmed 10% routing rule after test-branch CI deployment.

The existing shared pipeline updates only the API image. This wrapper uses the
established complete-source rollout for all ten existing workloads, without
starting a scientific task or changing native images/resources.
"""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import deploy_report_storage as release
from version_bundle import build,encode,sha

base=release.base
base.OUT=base.common.ROOT/'deploy/structure-routing/r01'
base.EV=base.common.ROOT/'reports/wt-engine-routing-20261013/deployment'
REVIEW=base.common.ROOT/'reports/wt-engine-routing-20261013'
release.PREVIOUS=base.common.ROOT/'deploy/scientific-report/r01/source-manifest.json'
release.EXPECTED={'t01_phase1_real/development/workflow/'+n for n in
    ('continuation.py','policy.py','revision_runtime.py','revision_structure.py','revision_v2.py','revision_v2_runtime.py')}
release.EXPECTED|={'t01_phase1_real/service_api/'+n for n in ('himat.py','native_report.py')}


def regression():
    receipt=json.loads((REVIEW/'implementation.json').read_bytes())
    assert receipt['verification']['all_previous_failures_covered']
    cases=set();reports=[]
    for name in ('ratio-same-engine.xml','regression-final.xml'):
        raw=(REVIEW/name).read_bytes();items=list(ET.fromstring(raw).iter('testcase'))
        assert not any(c.find(k) is not None for c in items for k in ('failure','error','skipped'))
        cases.update((c.get('classname'),c.get('name')) for c in items)
        reports.append(dict(path=name,sha256=sha(raw),passed=len(items)))
    assert len(cases)==369
    # Deployment must consume exactly the pushed Git source bytes, not an overlay
    # assembled from uncommitted implementation changes.
    manifest=build(base.common.ROOT/'src')[1]
    for name,digest in manifest.items():
        raw=subprocess.check_output(['git','show','HEAD:src/'+name],cwd=base.common.ROOT)
        assert sha(raw)==digest,name
    return dict(unique_tests=369,receipts=reports,single_final_full_run=False,
                commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.common.ROOT,text=True).strip())


base.regression=regression

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','apply','rollout','activate','verify'])
    action=parser.parse_args().action
    (release.prepare if action=='prepare' else getattr(base,action))()
