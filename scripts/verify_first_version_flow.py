"""Verify the deployed continuation overlay without starting a scientific job."""
import json
import subprocess
from datetime import datetime, timezone
import prepare_first_version_flow as deploy
import prepare_m1_p1_deploy as common
from t01_phase1_real.common import sha


def main():
    expected={n:sha((common.ROOT/'src/t01_phase1_real'/n).read_bytes()) for n in deploy.FILES}
    observed=common.remote('''import json,sys
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha
from t01_phase1_real.development.workflow.service import recoverable_child_failure
p=json.load(sys.stdin)
hashes={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p}
assert hashes==p
b=dict(engineering_design='BACKEND_EVIDENCE_V1')
assert recoverable_child_failure(b,'rep1_prediction',dict(state='failed',error_code='TOOL_FAILED'))
assert not recoverable_child_failure(b,'rep1_prediction',dict(state='failed',error_code='HASH_MISMATCH'))
assert not recoverable_child_failure(b,'prediction',dict(state='failed',error_code='TOOL_FAILED'))
print(json.dumps(hashes))
''',expected)
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['metadata']['generation']==live['status']['observedGeneration']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    value=dict(status='CONTINUATION_OVERLAY_READY',observed_at=datetime.now(timezone.utc).isoformat(),
        generation=live['metadata']['generation'],source_hashes=observed,idle=common.idle(),
        runtime_checks='operational variant failure continues; integrity and original prediction failures stop',
        checks_are_engineering_fixtures=True,full_workflow_verified=False,
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    with (deploy.EVIDENCE/'deployment-r01.json').open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
    print(json.dumps(value))


if __name__=='__main__':main()
