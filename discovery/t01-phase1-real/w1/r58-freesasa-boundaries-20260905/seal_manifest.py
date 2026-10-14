"""Archive the exact executed code and record a new evidence inventory without rewriting old batches."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

BATCH=Path(__file__).resolve().parent
ROOT=BATCH.parents[3]
target=BATCH/'manifest.json'
if target.exists():raise SystemExit('Manifest already exists; verify read-only and use a new batch for later changes')
execution=json.loads((BATCH/'raw-run/execution.json').read_text())
sources={path.replace('\\','/') for path in execution['source_hashes']}
sources.update(['src/t01_structure_mapping/__init__.py','tests/test_r58_sasa_boundaries.py',
                '工作流设计/02-数据契约/tool-interface-v0.1/structure_mapping/mapping.schema.json'])
for relative in sorted(sources):
    path=BATCH/'after'/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((ROOT/relative).read_bytes())
rows=[]
for path in sorted(BATCH.rglob('*')):
    if path.is_file() and '__pycache__' not in path.parts and path!=target:
        data=path.read_bytes();rows.append({'path':path.relative_to(BATCH).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
target.write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'scope':'R58_SASA_DEVELOPMENT_BOUNDARIES',
                  'files':rows,'production_status':'NOT_DEPLOYED'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'batch_files':len(rows)}))
