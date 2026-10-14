"""Python 2.7-compatible target entry for the pinned A3D image."""
from __future__ import print_function
import hashlib
import json
import os
import subprocess
import sys


def main():
    os.chdir('/out')
    command=['/opt/conda/bin/aggrescan','-i','/input.pdb','-w','/out/run','-v','4']
    with open('/out/stdout.txt','wb') as stdout, open('/out/stderr.txt','wb') as stderr:
        code=subprocess.call(command,stdout=stdout,stderr=stderr)
    with open('/input.pdb','rb') as stream:input_hash=hashlib.sha256(stream.read()).hexdigest()
    with open('/out/execution.json','w') as stream:
        json.dump(dict(exit_code=code,input_sha256=input_hash,command=command,python=sys.version.split()[0]),stream)
    return code


if __name__=='__main__':sys.exit(main())
