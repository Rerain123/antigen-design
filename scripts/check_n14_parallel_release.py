"""Final affected checks and source fence for the N14 parallel release."""
import json,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from version_bundle import build,encode,sha
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/n14-performance-20260928'

if __name__=='__main__':
    manifest=build(ROOT/'src')[1]
    prefixes=('test_foldx','test_n14','test_variant_report','test_local_delivery','test_user_report',
              'test_workflow_performance','test_local_workflow','test_real_service_api','test_resident_process','test_resident_assembly')
    paths=sorted(p for p in (ROOT/'tests').glob('test_*.py') if p.name.startswith(prefixes))
    cmd=[sys.executable,'-X','utf8','-B','-m','pytest','-o','addopts=','-p','no:cacheprovider','-q',
         *map(str,paths),'--junitxml='+str(OUT/'final-recheck.junit.xml')]
    done=subprocess.run(cmd,cwd=ROOT)
    if done.returncode:raise SystemExit(done.returncode)
    assert manifest==build(ROOT/'src')[1]
    (OUT/'tested-source.json').write_bytes(encode(dict(source_hashes=manifest,source_sha256=sha(encode(manifest)),test_files=[p.name for p in paths])))
    latest={}
    for name in ('full.junit.xml','final-recheck.junit.xml'):
        for c in ET.parse(OUT/name).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    value=dict(total=len(cases),passed=sum(not any(c.find(n) is not None for n in ('failure','error','skipped')) for c in cases),
        skipped=sum(c.find('skipped') is not None for c in cases),failed=sum(any(c.find(n) is not None for n in ('failure','error')) for c in cases),
        source_sha256=sha(encode(manifest)),method='full current-root run plus final affected recheck')
    (OUT/'regression-summary.json').write_bytes(encode(value));print(json.dumps(value))
