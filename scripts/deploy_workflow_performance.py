"""Deploy the tested controller optimization with an idle-service fence."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/workflow-performance-20260928'
release.OUT=release.common.ROOT/'deploy/workflow-performance/r01'


def regression():
    root=release.EVIDENCE
    tested=json.loads((root/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:
        raise RuntimeError('Untested source changes')
    names=('final-affected.junit.xml','downstream.junit.xml','api-final.junit.xml','http.junit.xml')
    latest={}
    for n in names:
        for c in ET.parse(root/n).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<180 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Affected controller, continuation, API and downstream regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
                method='affected regression; scientific algorithms and model settings unchanged',
                receipts={n:sha((root/n).read_bytes()) for n in (*names,'tested-source.json')})


release.regression=regression
if __name__=='__main__':release.main()
