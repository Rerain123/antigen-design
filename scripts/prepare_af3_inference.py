"""Generate the single-GPU, offline five-sample acceptance job."""
import yaml
from prepare_af3_gpu_probe import probe_documents
from prepare_af3_data_search import ROOT

NAME = 'antigen-af3-inference-r01'
OUTPUT = ROOT / 'deploy/alphafold3/inference.r01.rancher.yaml'


def documents():
    cm, policy, job = probe_documents()
    for doc in (cm, policy, job):
        doc['metadata']['name'] = NAME
    cm['data'] = {name: (ROOT / 'scripts' / name).read_text(encoding='utf-8') for name in (
        'run_af3_inference.py', 'inspect_af3_data_search.py', 'prepare_af3_data_search.py')}
    policy['spec']['podSelector']['matchLabels'] = {'app': NAME}
    job['spec']['activeDeadlineSeconds'] = 7200
    job['spec']['template']['metadata']['labels'] = {'app': NAME}
    # Keep the exact device successfully validated by the immediately preceding probe.
    job['spec']['template']['metadata']['annotations']['nvidia.com/use-gpuuuid'] = 'GPU-f098e2d4-4cf3-a2c2-3503-6cca5bedde31'
    pod = job['spec']['template']['spec']
    pod['volumes'][0]['configMap']['name'] = NAME
    pod['volumes'].append({'name':'weights','persistentVolumeClaim':{'claimName':'antigen-af3-models','readOnly':True}})
    c = pod['containers'][0]
    c['name'] = 'inference'
    c['command'][-1] = '/runner/run_af3_inference.py'
    c['resources']['requests'] = {'cpu':'4','memory':'32Gi'}
    c['resources']['limits'].update({'cpu':'8','memory':'96Gi'})
    c['volumeMounts'].append({'name':'weights','mountPath':'/weights','readOnly':True})
    return [cm, policy, job]


if __name__ == '__main__':
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding='utf-8')
    print(OUTPUT)
