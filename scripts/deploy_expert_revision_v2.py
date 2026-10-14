"""Deploy the tested v2 source snapshot without submitting scientific jobs."""
import json
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build, sha

TESTED = release.common.ROOT / 'reports/expert-revision-v2-20260930'
release.EVIDENCE = release.common.ROOT / 'reports/expert-revision-v2-deploy-20260930'
release.OUT = release.common.ROOT / 'deploy/expert-revision-v2/r01'


def regression():
    tested = json.loads((TESTED / 'tested-source.json').read_bytes())
    if build(release.common.ROOT / 'src')[1] != tested['source_hashes']:
        raise RuntimeError('Source differs from the verified v2 increment')
    summary = json.loads((TESTED / 'regression-summary.json').read_bytes())
    paths = [TESTED / row['file'] for row in summary['runs']]
    latest = {}
    for row, path in zip(summary['runs'], paths):
        if sha(path.read_bytes()) != row['sha256']:
            raise RuntimeError('V2 test receipt hash changed')
        for case in ET.parse(path).iter('testcase'):
            latest[(case.get('classname'), case.get('name'))] = case
    cases = list(latest.values())
    if len(cases) != 3009 or any(
            c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('V2 current-root regression must pass')
    skipped = sum(c.find('skipped') is not None for c in cases)
    if skipped != 15:
        raise RuntimeError('Unexpected skipped-test inventory')
    return dict(total=len(cases), skipped=skipped,
                method=summary['method'],
                receipts={p.name: sha(p.read_bytes()) for p in paths + [TESTED / 'tested-source.json']})


release.regression = regression
if __name__ == '__main__':
    release.main()
