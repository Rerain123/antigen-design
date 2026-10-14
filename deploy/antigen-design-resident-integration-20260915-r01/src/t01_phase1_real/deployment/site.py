"""Explicit site configuration rendering; never reads credentials or applies resources."""
import copy
import json
from urllib.parse import urlsplit

from .kubernetes import control_plane_documents, SCIENTIFIC_SOURCE_IMAGE_IDS, _name, _digest_image


def validate_site(value):
    fields={'schema_version','namespace','api_server','control_image','runtime_claim','storage_class',
            'storage_size','source_assets_claim','credentials_secret','image_pull_secrets','tools','database_claims'}
    if not isinstance(value,dict) or not fields<=set(value)<=fields|{'qualification'} or value['schema_version']!='0.1.0':
        raise ValueError('Exact site configuration v0.1.0 required')
    for key in ('namespace','runtime_claim','source_assets_claim','credentials_secret','storage_class'):
        _name(value[key],key)
    _digest_image(value['control_image'],'control image')
    parsed=urlsplit(value['api_server'])
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Explicit HTTPS API origin required')
    pulls=value['image_pull_secrets']
    if not isinstance(pulls,list) or len(pulls)>8 or any(not isinstance(p,str) for p in pulls) or len(set(pulls))!=len(pulls):
        raise ValueError('Unique bounded image pull secret names required')
    for name in pulls:_name(name,'image pull secret')
    if not isinstance(value['tools'],dict) or not value['tools'] or set(value['tools'])-set(SCIENTIFIC_SOURCE_IMAGE_IDS):
        raise ValueError('At least one supported target tool required')
    for tool,entry in value['tools'].items():
        if not isinstance(entry,dict) or set(entry)!={'image','asset_claim','gpu_resource_key'}:
            raise ValueError('Explicit image, asset claim and GPU resource required')
        _digest_image(entry['image'],'tool image');_name(entry['asset_claim'],'asset claim')
        # Use the same admission as the actual Job builder.
        from .kubernetes import scientific_job_spec
        scientific_job_spec(tool,'preflight',scientific_image=entry['image'],control_image=value['control_image'],
                            asset_claim=entry['asset_claim'],gpu_resource_key=entry['gpu_resource_key'])
    if not isinstance(value['database_claims'],dict) or set(value['database_claims'])-{'blast','homology','domains'}:
        raise ValueError('Only explicit supported database claim mappings accepted')
    for claim in value['database_claims'].values():_name(claim,'database claim')
    for tool in ('blast','homology'):
        if tool in value['tools'] and value['database_claims'].get(tool)!=value['tools'][tool]['asset_claim']:
            raise ValueError('Database tool and control plane must mount the same registered claim')
    if 'qualification' in value:
        import re
        q=value['qualification']
        if not isinstance(q,dict) or set(q)!={'claim','sha256'} or not isinstance(q['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',q['sha256']):
            raise ValueError('Qualification claim and exact receipt hash required')
        _name(q['claim'],'qualification claim')
    for image in [value['control_image']]+[entry['image'] for entry in value['tools'].values()]:
        if '.invalid/' in image or image.endswith('0'*64):raise ValueError('Placeholder image cannot be rendered for a site')
    return copy.deepcopy(value)


def render_site(value):
    """Return application and administrator documents separately for an existing namespace."""
    value=validate_site(value)
    docs=control_plane_documents(value['control_image'],namespace=value['namespace'],runtime_claim=value['runtime_claim'],
        storage_class=value['storage_class'],storage_size=value['storage_size'])
    docs=[d for d in docs if d['kind'] not in ('Namespace','Secret')]
    config=next(d for d in docs if d['kind']=='ConfigMap')
    launcher=dict(server=value['api_server'],token_file='/var/run/secrets/kubernetes.io/serviceaccount/token',
        ca_file='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt',namespace=value['namespace'],
        runtime_claim=value['runtime_claim'],runtime_volume_root='/var/lib/t01',control_image=value['control_image'],
        tools=value['tools'],image_pull_secrets=value['image_pull_secrets'])
    pod=next(d for d in docs if d['kind']=='Deployment')['spec']['template']['spec']
    pod['imagePullSecrets']=[{'name':name} for name in value['image_pull_secrets']]
    worker=pod['containers'][0]
    worker['volumeMounts'].append({'name':'config','mountPath':'/etc/t01-launcher.json','subPath':'launcher.json','readOnly':True})
    if 'qualification' in value:
        launcher['qualification']={'path':'/etc/t01/qualification/qualification.json','sha256':value['qualification']['sha256']}
        pod['volumes'].append({'name':'qualification','persistentVolumeClaim':{'claimName':value['qualification']['claim']}})
        worker['volumeMounts'].append({'name':'qualification','mountPath':'/etc/t01/qualification','readOnly':True})
    config['data']['launcher.json']=json.dumps(launcher,sort_keys=True,separators=(',',':'))
    worker['env'].append({'name':'T01_KUBERNETES_CONFIG_FILE','value':'/etc/t01-launcher.json'})
    next(v for v in pod['volumes'] if v['name']=='credentials')['secret']['secretName']=value['credentials_secret']
    # Preserve the authoritative, relative asset paths used by verify_assets.
    pod['volumes'].append({'name':'source-assets','persistentVolumeClaim':{'claimName':value['source_assets_claim']}})
    worker['volumeMounts'].append({'name':'source-assets','mountPath':'/app/var/t01-phase1-real/tool-assets','readOnly':True})
    for tool,claim in sorted(value['database_claims'].items()):
        name='database-'+tool;mount='/t01/databases/'+tool
        pod['volumes'].append({'name':name,'persistentVolumeClaim':{'claimName':claim}})
        worker['volumeMounts'].append({'name':name,'mountPath':mount,'subPath':'database','readOnly':True})
        worker['args'].extend(['--'+tool+'-database-root',mount])
    administrator=[d for d in docs if d['kind'] in ('Role','RoleBinding')]
    application=[d for d in docs if d['kind'] not in ('Role','RoleBinding')]
    return {'application':application,'administrator':administrator,'launcher':launcher}
