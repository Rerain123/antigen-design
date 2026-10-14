"""Whole-source opt-in expert core release; does not submit scientific jobs."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/expert-revision-core-20260929'
release.OUT=release.common.ROOT/'deploy/expert-revision-core/r01'


def regression():
    root=release.EVIDENCE
    tested=json.loads((root/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    paths=[root/'full.junit.xml']
    for name in ('final-recheck.junit.xml','handshake-final.junit.xml'):
        if (root/name).exists():paths.append(root/name)
    latest={}
    for path in paths:
        for case in ET.parse(path).iter('testcase'):latest[(case.get('classname'),case.get('name'))]=case
    cases=list(latest.values())
    if len(cases)<2900 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Full current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='Full current-root regression plus any explicit final recheck',
        receipts={p.name:sha(p.read_bytes()) for p in paths+[root/'tested-source.json']})


release.regression=regression
if __name__=='__main__':release.main()
