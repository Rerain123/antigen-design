"""Download bounded official source/metadata snapshots, never weights or prediction data."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

BATCH = Path(__file__).resolve().parent
OUT = BATCH/'official_sources'


def fetch(url, name):
    path = OUT/name
    if path.exists():
        raise FileExistsError(path)
    request = urllib.request.Request(url, headers={'User-Agent':'T01-W1-source-verification','Accept':'application/json, text/plain, */*'})
    record = dict(url=url, path=name, recorded_at=datetime.now(timezone.utc).isoformat())
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            data = response.read(4*1024*1024+1)
            if len(data)>4*1024*1024:
                raise ValueError('Public metadata exceeds 4 MiB cap')
            record.update(status=response.status, final_url=response.url, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
    return record


if __name__ == '__main__':
    OUT.mkdir(exist_ok=False)
    requests = [('https://api.github.com/repos/'+repo+'/commits/main',name+'/commit.json')
                for name,repo in [('af3','google-deepmind/alphafold3'),('esm','Biohub/esm')]]
    requests += [('https://huggingface.co/api/models/biohub/'+name+'?blobs=true','hf/'+name+'/metadata.json')
                 for name in ['ESMFold2','ESMFold2-Fast','ESMC-6B']]
    requests += [('https://pypi.org/pypi/esm/json','esm/pypi.json')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: fetch(*item), requests))
    next_requests = []
    for name,repo,files in [
        ('af3','google-deepmind/alphafold3',['README.md','LICENSE','WEIGHTS_TERMS_OF_USE.md','docs/installation.md','docs/performance.md','docs/known_issues.md','docs/input.md','docs/output.md','Dockerfile','pyproject.toml','run_alphafold.py','fetch_databases.sh']),
        ('esm','Biohub/esm',['README.md','LICENSE.md','THIRD_PARTY_NOTICE.md','pyproject.toml'])]:
        commit = json.loads((OUT/name/'commit.json').read_text())['sha']
        next_requests += [('https://api.github.com/repos/'+repo+'/git/trees/'+commit+'?recursive=1',name+'/tree.json')]
        for filename in files:
            local = filename+'.txt' if filename.endswith('.md') else filename
            next_requests.append(('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+filename,name+'/'+local))
    for name in ['ESMFold2','ESMFold2-Fast','ESMC-6B']:
        metadata = json.loads((OUT/'hf'/name/'metadata.json').read_text())
        for filename in ['README.md','config.json']:
            next_requests.append(('https://huggingface.co/biohub/'+name+'/resolve/'+metadata['sha']+'/'+filename,
                                  'hf/'+name+'/'+(filename+'.txt' if filename.endswith('.md') else filename)))
    with ThreadPoolExecutor(max_workers=4) as pool:
        records += list(pool.map(lambda item: fetch(*item), next_requests))
    (BATCH/'source_receipt.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'downloads':len(records),'errors':[record for record in records if 'error' in record],'model_execution':'NOT_RUN'}))
