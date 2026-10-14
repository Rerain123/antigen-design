"""Verify the deployed ESMFold2 policy through the native Python import path."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

import prepare_himat_esmfold2_path_fix as deployment
import prepare_m1_p1_deploy as common


OUT = (common.ROOT / "discovery/t01-phase1-real/m1-p4-20260922/"
       "himat-esmfold2-path-deployment-r06.json")

PROBE = """import hashlib,json
from pathlib import Path
from t01_phase1_real.development.esmfold2 import policy
root=Path(policy.__file__).parent
body={'protein_sequence':'A'*233,'user_sequence_id':'path-probe',
      'host_species':'Sus scrofa','seed':1,'timeout_seconds':7200}
policy.request(json.dumps(body).encode())
print(json.dumps({'import_path':str(Path(policy.__file__)),
                  'resolved_import_path':str(Path(policy.__file__).resolve()),
                  'registered_profile':policy.registered_profile(),
                  'profile_max_aa':policy.profile()['max_sequence_length'],
                  'admitted_synthetic_233_aa':True,
                  'hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in root.iterdir() if p.suffix in ('.py','.json')}}))
"""


def verify_import_path(worker):
    from pathlib import PurePosixPath
    if worker['import_path'] != '/backend/t01_phase1_real/development/esmfold2/policy.py' or not PurePosixPath(worker['resolved_import_path']).is_relative_to('/backend'):
        raise RuntimeError('Native Python did not import from /backend')


def main() -> None:
    before = common.idle()
    if before["active_jobs"] or before["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Verify only when backend is idle")
    live = json.loads(subprocess.check_output(common.K + [
        "get", "deployment", "antigen-design", "-o", "json"]))
    volumes = live["spec"]["template"]["spec"]["volumes"]
    code = next(v for v in volumes if v["name"] == deployment.VOLUME)
    if code["configMap"]["name"] != deployment.NEW_NAME or \
       live["status"].get("readyReplicas") != 1 or \
       live["status"].get("observedGeneration") != live["metadata"]["generation"]:
        raise RuntimeError("New ESMFold2 source volume is not ready")
    service = common.remote(PROBE)
    worker_launcher = """import json,os,subprocess
config=json.load(open('/etc/t01/esmfold2.worker.json'))['commands'][0]
env=dict(config['environment'])
env['HOME']='/tmp'
p=subprocess.run(['/opt/t01/env/esmfold2/bin/python','-B','-c',os.environ['T01_PROBE']],
                 env=env,capture_output=True,text=True,timeout=30)
if p.returncode:raise RuntimeError(p.stderr[-1500:])
print(p.stdout.strip())
"""
    # The supervisor passes the probe only to this transient, read-only native
    # interpreter; the resident worker and active job store are untouched.
    launcher = worker_launcher.replace("os.environ['T01_PROBE']", repr(PROBE))
    worker = json.loads(subprocess.check_output(common.K + [
        "exec", "deployment/antigen-design", "-c", "worker-unified-gpu", "--",
        "/opt/t01/supervisor/bin/python3.11", "-B", "-c", launcher]))
    after = common.idle()
    if after["active_jobs"] or after["gpu_state"]["phase"] != "idle":
        raise RuntimeError("Read-only probe changed backend work state")
    verify_import_path(worker)
    if service["hashes"] != worker["hashes"] or \
       service["registered_profile"] != worker["registered_profile"]:
        raise RuntimeError("Service and native execution profiles differ")
    if service["profile_max_aa"] != 999 or worker["profile_max_aa"] != 999:
        raise RuntimeError("Actual ESMFold2 profile still has old length limit")
    expected = deployment.source_hashes()
    for name in deployment.FILES:
        if service["hashes"][name] != expected[name]:
            raise RuntimeError("Deployed ESMFold2 source hash differs")
    OUT.write_text(json.dumps({
        "status": "HIMAT_ESMFOLD2_ACTUAL_PATH_DEPLOYED_PASS",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": "him-ws/antigen-design", "generation": live["metadata"]["generation"],
        "configmap": deployment.NEW_NAME, "service": service, "native_worker": worker,
        "synthetic_233_aa_only": True, "submitted_new_job": False,
        "scientific_gate": "CLOSED", "usable_for_pipeline": False,
        "production_status": "NOT_DEPLOYED",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("HIMAT_ESMFOLD2_ACTUAL_PATH_DEPLOYED_PASS", OUT)


if __name__ == "__main__":
    main()
