"""Scoped S28 service overlay; guarded idle rollout, never starts design jobs."""
import json
import subprocess
import sys
import yaml
import prepare_phase1_item3 as base

NAME='antigen-n12-validation-r02'
OUT=base.renderer.common.ROOT/'deploy/n12-validation/r02'
EVIDENCE=base.renderer.common.ROOT/'reports/n12-validation-20260926'
FILES=('development/workflow/validation.py','development/workflow/design_rounds.py',
       'development/workflow/policy.py','development/workflow/service.py','development/workflow/m1.py',
       'development/variant_report/m1.py','development/variant_report/policy.py',
       'development/variant_report/source.py','development/variant_report/compute.py',
       'development/epitope_protection/policy.py','development/epitope_protection/source.py',
       'development/n12_prediction_evidence.py','development/local_delivery/source.py',
       'development/local_delivery/compute.py','development/local_delivery/policy.py','service_api/user_report.py',
       'development/af3/policy.py','development/af3/result.py','development/af3/source.py')


def render(live):
    cm,patch,rollback=base.render(live)
    spec=live['spec']['template']['spec']
    index=next(i for i,c in enumerate(spec['containers']) if c['name']=='worker-unified-gpu')
    original=spec['containers'][index]['volumeMounts'];names=[n for n in FILES if n.startswith('development/af3/')]
    prefix='/opt/t01/src/t01_phase1_real/'
    mounts=[m for m in original if m['mountPath'] not in {prefix+n for n in names}]
    mounts.extend(dict(name=NAME,mountPath=prefix+n,subPath='p'+str(FILES.index(n)),readOnly=True) for n in names)
    assert len({m['mountPath'] for m in mounts})==len(mounts)
    path=f'/spec/template/spec/containers/{index}/volumeMounts'
    patch.append(dict(op='replace',path=path,value=mounts))
    rollback += [dict(op='test',path=path,value=mounts),dict(op='replace',path=path,value=original)]
    return cm,patch,rollback


def configure():
    base.NAME,base.OUT,base.EVIDENCE,base.FILES=NAME,OUT,EVIDENCE,FILES
    base.renderer.render=render
    return base.configure()


def prepare_unavailable():
    """Create reviewable artifacts only; applying still requires a fresh idle check."""
    renderer=configure();common=renderer.common
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    pods=json.loads(subprocess.check_output(common.K+['get','pods','-l','app.kubernetes.io/name=antigen-design','-o','json']))
    assert live['status'].get('readyReplicas',0)==0,'Use normal guarded preparation for available service'
    cm,patch,rollback=render(live);OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'configmap.yaml').write_text(yaml.safe_dump(cm,sort_keys=False),encoding='utf8')
    for name,value in [('deployment.patch.json',patch),('rollback.patch.json',rollback)]:
        (OUT/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    pre=dict(status='PREPARED_NOT_APPLIED_CLUSTER_UNAVAILABLE',source_hashes=renderer.hashes(),
        before_generation=live['metadata']['generation'],idle=None,
        blocker='Existing deployment unavailable; scheduling reports Insufficient memory. No node read RBAC.',
        pods=[dict(name=p['metadata']['name'],status=p['status']) for p in pods['items']],
        prepared_sha256={n:renderer.sha((OUT/n).read_bytes()) for n in ('configmap.yaml','deployment.patch.json','rollback.patch.json')})
    (OUT/'preflight.json').write_text(json.dumps(pre,indent=2)+'\n',encoding='utf8')
    subprocess.run(common.K+['create','--dry-run=server','-f',str(OUT/'configmap.yaml')],check=True)
    subprocess.run(common.K+['patch','deployment','antigen-design','--type=json','--patch-file',
                            str(OUT/'deployment.patch.json'),'--dry-run=server','-o','name'],check=True)
    (EVIDENCE/'deployment-blocker.json').write_text(json.dumps(pre,indent=2)+'\n',encoding='utf8')
    print(pre['status'])


if __name__=='__main__':
    if sys.argv[1:]==['--prepare-unavailable']:prepare_unavailable()
    else:configure().main()
