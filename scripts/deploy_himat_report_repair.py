"""Deploy the bounded HiMat report/entry repair after complete regression."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import deploy_n15_selection as release
from version_bundle import build, sha

release.EVIDENCE=release.common.ROOT/'reports/himat-report-repair-20261008'
release.OUT=release.common.ROOT/'deploy/himat-report-repair/r01'
BASE=release.common.ROOT/'deploy/mcp-client-guide/r01/preflight.json'
ALLOWED={f't01_phase1_real/service_api/{name}.py' for name in
         ('native_results','native_report','user_report','himat','app')}


def regression():
    current=build(release.common.ROOT/'src')[1]
    tested=json.loads((release.EVIDENCE/'tested-source.json').read_bytes())
    baseline=json.loads(BASE.read_bytes())['source_hashes']
    changed={p for p in set(current)|set(baseline) if current.get(p)!=baseline.get(p)}
    if current!=tested['source_hashes'] or changed!=ALLOWED:
        raise RuntimeError('Sources differ from the tested service-only repair')
    paths=[release.EVIDENCE/name for name in ('full.junit.xml','regression.junit.xml')]
    full=list(ET.parse(paths[0]).iter('testcase'))
    affected=list(ET.parse(paths[1]).iter('testcase'))
    if len(full)<3074 or len(affected)!=180:
        raise RuntimeError('Complete and affected regression receipts required')
    if any(c.find('failure') is not None or c.find('error') is not None for c in full+affected):
        raise RuntimeError('Regression has unresolved failures')
    if any(c.find('skipped') is not None for c in affected):
        raise RuntimeError('Affected regression must not be skipped')
    return dict(total=len(full),passed=sum(c.find('skipped') is None for c in full),
        skipped=sum(c.find('skipped') is not None for c in full),affected_passed=len(affected),
        changed_sources=sorted(changed),
        receipts={p.name:sha(p.read_bytes()) for p in paths+[release.EVIDENCE/'tested-source.json']})


def main():
    if len(sys.argv)!=2 or sys.argv[1] not in {'probe','prepare','apply','verify'}:
        raise SystemExit('Usage: deploy_himat_report_repair.py probe|prepare|apply|verify')
    if sys.argv[1] in {'prepare','apply'}:
        live=json.loads(subprocess.check_output(release.common.K+['get','deployment','antigen-design','-o','json']))
        if live['spec']['template']['metadata']['annotations']['antigen-design/source-sha256']!=json.loads(BASE.read_bytes())['source_sha256']:
            raise RuntimeError('Live source differs from the reviewed baseline')
    release.regression=regression
    release.main()


if __name__=='__main__':main()
