"""Interactively create only him-ws/antigen-design-rustfs; never print credentials.

Credentials are entered with getpass, sent to kubectl on stdin and verified in
memory. No credentials, Secret manifest, or last-applied annotation are written
to local files. This does not update Deployment or configure RustFS permissions.
"""
from __future__ import annotations

import argparse
import base64
import getpass
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'antigen-design-rustfs'
KEYS = ('RUSTFS_ACCESS_KEY_ID', 'RUSTFS_SECRET_ACCESS_KEY')
K = ['C:/Program Files/Docker/Docker/resources/bin/kubectl.exe', '--kubeconfig',
     str(ROOT/'.tmp/himat.kubeconfig'), '--request-timeout=30s', '-n', 'him-ws']


def call(*args, data=None):
    result = subprocess.run(K+list(args), input=data, capture_output=True, timeout=45)
    if result.returncode:
        # API error responses may echo submitted fields, so never print them.
        raise RuntimeError('Kubernetes request failed. No credentials are displayed; check connectivity and permissions.')
    return result.stdout


def preflight():
    if not Path(K[0]).is_file() or not (ROOT/'.tmp/himat.kubeconfig').is_file():
        raise RuntimeError('kubectl or project kubeconfig is missing.')
    if call('auth','can-i','create','secrets').strip() != b'yes':
        raise RuntimeError('This account cannot create Secrets in him-ws.')
    existing = call('get','secret',NAME,'--ignore-not-found','-o','name').strip()
    if existing:
        raise RuntimeError('antigen-design-rustfs already exists; it was not overwritten. Ask to verify the existing Secret.')


def document(access_key, secret_key):
    values = [access_key, secret_key]
    if any(not v or v != v.strip() or any(ord(c)<32 for c in v) for v in values):
        raise ValueError('Empty values, surrounding whitespace and control characters are not accepted.')
    return {'apiVersion':'v1', 'kind':'Secret', 'type':'Opaque',
            'metadata':{'name':NAME,'namespace':'him-ws'},
            'data':{k:base64.b64encode(v.encode('utf-8')).decode('ascii') for k,v in zip(KEYS,values)}}


def create():
    preflight()
    if not sys.stdin.isatty():
        raise RuntimeError('Run create in an interactive PowerShell window; piped credential input is not accepted.')
    print('Enter the dedicated RustFS application credentials. Input is hidden.', flush=True)
    access_key = getpass.getpass('Access Key: ')
    secret_key = getpass.getpass('Secret Key: ')
    payload = document(access_key, secret_key)
    call('create','-f','-','-o','name',data=json.dumps(payload).encode('utf-8'))
    # Read back only in memory; do not output the Secret document.
    observed = json.loads(call('get','secret',NAME,'-o','json'))
    if observed.get('data') != payload['data']:
        raise RuntimeError('Secret was created, but read-back differs. Do not retry creation; request a check.')
    print('SECRET_CREATED_AND_VERIFIED him-ws/'+NAME)
    print('Deployment unchanged. RustFS write/download verification is the next step.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['check','create'])
    action=parser.parse_args().action
    if action=='check':
        preflight()
        print('PREFLIGHT_PASS; no Secret was created.')
    else:
        create()


if __name__=='__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired, EOFError, KeyboardInterrupt) as exc:
        if isinstance(exc, (subprocess.TimeoutExpired, OSError)):
            print('STOP: Connection/process error. If creation was attempted, check whether the Secret exists before retrying.')
        elif isinstance(exc, (EOFError, KeyboardInterrupt)):
            print('STOP: Input cancelled.')
        else:
            print('STOP:',exc)
        raise SystemExit(1)
