"""Generate independent zero-GPU, read-only inference audit."""
import yaml
from prepare_af3_data_search_inspection import documents as base, ROOT

NAME = 'antigen-af3-inference-inspect-r01'
OUTPUT = ROOT / 'deploy/alphafold3/inference-inspect.r01.rancher.yaml'


def documents():
    cm, policy, job = base()
    for doc in (cm, policy, job):
        doc['metadata']['name'] = NAME
    cm['data'] = {'inspect_af3_inference.py': (ROOT / 'scripts/inspect_af3_inference.py').read_text(encoding='utf-8')}
    policy['spec']['podSelector']['matchLabels'] = {'app': NAME}
    job['spec']['template']['metadata']['labels'] = {'app': NAME}
    pod = job['spec']['template']['spec']
    pod['volumes'][0]['configMap']['name'] = NAME
    pod['containers'][0]['command'][-1] = '/inspect/inspect_af3_inference.py'
    return [cm, policy, job]


if __name__ == '__main__':
    OUTPUT.write_text(yaml.safe_dump_all(documents(), sort_keys=False), encoding='utf-8')
    print(OUTPUT)
