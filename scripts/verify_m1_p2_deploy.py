"""Hash the mounted P2 code/assets and recheck the existing single GPU guard."""
import hashlib
import json
import subprocess
import sys
import run_m1_p2_probe as p
import prepare_m1_p2_deploy as deployment
import inspect_m1_p2_profiles as profiles
import audit_unified_gpu_entry_guard as guard


def main():
    paths=deployment.FILES+[r['path'] for r in deployment.SCALES.values()]
    expected={path:hashlib.sha256((p.ROOT/path).read_bytes()).hexdigest() for path in paths}
    code="""import json,hashlib,sys
from pathlib import Path
expected=json.load(sys.stdin)
print(json.dumps({p:hashlib.sha256((Path('/app')/p).read_bytes()).hexdigest() for p in expected}))
"""
    mounted=p.deploy.remote(code,expected)
    assert mounted==expected,'Mounted P2 code or scale bytes differ'
    live=json.loads(subprocess.check_output(p.deploy.K+['get','deployment','antigen-design','-o','json']))
    spec=live['spec']['template']['spec'];status=live['status']
    assert status.get('observedGeneration')==live['metadata']['generation'] and status.get('readyReplicas')==1 and status.get('updatedReplicas')==1
    volumes={v['name']:v.get('configMap',{}).get('name') for v in spec['volumes'] if 'configMap' in v}
    assert volumes['m1-p2-code']==deployment.NAME and volumes['esmfold2-code']==deployment.ESM_NAME
    assert spec.get('automountServiceAccountToken') is False
    profiles.main()
    result=dict(status='M1_P2_DEPLOYED_CODE_HASHES_PASS',generation=live['metadata']['generation'],
        deployment='him-ws/antigen-design',replicas=1,ready=True,configmaps=volumes,mounted_hashes=mounted,
        gpu_configuration_changed=False,credentials_recorded=False)
    p.save('deployment-verification.json',result)
    guard.OUT=p.OUT/'gpu-entry-guard.json';sys.argv=['gpu-entry-guard'];guard.main()
    print(result['status'])


if __name__=='__main__':main()
