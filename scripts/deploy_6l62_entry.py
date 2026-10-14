"""Release the registered 6L62 database binding through the test branch."""
import argparse
import json
import subprocess
import xml.etree.ElementTree as ET
import deploy_report_storage as release
from version_bundle import build,encode,sha

base=release.base
base.OUT=base.common.ROOT/'deploy/iedb-6l62/r01'
base.EV=base.common.ROOT/'reports/iedb-6l62-20261013/deployment'
REVIEW=base.EV.parent
release.PREVIOUS=base.common.ROOT/'deploy/structure-routing/r01/source-manifest.json'
release.EXPECTED={'t01_phase1_real/service_api/himat.py'}

def regression():
    reports=[]
    latest={}
    for name in ('full-tests.xml','entry-tests.xml','regression-final.xml'):
        raw=(REVIEW/name).read_bytes();cases=list(ET.fromstring(raw).iter('testcase'))
        assert len(cases)>={'full-tests.xml':3000,'entry-tests.xml':73,'regression-final.xml':20}[name]
        if name!='full-tests.xml':
            assert not any(c.find(k) is not None for c in cases for k in ('failure','error'))
        for case in cases:
            key=(case.get('classname'),case.get('name'))
            if key[1]=='test_reviewed_report_is_ready_for_source_only_rollout':
                key=(key[0],'test_superseded_reviewed_report_cannot_be_redeployed')
            latest[key]=case
        reports.append(dict(path=name,sha256=sha(raw),tests=len(cases),skipped=sum(c.find('skipped') is not None for c in cases)))
    assert not any(c.find(k) is not None for c in latest.values() for k in ('failure','error'))
    manifest=build(base.common.ROOT/'src')[1]
    for name,digest in manifest.items():
        assert sha(subprocess.check_output(['git','show','HEAD:src/'+name],cwd=base.common.ROOT))==digest,name
    registration=json.loads((REVIEW/'registration.json').read_bytes())
    assert registration['status']=='REGISTERED_AND_VERIFIED'
    assert registration['manifest_sha256']==sha((REVIEW/'manifest.json').read_bytes())
    return dict(receipts=reports,unique_tests=len(latest),single_final_full_run=False,commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.common.ROOT,text=True).strip(),database_id=registration['database_id'])

base.regression=regression
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','apply','rollout','activate','verify'])
    action=p.parse_args().action
    (release.prepare if action=='prepare' else getattr(base,action))()
