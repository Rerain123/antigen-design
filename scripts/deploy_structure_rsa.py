"""Deploy the authorized AF3 address and per-position RSA repair without scientific jobs."""
import argparse
import json
import xml.etree.ElementTree as ET

import deploy_terminal_sync as base
from version_bundle import encode, sha

base.OUT=base.common.ROOT/'deploy/structure-rsa/r01'
base.EV=base.common.ROOT/'reports/rsa-position-20261010'
PREVIOUS=base.common.ROOT/'deploy/controller-latency/r03/source-manifest.json'
EXPECTED={
    'development/af3/result.py','development/af3/standard.py','development/af3/tool_structure.py',
    'development/developability/compute.py','development/domains/geometry.py','development/epitope_protection/source.py',
    'development/structure/normalization.py','development/structure/result.py','development/structure/worker.py',
    'development/workflow/stability_scope.py','service_api/himat.py','service_api/native_report.py'}


def regression():
    latest={};receipts=[]
    for name in ['full-r01.xml','fix-r02.xml','n10-r02.xml','item3-r02.xml','selection-r02.xml']:
        raw=(base.EV/name).read_bytes();cases=list(ET.fromstring(raw).iter('testcase'))
        if name=='full-r01.xml':assert len(cases)>=3368
        else:assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
        for case in cases:
            key=(case.get('classname'),case.get('name'))
            if name=='full-r01.xml' or key in latest:latest[key]=case
        receipts.append(dict(path=name,sha256=sha(raw),tests=len(cases)))
    cases=list(latest.values())
    assert not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
    frozen=json.loads((base.EV/'frozen.log').read_text(encoding='utf-8').strip())
    assert frozen['status']=='PASS' and frozen['frozen_asset_count']==457
    return dict(tests=len(cases),passed=sum(c.find('skipped') is None for c in cases),
        skipped=sum(c.find('skipped') is not None for c in cases),single_final_full_run=False,
        receipts=receipts,frozen=frozen)


def prior_task():
    return base.common.remote("""import json,sqlite3,hashlib
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
def digest(table):
    rows=db.execute('SELECT data FROM '+table+' ORDER BY data').fetchall()
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
print(json.dumps(dict(job_count=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
    jobs_sha256=digest('jobs'),executions_sha256=digest('executions'))))
""")


def prepare():
    base.OUT.mkdir(parents=True,exist_ok=True);base.EV.mkdir(parents=True,exist_ok=True)
    state=base.common.idle();assert not state['active_jobs'] and state['gpu_state']['phase']=='idle'
    live={n:base.run(['get','deployment',n,'-o','json']) for n in base.NAMES}
    previous=json.loads(PREVIOUS.read_bytes());old_digest=sha(encode(previous))
    assert all(d['spec']['template']['metadata']['annotations']['antigen-design/source-sha256']==old_digest for d in live.values())
    base.save('before-deployments.json',live)
    templates={};config=None;manifest=None
    for name,dep in live.items():
        cm,patch,rollback,m=base.bundle.render(dep)
        assert config is None or config==cm
        config=cm;manifest=m;template=patch[-1]['value']
        assert template['spec']['containers']==dep['spec']['template']['spec']['containers']
        assert len(template['spec']['containers'])==1
        templates[name]=template
        (base.OUT/(name+'.patch.json')).write_bytes(encode(patch))
        (base.OUT/(name+'.rollback.json')).write_bytes(encode(rollback))
    changed=sorted(k for k in set(previous)|set(manifest) if previous.get(k)!=manifest.get(k))
    assert set(changed)=={'t01_phase1_real/'+p for p in EXPECTED}
    (base.OUT/'source-manifest.json').write_bytes(encode(manifest))
    (base.OUT/'templates.json').write_bytes(encode(templates))
    (base.OUT/'configmaps.json').write_bytes(encode(config))
    for obj in config.get('items',[config]):base.run(['create','--dry-run=server','-f','-','-o','name'],obj)
    for name in base.NAMES:
        base.run(['patch','deployment',name,'--type=json','--dry-run=server','--patch-file',str(base.OUT/(name+'.patch.json')),'-o','name'])
    base.save('preparation.json',dict(status='PREPARED',source_sha256=sha(encode(manifest)),files=len(manifest),
        changed_sources=changed,previous_source_sha256=old_digest,deployments=base.NAMES,
        resources_images_commands_unchanged=True,scientific_jobs_submitted=0))
    print('PREPARED',len(manifest),'source files;',len(changed),'changed')


base.regression=regression
base.prior_task=prior_task

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','apply','rollout','activate','verify'])
    action=parser.parse_args().action
    (prepare if action=='prepare' else getattr(base,action))()
