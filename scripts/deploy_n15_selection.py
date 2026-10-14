"""N15 full-snapshot engineering release; no new model/scientific jobs."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import prepare_version_unification as deploy
import prepare_m1_p1_deploy as common
from version_bundle import build, encode, sha

EVIDENCE=common.ROOT/'reports/n15-selection-20260927'
OUT=common.ROOT/'deploy/n15-selection/r01'


def regression():
    tested=json.loads((EVIDENCE/'tested-source.json').read_bytes())
    if build(common.ROOT/'src')[1]!=tested['source_hashes']:
        raise RuntimeError('Project source changed after final affected-test checks')
    names=('full.junit.xml','final-recheck.junit.xml','selection-final.junit.xml','utf8-recheck.junit.xml')
    latest={}
    for name in names:
        for case in ET.parse(EVIDENCE/name).iter('testcase'):
            latest[(case.get('classname'),case.get('name'))]=case
    cases=list(latest.values())
    if len(cases)<2600 or any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        raise RuntimeError('Full current-root regression must pass')
    return dict(total=len(cases),skipped=sum(c.find('skipped') is not None for c in cases),
                method='full current-root run plus final affected-test recheck',
                receipts={name:sha((EVIDENCE/name).read_bytes()) for name in (*names,'tested-source.json')})


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['probe','prepare','apply','verify','replay'])
    action=parser.parse_args().action
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    deploy.OUT=OUT;deploy.EVIDENCE=EVIDENCE
    if action=='probe':
        import probe_version_unification as probe
        probe.OUT=EVIDENCE;probe.main();return
    if action=='verify':
        import verify_version_unification as verify
        verify.OUT=OUT;verify.EVIDENCE=EVIDENCE;verify.main();return
    if action=='replay':
        import verify_n12_control_replay as replay
        replay.deploy.EVIDENCE=EVIDENCE
        replay.REMOTE=replay.REMOTE.replace("data=dict(n12_validation=[fact],variant_report=report)",
            "assert report['engineering_selection']['status']=='ALL_EXCLUDED'\n"
            "assert len(report['engineering_selection']['inventory'])==24\n"
            "assert report['engineering_selection']['top20']==[]\n"
            "data=dict(n12_validation=[fact],variant_report=report)")
        replay.main();return
    state=deploy.idle()
    checks=regression()
    if action=='apply':
        pre=json.loads((OUT/'preflight.json').read_bytes())
        if build(common.ROOT/'src')[1]!=pre['source_hashes'] or pre['regression']!=checks:
            raise RuntimeError('Sources or test receipt changed since preparation')
        deploy.compatibility(pre['source_hashes'])
        for name,digest in pre['artifacts'].items():
            if sha((OUT/name).read_bytes())!=digest:raise RuntimeError('Prepared artifact changed')
        subprocess.run(common.K+['create','-f',str(OUT/'configmap.json')],check=True)
        subprocess.run(common.K+['patch','deployment','antigen-design','--type=json',
            '--patch-file',str(OUT/'deployment.patch.json')],check=True)
        print('N15_SOURCE_SNAPSHOT_SUBMITTED');return
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    cm,patch,rollback,manifest=deploy.render(live)
    deploy.compatibility(manifest)
    OUT.mkdir(parents=True,exist_ok=False)
    (EVIDENCE/'before-deployment.json').write_bytes(encode(live))
    count=common.remote("import sqlite3,json; db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True); print(json.dumps(dict(job_count=db.execute('SELECT count(*) FROM jobs').fetchone()[0])))")
    (EVIDENCE/'before-job-count.json').write_bytes(encode(count))
    artifacts={'configmap.json':cm,'deployment.patch.json':patch,'rollback.patch.json':rollback}
    for name,value in artifacts.items():(OUT/name).write_bytes(encode(value)+b'\n')
    for command in (['create','-f',str(OUT/'configmap.json')],
                    ['patch','deployment','antigen-design','--type=json','--patch-file',str(OUT/'deployment.patch.json')]):
        subprocess.run(common.K+command+['--dry-run=server','-o','name'],check=True)
    pre=dict(status='PREPARED',before_generation=live['metadata']['generation'],idle=state,
        source_hashes=manifest,source_sha256=sha(encode(manifest)),regression=checks,
        artifacts={name:sha((OUT/name).read_bytes()) for name in artifacts})
    (OUT/'preflight.json').write_bytes(encode(pre)+b'\n')
    print(json.dumps(dict(status='PREPARED',files=len(manifest),source_sha256=pre['source_sha256'])))


if __name__=='__main__':main()
