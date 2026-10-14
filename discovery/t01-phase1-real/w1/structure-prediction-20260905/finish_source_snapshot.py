"""Fetch observed helper and lock files required to review offline output semantics."""
import json
from collect_sources import BATCH, OUT, fetch

if __name__ == '__main__':
    receipt = BATCH/'final_source_receipt.json'
    if receipt.exists():
        raise FileExistsError(receipt)
    results = []
    for name,repo,paths in [
        ('esm','Biohub/esm',['esm/utils/structure/molecular_complex.py','esm/models/esmfold2/__init__.py']),
        ('af3','google-deepmind/alphafold3',['uv.lock'])]:
        commit = json.loads((OUT/name/'commit.json').read_text())['sha']
        paths_in_tree = {r['path'] for r in json.loads((OUT/name/'tree.json').read_text())['tree']}
        for path in paths:
            if path not in paths_in_tree:
                raise ValueError('Unobserved path')
            results.append(fetch('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+path,name+'/'+path))
    receipt.write_text(json.dumps(results,indent=2))
    print(json.dumps({'downloads':len(results),'errors':[r for r in results if 'error' in r]}))
