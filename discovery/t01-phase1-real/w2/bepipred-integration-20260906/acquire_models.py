"""Download public official ESM-2 assets once; no prediction network access."""
import hashlib
import json
from pathlib import Path
import time
import urllib.request

BASE=Path(__file__).parent
DEST=BASE.parents[3]/'var'  # Actual asset directory set from repository below.
REPO=BASE.parents[3]
DEST=REPO/'var/t01-phase1-real/tool-assets/bepipred-esm2-650m'
DEST.mkdir(parents=True,exist_ok=True)
items=[('esm2_t33_650M_UR50D.pt','https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t33_650M_UR50D.pt'),
       ('esm2_t33_650M_UR50D-contact-regression.pt','https://dl.fbaipublicfiles.com/fair-esm/regression/esm2_t33_650M_UR50D-contact-regression.pt'),
       ('ESM-LICENSE.txt','https://raw.githubusercontent.com/facebookresearch/esm/main/LICENSE')]
receipt=[]
for name,url in items:
    path=DEST/name
    assert not path.exists(),str(path)
    digest=hashlib.sha256();n=0;started=time.monotonic()
    with urllib.request.urlopen(url,timeout=120) as response,path.with_suffix(path.suffix+'.partial').open('xb') as stream:
        headers=dict(response.headers)
        while chunk:=response.read(8*1024**2):
            stream.write(chunk);digest.update(chunk);n+=len(chunk)
            if n%(256*1024**2)==0:print(name,n,flush=True)
    if headers.get('Content-Length'):assert n==int(headers['Content-Length'])
    path.with_suffix(path.suffix+'.partial').rename(path)
    receipt.append(dict(name=name,url=url,path=path.relative_to(REPO).as_posix(),bytes=n,sha256=digest.hexdigest(),elapsed_seconds=time.monotonic()-started,headers=headers))
    (BASE/'model-downloads.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(name,n,digest.hexdigest(),flush=True)
