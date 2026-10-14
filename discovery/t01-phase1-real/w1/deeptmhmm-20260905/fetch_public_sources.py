"""Download public SDK sources and official documentation/test inputs; never submit a prediction."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

BATCH=Path(__file__).resolve().parent
OUTPUT=BATCH/'public_sources'
OUTPUT.mkdir(exist_ok=True)
records=[]


def get(url,filename,sha=None):
    target=OUTPUT/filename
    if target.exists(): raise SystemExit('Refusing to overwrite '+str(target))
    with urllib.request.urlopen(url,timeout=45) as response:
        data=response.read(); final=response.url
    digest=hashlib.sha256(data).hexdigest()
    if sha is not None and digest!=sha: raise ValueError('Download hash mismatch')
    target.write_bytes(data)
    records.append({'url':url,'final_url':final,'filename':filename,'sha256':digest,'bytes':len(data)})
    return data


metadata=json.loads(get('https://pypi.org/pypi/pybiolib/json','pybiolib-pypi.json'))
wheel=next(f for f in metadata['urls'] if f['filename'].endswith('.whl'))
get(wheel['url'],wheel['filename'],wheel['digests']['sha256'])
get('https://dtu.biolib.com/DeepTMHMM/','deeptmhmm-app.html')
get('https://services.healthtech.dtu.dk/services/DeepTMHMM-1.0/fasta_example.html','dtu-fasta-example.html')
(OUTPUT/'retrieval.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'scope':'PUBLIC_SOFTWARE_AND_DOCUMENTATION_ONLY','downloads':records},indent=2)+'\n')
print(json.dumps({'sdk_version':metadata['info']['version'],'sdk_license':metadata['info'].get('license_expression',metadata['info'].get('license')),'project_urls':metadata['info']['project_urls'],'downloads':records},indent=2))
