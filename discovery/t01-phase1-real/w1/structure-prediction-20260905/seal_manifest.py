"""Seal evidence once; subsequent checks are read-only."""
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def record(path,root):
    data = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def inventory():
    return dict(files=[record(p,BATCH) for p in sorted(BATCH.rglob('*')) if p.is_file() and p.name!='manifest.json' and '__pycache__' not in p.parts],
                user_sources=[record(ROOT/p,ROOT) for p in [
                    'docs/project/sources/PHASE1_W1_STRUCTURE_ASSET_AVAILABILITY_20260905.json',
                    'docs/project/sources/PHASE1_NODE01_OFFLINE_SOURCE_20260903.json']],
                model_execution='NOT_RUN',production_status='NOT_DEPLOYED')


if __name__=='__main__':
    target = BATCH/'manifest.json'
    if target.exists():
        raise FileExistsError('Do not overwrite sealed evidence')
    result = inventory()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'sealed_files':len(result['files'])}))
