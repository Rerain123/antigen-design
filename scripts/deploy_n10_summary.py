"""N10 S40 complete-candidate source release and read-only historical replay."""
import json
import sys
import xml.etree.ElementTree as ET
import deploy_n15_selection as release
from version_bundle import build,sha

release.EVIDENCE=release.common.ROOT/'reports/n10-summary-20260927'
release.OUT=release.common.ROOT/'deploy/n10-summary/r01'


def regression():
    p=release.EVIDENCE
    tested=json.loads((p/'tested-source.json').read_bytes())
    if build(release.common.ROOT/'src')[1]!=tested['source_hashes']:raise RuntimeError('Untested source changes')
    names=['full.junit.xml','final-affected.junit.xml'];latest={}
    for name in names:
        for c in ET.parse(p/name).iter('testcase'):latest[(c.get('classname'),c.get('name'))]=c
    cases=list(latest.values())
    if len(cases)<2709 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
        method='full current-root run plus final affected source tests',
        receipts={n:sha((p/n).read_bytes()) for n in [*names,'tested-source.json']})


release.regression=regression
if __name__=='__main__':
    if sys.argv[1]=='probe':
        import probe_version_unification as probe
        probe.REMOTE=probe.REMOTE.replace("'development.workflow.stability_scope')",
            "'development.workflow.stability_scope','development.workflow.candidate_developability')")
    if sys.argv[1]=='replay':
        import verify_n12_control_replay as replay
        replay.REMOTE=replay.REMOTE.replace('report=compute.evaluate(report_body,files)',
            "from t01_phase1_real.development.workflow.candidate_developability import observations,request as n10_request\n"
            "receipts=decode(files['input/source-receipts.json'])\n"
            "values={n:decode(files['input/'+n+'-result.json']) for n in policy.PRODUCERS if receipts[n]['state']=='available'}\n"
            "records=compute.preselection_rows(report_body,files,values)\n"
            "for n in range(1,25):\n"
            "    req,why=n10_request(proxy,body,view['nodes'],f'c_s{n}_developability')\n"
            "    assert req is None and why=='N10_CANDIDATE_NOT_VALIDATED'\n"
            "    view['nodes'][f'c_s{n}_developability']=dict(state='skipped',reason_code=why)\n"
            "observed=observations(proxy,body,view['nodes'],records,before['run_id'])\n"
            "assert len(observed)==24 and all(r['results']['developability'] is None for r in observed)\n"
            "files['input/candidate-developability.json']=encode(dict(records=observed))\n"
            "report=compute.evaluate(report_body,files)\n"
            "assert len(report['candidate_developability']['records'])==24\n"
            "assert all(r['developability'] is None for r in report['candidate_developability']['records'])")
    release.main()
