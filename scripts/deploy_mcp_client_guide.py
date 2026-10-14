"""Release only MCP guidance changes, using the existing source snapshot path."""
import json
import sys
import subprocess
import xml.etree.ElementTree as ET

import deploy_n15_selection as release
from version_bundle import build, sha

release.EVIDENCE = release.common.ROOT / 'reports/mcp-client-guide-20261008'
release.OUT = release.common.ROOT / 'deploy/mcp-client-guide/r01'
BASE = release.common.ROOT / 'deploy/expert-revision-v2-results/r01/preflight.json'
ALLOWED_CHANGES = {
    't01_phase1_real/service_api/client_guide.py',
    't01_phase1_real/service_api/transport.py',
}


def guidance_only(manifest, baseline):
    changed = {name for name in set(manifest) | set(baseline)
               if manifest.get(name) != baseline.get(name)}
    if changed != ALLOWED_CHANGES or set(baseline) - set(manifest):
        raise RuntimeError('This release allows only MCP guidance metadata changes')
    return sorted(changed)


def regression():
    tested = json.loads((release.EVIDENCE / 'tested-source.json').read_bytes())
    current = build(release.common.ROOT / 'src')[1]
    if current != tested['source_hashes']:
        raise RuntimeError('Sources changed after MCP guidance checks')
    baseline = json.loads(BASE.read_bytes())
    changed = guidance_only(current, baseline['source_hashes'])
    path = release.EVIDENCE / 'regression-r02.junit.xml'
    cases = list(ET.parse(path).iter('testcase'))
    if len(cases) != 60 or any(any(c.find(tag) is not None for tag in ('failure', 'error', 'skipped')) for c in cases):
        raise RuntimeError('All 60 affected MCP/API/progress/confirmation checks must pass')
    return dict(total=len(cases), passed=len(cases), skipped=0, changed_sources=changed,
                method='affected metadata/API/progress/confirmation regression; scientific sources unchanged',
                receipts={p.name: sha(p.read_bytes()) for p in (path, release.EVIDENCE / 'tested-source.json')})


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {'probe', 'prepare', 'apply', 'verify'}:
        raise SystemExit('Usage: deploy_mcp_client_guide.py probe|prepare|apply|verify')
    regression()
    if sys.argv[1] in {'probe', 'prepare', 'apply'}:
        live = json.loads(subprocess.check_output(release.common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
        expected = json.loads(BASE.read_bytes())['source_sha256']
        if live['spec']['template']['metadata']['annotations']['antigen-design/source-sha256'] != expected:
            raise RuntimeError('Live source differs from the reviewed guidance baseline')
    release.regression = regression
    release.main()


if __name__ == '__main__':
    main()
