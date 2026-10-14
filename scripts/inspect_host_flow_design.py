"""Read the completed host-panel run's design constraints and no-generation facts."""
import json
import prepare_m1_p1_deploy as common
from host_panel_flow_probe import OUT
REMOTE=r'''
import json,sys
from collections import Counter
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
rt=Runtime('/var/lib/t01/runtime',scope=Principal('himat-t01-test',frozenset(['query']),'none').runtime_scope)
jid=json.load(sys.stdin)['job_id'];rows=rt.execution(jid)['nodes']
audit=rt.result(rows['design_inputs']['job_id'])['audit'];perms=audit['permissions']
gen=rt.result(rows['design']['job_id'])['generation']
print(json.dumps(dict(job_id=jid,permission_summary={k:v for k,v in perms.items() if k!='per_residue'},
 example_residues=perms['per_residue'][:2],review_reasons=audit['review_reasons'],
 generation={k:v for k,v in gen.items() if k not in ('conversion','engine_runtime','native_wt','records')},
 runtime={k:v for k,v in gen.get('engine_runtime',{}).items() if k in ('tool_invoked','designable_positions')},
 domains=rt.result(rows['domains']['job_id'])['analysis']['functional_domains'])))
'''
if __name__=='__main__':
    job=json.loads((OUT/'host-panel-flow-submit.json').read_bytes())
    value=common.remote(REMOTE,dict(job_id=job['job_id']))
    (OUT/'host-flow-design-inspection.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(value,ensure_ascii=False))
