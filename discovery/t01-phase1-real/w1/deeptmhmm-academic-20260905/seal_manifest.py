"""One-time local evidence inventory. Never overwrite a sealed manifest."""
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]


def record(path, root):
    data = path.read_bytes()
    return dict(path=path.relative_to(root).as_posix(), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    target = BATCH/'manifest.json'
    if target.exists():
        raise FileExistsError('Do not replace sealed evidence')
    source = ROOT/'docs/project/sources/PHASE1_W1_DEEPTMHMM_USAGE_20260905.json'
    files = [record(p, BATCH) for p in sorted(BATCH.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    target.write_text(json.dumps(dict(files=files, usage_source=record(source, ROOT), model_execution='EXECUTED_OFFLINE_CPU',
                                     production_status='NOT_DEPLOYED'), ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'sealed_files': len(files)}))
