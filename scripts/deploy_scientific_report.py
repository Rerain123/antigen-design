"""Publish the reviewed scientific-report presentation using complete source bundles."""
import argparse
import json
import xml.etree.ElementTree as ET

import deploy_report_storage as release
from version_bundle import encode, sha

base = release.base
base.OUT = base.common.ROOT / 'deploy/scientific-report/r01'
base.EV = base.common.ROOT / 'reports/scientific-report-20261011/deployment'
REVIEW = base.common.ROOT / 'reports/scientific-report-20261011'
release.PREVIOUS = base.common.ROOT / 'deploy/report-storage/r01/source-manifest.json'
release.EXPECTED = {'t01_phase1_real/service_api/' + name
                    for name in ('user_report.py', 'native_report.py')}


def regression():
    review = json.loads((REVIEW / 'closeout.json').read_bytes())
    for item in review['sources']:
        assert sha((base.common.ROOT / item['path']).read_bytes()) == item['sha256'], 'Reviewed source changed'
    path = REVIEW / 'targeted-final.xml'
    raw = path.read_bytes()
    cases = list(ET.fromstring(raw).iter('testcase'))
    assert len(cases) >= 113
    assert not any(c.find(k) is not None for c in cases for k in ('failure', 'error', 'skipped'))
    assert {'test_scientific_report', 'test_user_report', 'test_native_user_report',
            'test_himat_report_repair', 'test_rustfs_publication'} <= {
                c.get('classname', '').split('.')[-1] for c in cases}
    visual = json.loads((REVIEW / '20261011-073807-7ff412a6-scientific-report-visual-check.json').read_bytes())
    printed = json.loads((REVIEW / 'print-check.json').read_bytes())
    assert visual['status'] == printed['status'] == 'PASS'
    assert review['validation']['frozen_status'] == 'PASS' and review['validation']['frozen_assets'] == 457
    expected = review['output']
    assert sha((base.common.ROOT / expected['path']).read_bytes()) == expected['sha256']
    return dict(tests=len(cases), passed=len(cases), skipped=0,
                scope='report presentation and affected integrations; no full current-root rerun',
                receipt=dict(path=str(path.relative_to(base.common.ROOT)), sha256=sha(raw)),
                source_review_sha256=sha((REVIEW / 'closeout.json').read_bytes()),
                frozen_assets=457, visual_status='PASS', print_status='PASS')


base.regression = regression


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'rollout', 'activate', 'verify'])
    action = parser.parse_args().action
    (release.prepare if action == 'prepare' else getattr(base, action))()
