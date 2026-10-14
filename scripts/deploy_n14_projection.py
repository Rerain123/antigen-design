"""N14 PDB format projection; preserve the exact native N11 WT design basis."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/n14-projection-20260928'
release.OUT=release.common.ROOT/'deploy/n14-projection/r01'


def regression():
    root=release.EVIDENCE;old=root.parent/'n14-capacity-20260928'
    tested=json.loads((root/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    paths=[old/n for n in ('full.junit.xml','final-recheck.junit.xml','mapping-recheck.junit.xml')]+[root/'affected.junit.xml']
    latest={}
    for path in paths:
        for c in ET.parse(path).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<2800 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Full baseline and final affected regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='same-session full regression plus projection affected recheck',
        receipts={str(p.relative_to(root.parent)):sha(p.read_bytes()) for p in paths+[root/'tested-source.json']})


release.regression=regression
if __name__=='__main__':release.main()
