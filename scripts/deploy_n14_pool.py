"""N14 complete-pool full-source release; never starts a scientific job."""
import json
import sys
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/n14-pool-20260927/r02'
release.OUT=release.common.ROOT/'deploy/n14-pool/r02'


def regression():
    p=release.EVIDENCE.parent
    tested=json.loads((p/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    names=['full.junit.xml','final-affected.junit.xml'];latest={}
    for name in names:
        for c in ET.parse(p/name).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<2670 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='full current-root run plus final affected source tests',
        receipts={n:sha((p/n).read_bytes()) for n in [*names,'tested-source.json']})


release.regression=regression
if __name__=='__main__':
    if sys.argv[1]=='probe':
        import probe_version_unification as probe
        probe.REMOTE=probe.REMOTE.replace("'development.workflow.stability_scope')", "'development.workflow.stability_scope','development.workflow.stability_pool')")
    if sys.argv[1]=='replay':
        import verify_n12_control_replay as replay
        replay.REMOTE=replay.REMOTE.replace('report=compute.evaluate(report_body,files)',
            "from t01_phase1_real.development.workflow.stability_pool import pool\n"
            "n14,why=pool(proxy,body,view['nodes'])\n"
            "assert why=='NO_VALIDATED_MUTANT_FOR_N14' and n14['eligible_count']==0 and len(n14['excluded'])==24\n"
            "files['input/n14-pool.json']=encode(dict(pool=n14,state='skipped',reason_code=why,source=None))\n"
            "report=compute.evaluate(report_body,files)")
    release.main()
