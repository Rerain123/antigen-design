"""Deploy the tested report/registered-output export repair, without model jobs."""
import json
import xml.etree.ElementTree as ET

import deploy_n15_selection as release
from version_bundle import build, sha

release.EVIDENCE=release.common.ROOT/'reports/expert-revision-v2-results-20260930'
release.OUT=release.common.ROOT/'deploy/expert-revision-v2-results/r01'


def regression():
    path=release.EVIDENCE/'full.junit.xml'
    tested=release.EVIDENCE/'tested-source.json'
    if build(release.common.ROOT/'src')[1]!=json.loads(tested.read_bytes())['source_hashes']:
        raise RuntimeError('Report sources changed after current-root regression')
    full=list(ET.parse(path).iter('testcase'))
    cases=full
    receipt_paths=[path,tested]
    method='single full current-root run after native report repair'
    failed=[c for c in full if c.find('failure') is not None or c.find('error') is not None]
    if failed:
        allowed={'test_same_run_proteinmpnn_keeps_source_provenance_checks',
                 'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[sequence]',
                 'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[hash]'}
        if any(c.get('classname')!='tests.test_same_run_submission' or c.get('name') not in allowed for c in failed):
            raise RuntimeError('Unexpected failure in full current-root regression')
        recheck=release.EVIDENCE/'docker-original-store-recheck.junit.xml'
        latest={(c.get('classname'),c.get('name')):c for c in full}
        for c in ET.parse(recheck).iter('testcase'):
            key=(c.get('classname'),c.get('name'))
            if key not in latest:raise RuntimeError('Recheck is not from the full regression')
            latest[key]=c
        cases=list(latest.values());receipt_paths.append(recheck)
        method='full current-root run plus same-source original-Docker-store recheck; not a single all-green run'
    if len(cases)<3074 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Current-root report/API regression must pass')
    return dict(total=len(cases),passed=sum(c.find('skipped') is None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases),
                method=method,initial_failed=len(failed),
                receipts={p.name:sha(p.read_bytes()) for p in receipt_paths})


release.regression=regression
if __name__=='__main__':release.main()
