"""Deploy the tested post-score checkpoint continuation without native jobs."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/expert-revision-v2-resume-20260930'
release.OUT=release.common.ROOT/'deploy/expert-revision-v2-resume/r01'


def regression():
    path=release.EVIDENCE/'full.junit.xml';tested=release.EVIDENCE/'tested-source.json'
    if build(release.common.ROOT/'src')[1]!=json.loads(tested.read_bytes())['source_hashes']:
        raise RuntimeError('Sources changed after post-score continuation validation')
    cases=list(ET.parse(path).iter('testcase'))
    failed=[c for c in cases if c.find('failure') is not None or c.find('error') is not None]
    receipts=[path,tested]
    method='single full current-root run after post-score continuation support'
    if failed:
        # Retain the original run. Docker Desktop was stopped; only the same
        # six source-provenance tests may replace their recorded outcomes.
        allowed={('tests.test_same_run_submission',name) for name in (
            'test_same_run_proteinmpnn_keeps_source_provenance_checks',
            'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[sequence]',
            'test_same_run_proteinmpnn_still_rejects_corrupt_local_source[hash]')}
        if {(c.get('classname'),c.get('name')) for c in failed}!=allowed:
            raise RuntimeError('Unexpected full-regression failures')
        recheck=release.EVIDENCE/'docker-recheck.junit.xml'
        final=list(ET.parse(recheck).iter('testcase'))
        index={(c.get('classname'),c.get('name')):c for c in cases}
        if len(final)!=6 or any(c.get('classname')!='tests.test_same_run_submission' or
                (c.get('classname'),c.get('name')) not in index or
                any(c.find(tag) is not None for tag in ('failure','error','skipped')) for c in final):
            raise RuntimeError('Docker source-provenance recheck must pass all six cases')
        index.update({(c.get('classname'),c.get('name')):c for c in final})
        cases=list(index.values());receipts.append(recheck)
        method='full current-root run plus six Docker rechecks after restoring the stopped daemon; not a single all-green run'
    if len(cases)<3063 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Complete current-root regression must pass')
    return dict(total=len(cases),passed=sum(c.find('skipped') is None for c in cases),
        skipped=sum(c.find('skipped') is not None for c in cases),original_failures=len(failed),
        method=method,receipts={p.name:sha(p.read_bytes()) for p in receipts})


release.regression=regression
if __name__=='__main__':release.main()
