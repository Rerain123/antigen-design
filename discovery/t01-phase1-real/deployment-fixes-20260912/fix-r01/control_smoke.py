"""Isolated image acceptance. Credentials exist only in container tmpfs."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

spec=importlib.util.spec_from_file_location('client','/acceptance_client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
client.TOKEN_A=secrets.token_hex(32);client.TOKEN_B=secrets.token_hex(32)
base='http://127.0.0.1:18083'

with tempfile.TemporaryDirectory(prefix='t01-credentials-') as directory:
    secret=Path(directory)/'credentials.json'
    secret.write_text(json.dumps({'credentials':[{'token':token,'principal':name,'scopes':['submit','query','control','download','upload']}
        for token,name in [(client.TOKEN_A,'operator'),(client.TOKEN_B,'other')]]}))
    secret.chmod(0o600)
    env=dict(os.environ,T01_REAL_SERVICE_CREDENTIALS_FILE=str(secret))
    process=None
    def start(delay):
        proc=subprocess.Popen([sys.executable,'-B','-m','t01_phase1_real.linux_service','--host','127.0.0.1','--port','18083',
            '--runtime-root','/var/lib/t01/runtime','--dispatch-start-delay-seconds',str(delay)],env=env,
            stdout=subprocess.DEVNULL,stderr=None)
        for _ in range(100):
            if proc.poll() is not None:raise RuntimeError('Service exited during startup')
            try:
                if client.value(base,'/healthz')[0]==200:return proc
            except OSError:pass
            time.sleep(.1)
        proc.terminate();proc.wait(timeout=20);raise RuntimeError('Service startup timed out')
    try:
        process=start(2);client.prepare(base)
        process.terminate();process.wait(timeout=20)
        process=start(0);client.verify(base);client.snapshot(base)
        print(json.dumps({'status':'PASS','boundary':'LOCAL_LINUX_CONTAINER_ONLY','cluster_contacted':False,'production_status':'NOT_DEPLOYED'}))
    finally:
        if process and process.poll() is None:process.terminate();process.wait(timeout=20)
