"""Publish the N17 complete-scope increment using the existing whole snapshot path."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,encode,sha

release.EVIDENCE=release.common.ROOT/'reports/n17-scope-20260927'
release.OUT=release.common.ROOT/'deploy/n17-scope/r01'


def regression():
    evidence=release.EVIDENCE
    tested=json.loads((evidence/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:
        raise RuntimeError('Source changed after tests')
    paths=['full.junit.xml','targeted.junit.xml','lifecycle.junit.xml']
    latest={}
    for name in paths:
        for case in ET.parse(evidence/name).iter('testcase'):
            latest[(case.get('classname'),case.get('name'))]=case
    cases=list(latest.values())
    if len(cases)<2624 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('N17 complete regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='full current-root UTF-8 run and N17 targeted/lifecycle checks',
        receipts={name:sha((evidence/name).read_bytes()) for name in [*paths,'tested-source.json']})


release.regression=regression
if __name__=='__main__':release.main()
