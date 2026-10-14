"""Prepare a N11 confirmation and execution-report overlay; apply only after all backend work stops."""
import argparse
import base64
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

import yaml
import prepare_m1_p1_deploy as common
from prepare_himat_p1_fixes import idle

OUT = common.ROOT / 'deploy/m1-p4/n11-confirm-r15'
NAME = 'antigen-m1-n11-confirm-r15'
FILES = ('service_api/himat.py','service_api/progress.py','service_api/transport.py','service_api/app.py',
    'development/workflow/service.py','development/workflow/engineering.py',
    'development/workflow/confirmation.py','development/workflow/reporting.py',
    'development/design_backend/policy.py','development/design_backend/compute.py',
    'development/proteinmpnn/policy.py','development/proteinmpnn/mapping.py','development/local_delivery/policy.py',
    'development/local_delivery/source.py','development/local_delivery/compute.py')
TESTS = common.ROOT / 'discovery/t01-phase1-real/m1-p4-20260922/n11-confirm-full-r03.junit.xml'


def hashes():
    return {n: hashlib.sha256((common.ROOT / 'src/t01_phase1_real' / n).read_bytes()).hexdigest() for n in FILES}


def render(live):
    if live['spec']['replicas'] != 1 or live['spec']['strategy'] != {'type': 'Recreate'}:
        raise RuntimeError('Expected singleton Recreate deployment')
    spec = live['spec']['template']['spec']
    if any(v['name'] == NAME for v in spec['volumes']):
        raise RuntimeError('Progress overlay already exists')
    index = next(i for i, c in enumerate(spec['containers']) if c['name'] == 'service')
    targets = {'/app/src/t01_phase1_real/' + n for n in FILES}
    mounts = [m for m in spec['containers'][index]['volumeMounts'] if m['mountPath'] not in targets]
    mounts += [dict(name=NAME, mountPath='/app/src/t01_phase1_real/' + n,
                    subPath='p' + str(i), readOnly=True) for i, n in enumerate(FILES)]
    patch = [dict(op='test', path='/metadata/uid', value=live['metadata']['uid']),
             dict(op='test', path='/metadata/resourceVersion', value=live['metadata']['resourceVersion']),
             dict(op='replace', path=f'/spec/template/spec/containers/{index}/volumeMounts', value=mounts),
             dict(op='add', path='/spec/template/spec/volumes/-', value=dict(name=NAME, configMap=dict(name=NAME)))]
    cm = dict(apiVersion='v1', kind='ConfigMap', metadata=dict(name=NAME, namespace='him-ws'), immutable=True,
              binaryData={'p' + str(i): base64.b64encode((common.ROOT / 'src/t01_phase1_real' / n).read_bytes()).decode()
                          for i, n in enumerate(FILES)})
    return cm, patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply:
        idle()  # Never restart a Pod containing an active scientific tool.
        prepared = json.loads((OUT / 'preflight.json').read_bytes())
        if prepared['source_hashes'] != hashes():
            raise RuntimeError('Source changed after preparation')
        for name, digest in prepared['prepared_sha256'].items():
            if hashlib.sha256((OUT / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Prepared bytes changed')
        suites = list(ET.parse(TESTS).getroot().iter('testsuite'))
        if not suites or any(int(s.get('failures', 0)) or int(s.get('errors', 0)) for s in suites):
            raise RuntimeError('Current root regression must pass')
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file',
                                  str(OUT / 'deployment.patch.json'), '--dry-run=server', '-o', 'name'], check=True)
        idle()
        subprocess.run(common.K + ['create', '-f', str(OUT / 'configmap.yaml')], check=True)
        subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file',
                                  str(OUT / 'deployment.patch.json')], check=True)
        print('N11_CONFIRM_ROLLOUT_REQUESTED')
        return
    state = common.idle()  # Observation only: preparation is allowed while a task runs.
    live = json.loads(subprocess.check_output(common.K + ['get', 'deployment', 'antigen-design', '-o', 'json']))
    cm, patch = render(live)
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'configmap.yaml').write_text(yaml.safe_dump(cm, sort_keys=False), encoding='utf-8')
    (OUT / 'deployment.patch.json').write_text(json.dumps(patch, indent=2) + '\n', encoding='utf-8')
    (OUT / 'preflight.json').write_text(json.dumps(dict(observed_state=state, source_hashes=hashes(),
        prepared_sha256={n: hashlib.sha256((OUT / n).read_bytes()).hexdigest()
                        for n in ('configmap.yaml', 'deployment.patch.json')},
        applied=False, requires_fresh_idle_and_revision_check=True), indent=2) + '\n', encoding='utf-8')
    subprocess.run(common.K + ['create', '--dry-run=server', '-f', str(OUT / 'configmap.yaml')], check=True)
    subprocess.run(common.K + ['patch', 'deployment', 'antigen-design', '--type=json', '--patch-file',
                              str(OUT / 'deployment.patch.json'), '--dry-run=server', '-o', 'name'], check=True)
    print('N11_CONFIRM_PREPARED_NOT_APPLIED', OUT)


if __name__ == '__main__':
    main()
