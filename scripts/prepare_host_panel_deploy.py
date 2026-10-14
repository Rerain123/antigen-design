"""Guarded host-panel/report overlay; never starts a scientific job."""
import base64
import prepare_phase1_item2 as base

NAME='antigen-host-panel-r01'
OUT=base.common.ROOT/'deploy/host-panel/r01'
EVIDENCE=base.common.ROOT/'reports/n05-duration-20260926'
FILES=('development/netmhc/host-panel.json','development/netmhc/host_panel.py',
       'development/netmhc/policy.py','development/netmhc/pan.py','development/netmhc/service.py',
       'development/netmhc/result.py','development/netmhc/worker.py',
       'development/runtime.py','development/epitope_map/result.py','development/epitope_protection/source.py',
       'development/workflow/service.py','development/wt_draft/compute.py',
       'service_api/himat.py','service_api/user_report.py','service_api/transport.py')


def render(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec'];assert not any(v['name']==NAME for v in spec['volumes'])
    patch=[dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
           dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion'])]
    rollback=[]
    for index,con in enumerate(spec['containers']):
        if con['name']=='service':prefix='/app/src/t01_phase1_real/';names=FILES
        elif con['name']=='worker-netmhc':prefix='/opt/t01/src/t01_phase1_real/';names=('development/netmhc/worker.py',)
        else:continue
        original=con['volumeMounts'];targets={prefix+n for n in names}
        mounts=[m for m in original if m['mountPath'] not in targets]
        mounts += [dict(name=NAME,mountPath=prefix+n,subPath='p'+str(FILES.index(n)),readOnly=True) for n in names]
        assert len({m['mountPath'] for m in mounts})==len(mounts)
        path=f'/spec/template/spec/containers/{index}/volumeMounts'
        patch.append(dict(op='replace',path=path,value=mounts))
        rollback += [dict(op='test',path=path,value=mounts),dict(op='replace',path=path,value=original)]
    patch.append(dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=NAME,configMap=dict(name=NAME))))
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(i):base64.b64encode((base.common.ROOT/'src/t01_phase1_real'/n).read_bytes()).decode() for i,n in enumerate(FILES)})
    return cm,patch,rollback


if __name__=='__main__':
    base.NAME,base.OUT,base.EVIDENCE,base.FILES=NAME,OUT,EVIDENCE,FILES
    base.render=render
    base.main()
