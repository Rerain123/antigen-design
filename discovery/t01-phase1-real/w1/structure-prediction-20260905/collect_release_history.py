"""Compare May release metadata to current public snapshots without model downloads."""
from concurrent.futures import ThreadPoolExecutor
import json
import urllib.request
from collect_sources import BATCH, OUT, fetch

if __name__ == '__main__':
    target = BATCH/'history_receipt.json'
    if target.exists():
        raise FileExistsError(target)
    requests = []
    for name in ['ESMFold2','ESMFold2-Fast']:
        history = json.loads((OUT/'hf'/name/'commits.json').read_text())
        may = next(item for item in history if item['date'].startswith('2026-05'))['id']
        requests += [('https://huggingface.co/api/models/biohub/'+name+'/revision/'+may+'?blobs=true','hf/'+name+'/may-metadata.json'),
                     ('https://huggingface.co/biohub/'+name+'/resolve/'+may+'/config.json','hf/'+name+'/may-config.json')]
    requests.append(('https://api.github.com/repos/Biohub/esm/commits?until=2026-05-31T23:59:59Z&per_page=1','esm/may-commits.json'))
    esm_commit = json.loads((OUT/'esm/commit.json').read_text())['sha']
    for path in ['esm/models/esmfold2/conformers.py','esm/utils/structure/biomolecular_complex.py']:
        known = {r['path'] for r in json.loads((OUT/'esm/tree.json').read_text())['tree']}
        if path in known:
            requests.append(('https://raw.githubusercontent.com/Biohub/esm/'+esm_commit+'/'+path,'esm/'+path))
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: fetch(*item), requests))
    may_commit = json.loads((OUT/'esm/may-commits.json').read_text())[0]['sha']
    with ThreadPoolExecutor(max_workers=3) as pool:
        records += list(pool.map(lambda path: fetch('https://raw.githubusercontent.com/Biohub/esm/'+may_commit+'/'+path,'esm/may/'+path+'.txt'),['README.md','pyproject.toml']))
    # Public object header only, no model body or user credentials.
    url = 'https://storage.googleapis.com/alphafold3/af3.bin.zst'
    header = {'url':url,'method':'HEAD','weight_body_downloaded':False}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'),timeout=30) as response:
            header.update(status=response.status,headers={k:v for k,v in response.headers.items() if k.lower() in ['content-length','content-type','x-goog-hash','last-modified','etag']})
    except Exception as exc:
        header['error'] = str(exc)
    (BATCH/'af3_weight_header.json').write_text(json.dumps(header,indent=2))
    target.write_text(json.dumps(records,indent=2))
    print(json.dumps({'sources':len(records),'errors':[r for r in records if 'error' in r],'af3_header':header}))
