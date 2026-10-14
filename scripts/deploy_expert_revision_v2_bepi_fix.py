"""Publish the tested N04 consumer and immutable v2 checkpoint continuation."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930'
release.OUT=release.common.ROOT/'deploy/expert-revision-v2-bepi-fix/r01'


def regression():
    tested=json.loads((release.EVIDENCE/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:
        raise RuntimeError('Sources changed after the tested repair')
    path=release.EVIDENCE/'full.junit.xml'
    cases=list(ET.parse(path).iter('testcase'))
    if len(cases)<3049 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Complete current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='single full current-root run after the N04 contract repair',
        receipts={p.name:sha(p.read_bytes()) for p in (path,release.EVIDENCE/'tested-source.json')})


release.regression=regression
if __name__=='__main__':release.main()
