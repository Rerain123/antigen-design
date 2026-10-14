"""WT MSA and bounded FoldX scan release; no scientific job submissions."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/msa-scan-20260928'
release.OUT=release.common.ROOT/'deploy/msa-scan/r01'


def regression():
    root=release.EVIDENCE
    tested=json.loads((root/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    names=('full.junit.xml','final-affected.junit.xml','docker-recheck.junit.xml')
    latest={}
    for name in names:
        for c in ET.parse(root/name).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<2780 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Full current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='full current-root plus final affected checks; no new scientific jobs',
        receipts={n:sha((root/n).read_bytes()) for n in (*names,'tested-source.json')})


release.regression=regression
if __name__=='__main__':release.main()
