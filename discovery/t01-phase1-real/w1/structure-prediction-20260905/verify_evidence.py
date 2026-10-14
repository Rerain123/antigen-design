"""Verify this preparatory snapshot; never interpret readiness as a successful fold."""
import hashlib
import importlib.util
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def require(value,message):
    if not value:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(root,entries):
    root = root.resolve()
    seen = set()
    for row in entries:
        path = (root/row['path']).resolve()
        require(path.is_relative_to(root) and path!=root and path not in seen,'Unsafe or duplicate manifest path')
        seen.add(path)
        require(path.stat().st_size==row['bytes'] and digest(path)==row['sha256'],'Evidence hash mismatch: '+row['path'])


def verify(manifest=None):
    manifest = read(BATCH/'manifest.json') if manifest is None else manifest
    verify_files(BATCH,manifest['files'])
    actual = {p.relative_to(BATCH).as_posix() for p in BATCH.rglob('*') if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts}
    require(actual=={r['path'] for r in manifest['files']},'Evidence inventory drift')
    environment = read(BATCH/'environment.json')
    for path,expected in environment['expert_sources_before'].items():
        require(digest(ROOT/path)==expected,'Expert source changed')
    verify_files(ROOT,manifest['user_sources'])
    receipts = [r for name in ['source_receipt.json','detail_receipt.json','history_receipt.json','final_source_receipt.json'] for r in read(BATCH/name)]
    failures = [r for r in receipts if 'error' in r]
    require(len(failures)==1 and failures[0]['path']=='af3/Dockerfile' and '404' in failures[0]['error'],'Unexpected source fetch failures')
    downloaded = [r for r in receipts if 'error' not in r]
    verify_files(BATCH/'official_sources',downloaded)
    fixed = {name:read(BATCH/'official_sources'/name/'commit.json')['sha'] for name in ['af3','esm']}
    for name in fixed:
        tree = read(BATCH/'official_sources'/name/'tree.json')
        require(not tree.get('truncated'),'Incomplete official file tree')
        entries = {r['path']:r for r in tree['tree'] if r['type']=='blob'}
        for record in downloaded:
            if record['url'].startswith('https://raw.githubusercontent.com/') and '/'+fixed[name]+'/' in record['url']:
                source_path = record['url'].split('/'+fixed[name]+'/',1)[1]
                data = (BATCH/'official_sources'/record['path']).read_bytes()
                require(source_path in entries,'Unobserved source-tree path')
                blob = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                require(blob==entries[source_path]['sha'],'Source does not match fixed commit blob')
    spec = importlib.util.spec_from_file_location('structure_readiness',BATCH/'assess_readiness.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    require(module.derive()==read(BATCH/'readiness.json'),'Readiness calculation drift')
    plan = read(BATCH/'validation/plan.json')
    require(plan['model_execution']=='NOT_RUN' and plan['production_status']=='NOT_DEPLOYED','Plan mistaken for execution')
    require(all(c['execution_status']=='DECLARED_NOT_RUN' for c in plan['cases']),'Fabricated executed case')
    for record in plan['input_provenance']:
        require(digest(ROOT/record['path'])==record['sha256'],'Input source changed')
    sequence = ''.join((BATCH/'validation/ubiquitin76.fasta').read_text().splitlines()[1:])
    require(len(sequence)==76 and hashlib.sha256(sequence.encode()).hexdigest()==plan['sequence_sha256'],'Prepared sequence mismatch')
    af3 = read(BATCH/'validation/af3_full_pipeline_input.json')
    protein = af3['sequences'][0]['protein']
    require(protein==dict(id='A',sequence=sequence),'Prepared AF3 input changed or MSA silently emptied')
    require(af3['modelSeeds']==[1] and plan['af3_profile']['num_diffusion_samples']==5,'AF3 sample profile mismatch')
    expected = read(BATCH/'readiness.json')['esmfold2']['fold_wrapper_defaults']
    require(all(plan['esm_profile'][k]==expected[k] for k in ['num_loops','num_sampling_steps','num_diffusion_samples','lm_dropout','msa_max_depth','msa_column_mask_rate']),'ESMFold2 defaults drift')
    return dict(status='PASS',batch_files=len(manifest['files']),official_downloads=len(downloaded),
                expert_sources_unchanged=len(environment['expert_sources_before']),prepared_cases=len(plan['cases']),
                gpu_visibility='PASS_ONLY',model_execution='NOT_RUN',production_status='NOT_DEPLOYED')


if __name__=='__main__':
    print(json.dumps(verify()))
