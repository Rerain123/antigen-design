"""Inventory installed OS and Python packages without network/scanner services."""
import importlib.metadata
import json
import subprocess

raw=subprocess.check_output(['dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\n'],text=True)
packages=[dict(name=n,version=v,architecture=a,ecosystem='deb') for n,v,a in (line.split('\t') for line in raw.splitlines())]
packages.extend(dict(name=d.metadata['Name'],version=d.version,ecosystem='pypi') for d in importlib.metadata.distributions())
print(json.dumps({'method':'dpkg-query and Python importlib.metadata; offline installed-package inventory only',
    'network':'none','vulnerability_scan_performed':False,'packages':sorted(packages,key=lambda p:(p['ecosystem'],p['name']))},sort_keys=True))
