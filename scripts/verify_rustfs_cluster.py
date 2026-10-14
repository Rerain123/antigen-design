"""Run a single RustFS write/read/delete probe from the existing control Pod.

Secret values travel only through captured process memory and exec stdin. The
Deployment is not changed; only a unique data/_probes/ object is briefly created.
"""
import base64
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
K=['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe','--kubeconfig',str(ROOT/'.tmp/himat.kubeconfig'),
   '--request-timeout=180s','-n','him-ws']


def main():
    secret=subprocess.run(K+['get','secret','antigen-design-rustfs','-o','json'],capture_output=True,timeout=45)
    if secret.returncode:
        raise RuntimeError('Cannot read antigen-design-rustfs Secret; values were not displayed.')
    document=json.loads(secret.stdout)
    env={name:base64.b64decode(document['data'][name],validate=True).decode('utf-8') for name in ('RUSTFS_ACCESS_KEY_ID','RUSTFS_SECRET_ACCESS_KEY')}
    env.update(RUSTFS_ENABLED='true',RUSTFS_ENDPOINT_URL='https://rustfs.ne.scqcyz.cn',
               RUSTFS_PUBLIC_BASE_URL='https://rustfs.ne.scqcyz.cn',RUSTFS_BUCKET='antigen-design',RUSTFS_OBJECT_PREFIX='data')
    source=(ROOT/'src/t01_phase1_real/service_api/object_storage.py').read_text(encoding='utf-8')
    source+='\ntry:\n    print(json.dumps(RustFSPublisher.from_environment().probe()))\nexcept StorageError as exc:\n    print(json.dumps({"status":"failed","message":str(exc)}))\n'
    bootstrap="import json,os,sys; p=json.load(sys.stdin); os.environ.update(p['environment']); exec(compile(p['source'],'<rustfs-probe>','exec'))"
    run=subprocess.run(K+['exec','-i','deployment/antigen-design','-c','service','--','python','-B','-c',bootstrap],
                       input=json.dumps({'environment':env,'source':source}).encode(),capture_output=True,timeout=200)
    if run.returncode:
        raise RuntimeError('Remote probe process failed. Raw output is withheld to avoid credential disclosure.')
    value=json.loads(run.stdout)
    if value.get('status') not in ('ready','failed'):
        raise RuntimeError('Unexpected probe output')
    out=ROOT/'.tmp/rustfs-verification'
    out.mkdir(parents=True,exist_ok=True)
    (out/'probe.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(value,indent=2))
    return 0 if value['status']=='ready' else 1


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print('STOP:',exc);raise SystemExit(1)
    except (OSError,ValueError,KeyError,subprocess.TimeoutExpired):
        print('STOP: Probe configuration/connection failed; credentials are not displayed.');raise SystemExit(1)
