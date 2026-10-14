"""Release bounded streaming report exports after the presentation deployment."""
import argparse
import json
import xml.etree.ElementTree as ET

import deploy_report_facts as facts
from version_bundle import sha

release = facts.release
base = facts.base
base.OUT = base.common.ROOT / 'deploy/report-facts/r02'
base.EV = facts.REVIEW / 'deployment-r02'
release.PREVIOUS = base.common.ROOT / 'deploy/report-facts/r01/source-manifest.json'
release.EXPECTED = {'t01_phase1_real/service_api/' + name for name in
                    ('native_results.py', 'object_storage.py')}


def regression():
    result = facts.regression()
    raw = (facts.REVIEW / 'export-fix-tests.xml').read_bytes()
    cases = list(ET.fromstring(raw).iter('testcase'))
    assert len(cases) >= 145
    assert not any(c.find(k) is not None for c in cases for k in ('failure', 'error', 'skipped'))
    receipt = json.loads((facts.REVIEW / 'export-implementation.json').read_bytes())
    for path, digest in receipt['source_files'].items():
        assert sha((base.common.ROOT / path).read_bytes()) == digest
    probe = json.loads((facts.REVIEW / 'export-probe.json').read_bytes())
    assert probe['status'] == 'PASS' and probe['manifest_hashes_verified']
    assert probe['source_sha256'] == receipt['source_files']['src/t01_phase1_real/service_api/native_results.py']
    result.update(final_affected_tests=len(cases), final_affected_sha256=sha(raw), real_export=probe,
                  note='Prior full regression; final report/export/API/storage regression passed.')
    return result


base.regression = regression
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'apply', 'rollout', 'activate', 'verify'])
    action = parser.parse_args().action
    (release.prepare if action == 'prepare' else getattr(base, action))()
