"""Whole-snapshot release of marked temporary parallel N14 execution."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/n14-performance-20260928'
release.OUT=release.common.ROOT/'deploy/n14-parallel/r01'


def regression():
    root=release.EVIDENCE
    tested=json.loads((root/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    paths=[root/'full.junit.xml']
    if (root/'final-recheck.junit.xml').exists():paths.append(root/'final-recheck.junit.xml')
    latest={}
    for path in paths:
        for c in ET.parse(path).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<2800 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Full current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='full current-root regression and final affected recheck',
        receipts={p.name:sha(p.read_bytes()) for p in paths+[root/'tested-source.json']})


release.regression=regression
if __name__=='__main__':release.main()
