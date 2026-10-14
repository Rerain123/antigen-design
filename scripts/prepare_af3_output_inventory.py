import yaml
from prepare_af3_data_search_inspection import documents, ROOT

NAME = 'antigen-af3-output-inventory-r01'
CODE = '''from pathlib import Path
import json
root=Path('/runtime/inference-r01')
for path in sorted(root.rglob('*')):
    if path.is_file():
        print(path.relative_to(root), path.stat().st_size)
        if 'sample-0' in str(path) and path.suffix == '.cif':
            print('CIF_START', path.read_text()[:14000])
        if 'sample-0' in str(path) and 'summary_confidences' in path.name:
            print('SUMMARY',path.read_text())
        if 'sample-0' in str(path) and path.name.endswith('_confidences.json') and 'summary' not in path.name:
            value=json.loads(path.read_bytes());print('CONFIDENCE_KEYS',list(value));print('ATOM_PLDDTS',value.get('atom_plddts',[])[:6])
'''

if __name__ == '__main__':
    cm, policy, job = documents()
    for doc in (cm, policy, job):
        doc['metadata']['name'] = NAME
    cm['data'] = {'inventory.py': CODE}
    policy['spec']['podSelector']['matchLabels'] = {'app':NAME}
    job['spec']['template']['metadata']['labels'] = {'app':NAME}
    pod=job['spec']['template']['spec']
    pod['volumes'][0]['configMap']['name']=NAME
    pod['containers'][0]['command'][-1]='/inspect/inventory.py'
    target=ROOT/'deploy/alphafold3/output-inventory.r01.rancher.yaml'
    target.write_text(yaml.safe_dump_all([cm,policy,job],sort_keys=False),encoding='utf-8')
    print(target)
