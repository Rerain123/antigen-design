"""Deploy the tested scientific-report presentation without starting scientific jobs."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET

import deploy_report_storage as release
from version_bundle import build, sha

base = release.base
base.OUT = base.common.ROOT / 'deploy/report-facts/r01'
base.EV = base.common.ROOT / 'reports/report-fix-20261014/deployment'
REVIEW = base.EV.parent
release.PREVIOUS = base.common.ROOT / 'deploy/iedb-6l62/r01/source-manifest.json'
release.EXPECTED = {'t01_phase1_real/service_api/' + name for name in
                    ('native_report.py', 'user_report.py', 'himat.py')}


def regression():
    receipts = []
    for name, minimum in (('full-tests.xml', 3435),
                          ('results-only-tests-final.xml', 111),
                          ('deployment-integration-tests.xml', 29)):
        raw = (REVIEW / name).read_bytes()
        cases = list(ET.fromstring(raw).iter('testcase'))
        assert len(cases) >= minimum, name
        assert not any(c.find(k) is not None for c in cases for k in ('failure', 'error')), name
        receipts.append(dict(path=name, sha256=sha(raw), tests=len(cases),
                             skipped=sum(c.find('skipped') is not None for c in cases)))
    implementation = json.loads((REVIEW / 'implementation.json').read_bytes())
    for name, digest in implementation['source_files'].items():
        assert sha((base.common.ROOT / name).read_bytes()) == digest, name
    for name, digest in build(base.common.ROOT / 'src')[1].items():
        assert sha(subprocess.check_output(['git', 'show', 'HEAD:src/' + name],
                                          cwd=base.common.ROOT)) == digest, name
    frozen = json.loads((REVIEW / 'frozen.json').read_bytes())
    assert frozen['status'] == 'PASS' and frozen['frozen_asset_count'] == 457
    return dict(receipts=receipts, single_final_full_run=False,
                note='Full regression precedes final results-only text edits; final affected tests passed.',
                commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                               cwd=base.common.ROOT, text=True).strip())


base.regression = regression

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'rollout', 'activate', 'verify'])
    action = parser.parse_args().action
    (release.prepare if action == 'prepare' else getattr(base, action))()
