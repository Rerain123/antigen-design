"""Repair native alias mounts only; preserve complete source snapshot and model configuration."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import prepare_version_unification as deploy
import prepare_m1_p1_deploy as common
from version_bundle import build,encode,sha

OUT=common.ROOT/'deploy/n02-slot-fix/r01'
EVIDENCE=common.ROOT/'reports/n02-slot-fix-20260928'


def checks():
    baseline=common.ROOT/'reports/msa-scan-20260928'
    manifest=build(common.ROOT/'src')[1]
    previous=json.loads((baseline/'deployment-verification.json').read_bytes())
    assert sha(encode(manifest))==previous['source_sha256'], 'This repair must not change scientific application code'
    assert json.loads((EVIDENCE/'linux-slot-probe.json').read_bytes())['status']=='PASS'
    cases=list(ET.parse(EVIDENCE/'deployment.junit.xml').iter('testcase'))
    assert len(cases)>=15 and all(not any(c.find(s) is not None for s in ('failure','error','skipped')) for c in cases)
    names=['scripts/prepare_version_unification.py','scripts/verify_version_unification.py',
           'scripts/deploy_n02_slot_fix.py','scripts/probe_n02_slot_mounts.py','tests/test_version_unification.py']
    return dict(source_sha256=previous['source_sha256'],deployment_tests=len(cases),
        script_hashes={n:sha((common.ROOT/n).read_bytes()) for n in names},
        receipts={n:sha((EVIDENCE/n).read_bytes()) for n in ('linux-slot-probe.json','deployment.junit.xml')},
        application_regression_reference='reports/msa-scan-20260928/closeout.json',
        application_regression_sha256=sha((baseline/'closeout.json').read_bytes()))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','apply','verify'])
    action=parser.parse_args().action
    if action=='verify':
        import verify_version_unification as verify
        verify.OUT=OUT;verify.EVIDENCE=EVIDENCE;verify.main();return
    state=deploy.idle();checked=checks()
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    if action=='apply':
        pre=json.loads((OUT/'preflight.json').read_bytes())
        assert pre['regression']==checked
        for name,digest in pre['artifacts'].items():assert sha((OUT/name).read_bytes())==digest
        # Same immutable source bundle: verify it byte-for-byte and reuse it.
        expected=json.loads((OUT/'configmap.json').read_bytes())
        actual=json.loads(subprocess.check_output(common.K+['get','configmap',expected['metadata']['name'],'-o','json']))
        assert actual['immutable'] and actual['binaryData']==expected['binaryData']
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('N02_SLOT_MOUNT_REPAIR_SUBMITTED');return
    cm,patch,rollback,manifest=deploy.render(live)
    before=live['spec']['template'];after=patch[-1]['value']
    expected=json.loads(json.dumps(before))
    deploy.detach_native_alias_mounts(expected['spec'])
    assert expected==after, 'Only redundant native /app mounts may change'
    assert after!=before, 'Repair already applied'
    OUT.mkdir(parents=True,exist_ok=False)
    (EVIDENCE/'before-deployment.json').write_bytes(encode(live))
    count=common.remote("import sqlite3,json; db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True); print(json.dumps(dict(job_count=db.execute('SELECT count(*) FROM jobs').fetchone()[0])))")
    (EVIDENCE/'before-job-count.json').write_bytes(encode(count))
    artifacts={'configmap.json':cm,'deployment.patch.json':patch,'rollback.patch.json':rollback}
    for name,value in artifacts.items():(OUT/name).write_bytes(encode(value))
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    pre=dict(status='PREPARED',before_generation=live['metadata']['generation'],idle=state,
        source_hashes=manifest,source_sha256=sha(encode(manifest)),regression=checked,
        artifacts={n:sha((OUT/n).read_bytes()) for n in artifacts})
    (OUT/'preflight.json').write_bytes(encode(pre));print(json.dumps(dict(status='PREPARED',generation=pre['before_generation'],removed_mounts=18)))


if __name__=='__main__':main()
