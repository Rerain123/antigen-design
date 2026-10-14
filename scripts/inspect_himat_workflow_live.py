"""Capture a redacted, read-only status of a HiMat workflow and its native work."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone

import prepare_m1_p1_deploy as common


OUT = (common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/"
       "himat-first-job-inspection-r01.json")

REMOTE = """import json,sqlite3,sys
from pathlib import Path
task=json.load(sys.stdin)
db=sqlite3.connect('file:/var/lib/t01/runtime/state.sqlite3?mode=ro',uri=True)
jobs=[json.loads(raw) for (raw,) in db.execute('SELECT data FROM jobs')]
run=[j for j in jobs if j.get('run_id')==task['run_id']]
if not any(j['job_id']==task['job_id'] and j['tool_id']=='t01.real.local_workflow' for j in run):
    raise RuntimeError('Parent job and run do not match')
rows=[{k:j.get(k) for k in ('job_id','tool_id','node_id','state','error_code',
                            'started_at','finished_at')} for j in run]
native=[]
for j in run:
    if j['tool_id']!='t01.real.blast':continue
    row=db.execute('SELECT data FROM executions WHERE job_id=?',(j['job_id'],)).fetchone()
    execution=json.loads(row[0]) if row else {}
    target=Path(execution['resident_target']) if execution.get('resident_target') else None
    receipt=target/'execution.json' if target else None
    state=json.loads(receipt.read_bytes()) if receipt and receipt.is_file() else {}
    native_dir=target/'output/native' if target else None
    native.append({'job_id':j['job_id'],'phase':execution.get('phase'),
                   'resident_state':state.get('state'),
                   'native_started':bool(native_dir and (native_dir/'runtime_started.json').is_file()),
                   'native_finished':bool(native_dir and (native_dir/'runtime.json').is_file()),
                   'cancelled':bool(target and (target/'cancel').is_file())})
failure=[]
for j in run:
    if j['tool_id']!='t01.real.esmfold2' or j['state']!='failed':continue
    marker=False
    for ref in j.get('artifacts',[]):
        row=db.execute('SELECT relative_path FROM artifacts WHERE id=?',
                       (ref['artifact_id'],)).fetchone()
        if row and ref.get('role')=='raw':
            path=(Path('/var/lib/t01/runtime')/row[0]).resolve()
            if path.is_relative_to(Path('/var/lib/t01/runtime')) and path.stat().st_size < 100000:
                marker=marker or 'bounded to 9..76' in path.read_text(errors='replace')
    failure.append({'job_id':j['job_id'],'legacy_76_aa_rejection_in_stderr':marker})
print(json.dumps({'jobs':rows,'blast_native':native,'prediction_failure':failure}))
"""

GPU = """import hashlib,json,re
from pathlib import Path
roots={'actual_import':Path('/backend/t01_phase1_real/development/esmfold2'),
       'previously_verified':Path('/opt/t01/src/t01_phase1_real/development/esmfold2')}
sources={key:{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in ('policy.py','profile.json')} for key,root in roots.items()}
limits={key:{'policy_max_aa':int(re.search(r'MAX_AA = (\\d+)',
                     (root/'policy.py').read_text()).group(1)),
             'profile_max_aa':json.loads((root/'profile.json').read_bytes())['max_sequence_length']}
        for key,root in roots.items()}
config=json.loads(Path('/etc/t01/esmfold2.worker.json').read_bytes())
print(json.dumps({'sources':sources,'limits':limits,
                  'pythonpath':config['commands'][0]['environment']['PYTHONPATH']}))
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    service = common.remote(REMOTE, {"job_id": args.job_id, "run_id": args.run_id})
    gpu = json.loads(subprocess.check_output(common.K + ["exec", "deployment/antigen-design",
        "-c", "worker-unified-gpu", "--", "/opt/t01/supervisor/bin/python3.11",
        "-B", "-c", GPU]))
    processes = subprocess.check_output(common.K + ["exec", "deployment/antigen-design",
        "-c", "worker-blast", "--", "ps", "-eo", "pid,etime,pcpu,comm"], text=True)
    blast = []
    for line in processes.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 4 and parts[3] == "blastp.REAL":
            blast.append({"pid": int(parts[0]), "elapsed": parts[1], "cpu_percent": float(parts[2])})
    parent = next(row for row in service["jobs"] if row["job_id"] == args.job_id)
    OUT.write_text(json.dumps({
        "status": "HIMAT_REAL_SUBMISSION_" + parent["state"].upper(),
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "job_id": args.job_id, "run_id": args.run_id,
        "service": service, "gpu": gpu, "blast_processes": blast,
        "read_only": True, "submitted_new_job": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
