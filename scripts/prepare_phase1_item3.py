"""Item 3 service overlay using the existing guarded deployment renderer."""
import prepare_phase1_item2 as renderer
import base64

NAME='antigen-phase1-item3-r01'
OUT=renderer.common.ROOT/'deploy/phase1-item3/r01'
EVIDENCE=renderer.common.ROOT/'discovery/t01-phase1-real/phase1-item3-20260925'
FILES=('development/developability/camsol.py','development/developability/compute.py',
       'development/developability/policy.py','development/developability/service.py')


def configure():
    renderer.NAME=NAME;renderer.OUT=OUT;renderer.EVIDENCE=EVIDENCE;renderer.FILES=FILES
    return renderer


def render(live):
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    spec=live['spec']['template']['spec']
    assert not any(v['name']==NAME for v in spec['volumes'])
    index=next(i for i,c in enumerate(spec['containers']) if c['name']=='service')
    original=spec['containers'][index]['volumeMounts'];prefix='/app/src/t01_phase1_real/'
    mounts=[m for m in original if m['mountPath'] not in {prefix+n for n in FILES}]
    mounts += [dict(name=NAME,mountPath=prefix+n,subPath='p'+str(i),readOnly=True) for i,n in enumerate(FILES)]
    assert len({m['mountPath'] for m in mounts})==len(mounts)
    path=f'/spec/template/spec/containers/{index}/volumeMounts'
    patch=[dict(op='test',path='/metadata/uid',value=live['metadata']['uid']),
           dict(op='test',path='/metadata/resourceVersion',value=live['metadata']['resourceVersion']),
           dict(op='replace',path=path,value=mounts),
           dict(op='add',path='/spec/template/spec/volumes/-',value=dict(name=NAME,configMap=dict(name=NAME)))]
    rollback=[dict(op='test',path=path,value=mounts),dict(op='replace',path=path,value=original)]
    cm=dict(apiVersion='v1',kind='ConfigMap',metadata=dict(name=NAME,namespace='him-ws'),immutable=True,
        binaryData={'p'+str(i):base64.b64encode((renderer.common.ROOT/'src/t01_phase1_real'/n).read_bytes()).decode()
                    for i,n in enumerate(FILES)})
    return cm,patch,rollback


if __name__=='__main__':
    renderer.render=render
    configure().main()
