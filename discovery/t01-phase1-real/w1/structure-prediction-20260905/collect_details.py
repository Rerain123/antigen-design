"""Follow source-tree-discovered paths; do not execute downloaded code."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from collect_sources import BATCH, OUT, fetch

if __name__ == '__main__':
    receipt = BATCH/'detail_receipt.json'
    if receipt.exists():
        raise FileExistsError(receipt)
    requests = []
    for name,repo,paths in [
        ('af3','google-deepmind/alphafold3',['docker/Dockerfile','WEIGHTS_PROHIBITED_USE_POLICY.md','OUTPUT_TERMS_OF_USE.md','src/alphafold3/common/folding_input.py']),
        ('esm','Biohub/esm',['esm/models/hub.py','esm/models/esmfold2/model.py','esm/models/esmfold2/output.py','esm/models/esmfold2/processor.py','esm/models/esmfold2/prepare_input.py','esm/models/esmfold2/hf_adapter.py','esm/models/esmfold2/config.py','esm/models/esmc/model.py','esm/utils/structure/input_builder.py','esm/utils/structure/protein_complex.py','cookbook/tutorials/esmfold2_local_gpu.ipynb','cookbook/tutorials/esmfold2.ipynb'])]:
        commit = json.loads((OUT/name/'commit.json').read_text())['sha']
        known = {row['path'] for row in json.loads((OUT/name/'tree.json').read_text())['tree']}
        for path in paths:
            if path not in known:
                raise ValueError('Path not present in observed source tree: '+path)
            local = path+'.txt' if path.endswith('.md') else path
            requests.append(('https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+path,name+'/'+local))
    requests += [('https://huggingface.co/api/models/biohub/'+name+'/commits/main','hf/'+name+'/commits.json') for name in ['ESMFold2','ESMFold2-Fast']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(lambda item: fetch(*item), requests))
    receipt.write_text(json.dumps(records,indent=2),encoding='utf-8')
    print(json.dumps({'downloads':len(records),'errors':[r for r in records if 'error' in r]}))
