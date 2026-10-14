import copy
import json
import pytest
from t01_phase1_real.deployment.site import render_site
from t01_phase1_real.deployment.kubernetes import scientific_job_spec

IMAGE='registry.local/antigen/control@sha256:'+'b'*64


def site():
    return dict(schema_version='0.1.0',namespace='him-ws',api_server='https://kubernetes.default.svc',
        control_image=IMAGE,runtime_claim='antigen-runtime',storage_class='ceph-rbd',storage_size='2Ti',
        source_assets_claim='antigen-source-assets',credentials_secret='antigen-credentials',image_pull_secrets=['antigen-pull'],
        tools={'structure':dict(image=IMAGE,asset_claim='antigen-structure',gpu_resource_key=None)},
        database_claims={'blast':'antigen-blast','homology':'antigen-homology','domains':'antigen-domains'})


def test_site_renderer_wires_launcher_assets_and_separates_admin_permissions():
    value=site();before=copy.deepcopy(value);result=render_site(value)
    assert value==before
    app=result['application']
    assert not {'Namespace','Secret','Role','RoleBinding'}&{d['kind'] for d in app}
    assert [d['kind'] for d in result['administrator']]==['Role','RoleBinding']
    pod=next(d for d in app if d['kind']=='Deployment')['spec']['template']['spec'];worker=pod['containers'][0]
    assert dict((e['name'],e['value']) for e in worker['env'])['T01_KUBERNETES_CONFIG_FILE']=='/etc/t01-launcher.json'
    assert any(m.get('subPath')=='launcher.json' and m['readOnly'] for m in worker['volumeMounts'])
    config=json.loads(next(d for d in app if d['kind']=='ConfigMap')['data']['launcher.json'])
    assert config==result['launcher'] and config['namespace']=='him-ws'
    assert any(m['mountPath']=='/app/var/t01-phase1-real/tool-assets' and m['readOnly'] for m in worker['volumeMounts'])
    assert worker['args'][-2:]==['--homology-database-root','/t01/databases/homology']
    assert pod['imagePullSecrets']==[{'name':'antigen-pull'}]
    job=scientific_job_spec('structure','one',scientific_image=IMAGE,control_image=IMAGE,asset_claim='assets',image_pull_secrets=config['image_pull_secrets'])
    assert job['spec']['template']['spec']['imagePullSecrets']==pod['imagePullSecrets']


@pytest.mark.parametrize('field,value',[
    ('namespace','a/b'),('api_server','https://name:password@cluster'),('api_server','http://cluster'),
    ('control_image','registry/x:latest'),('control_image','registry/x@sha256:'+'0'*64),
    ('image_pull_secrets',['duplicate','duplicate']),('source_assets_claim','../assets'),
    ('tools',{}),('database_claims',{'arbitrary':'claim'}),('credentials','plain-text'),
])
def test_site_rejects_ambiguous_or_secret_bearing_inputs(field,value):
    config=site();config[field]=value
    with pytest.raises(ValueError):render_site(config)
