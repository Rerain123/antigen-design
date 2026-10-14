"""One-time evidence inventory. Subsequent results belong in a new batch."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

BATCH = Path(__file__).resolve().parent
ROOT = BATCH.parents[3]
target = BATCH/'manifest.json'
if target.exists():
    raise SystemExit('Manifest already exists; verify it read-only, use a new batch for changes')
snapshot = BATCH/'code_snapshot'
snapshot.mkdir()
(snapshot/'test_w1_deeptmhmm_evidence.py').write_bytes((ROOT/'tests/test_w1_deeptmhmm_evidence.py').read_bytes())
entries = []
for path in sorted(BATCH.rglob('*')):
    if path.is_file() and '__pycache__' not in path.parts and path != target:
        data = path.read_bytes()
        entries.append({'path':path.relative_to(BATCH).as_posix(), 'bytes':len(data),
                        'sha256':hashlib.sha256(data).hexdigest()})
user = ROOT/'docs/project/sources/PHASE1_W1_DEEPTMHMM_USAGE_20260905.json'
manifest = {'schema':'W1_DEEPTMHMM_PREPARATION_EVIDENCE_1',
            'recorded_at':datetime.now(timezone.utc).isoformat(), 'files':entries,
            'user_source':{'path':user.relative_to(ROOT).as_posix(), 'sha256':hashlib.sha256(user.read_bytes()).hexdigest()},
            'scope':'LOCAL_PREPARATION_NOT_G0_MODEL_COMPLETION',
            'model_execution':'NOT_RUN', 'production_status':'NOT_DEPLOYED'}
target.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'evidence_files':len(entries),'model_execution':'NOT_RUN'}))
