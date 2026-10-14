"""Fresh, bounded v2 native test through the deployed authenticated MCP service.

prepare is local only. start requires a verified deployment and idle workers.
This script never resumes PCV2 or submits T4/R57 consent.
"""
import argparse
import json
from pathlib import Path
import prepare_m1_p1_deploy as common
from run_pcv2_full_20260928 import SEQUENCE
from version_bundle import build, encode, sha

OUT = common.ROOT / 'reports/expert-revision-v2-native-20260930/r01'
DEPLOY = common.ROOT / 'reports/expert-revision-v2-deploy-20260930'
TESTED = common.ROOT / 'reports/expert-revision-v2-20260930'
KEY = 'expert-v2-native-20260930-r01'


def active_submission():
    continuation=common.ROOT/'reports/expert-revision-v2-bepi-fix-20260930/continuation-submission.json'
    original=json.loads((OUT/'submission.json').read_bytes())
    if continuation.exists():
        current=json.loads(continuation.read_bytes())
        assert current['run_id']==original['run_id'] and current['source_job_id']==original['job_id']
        resumed=common.ROOT/'reports/expert-revision-v2-resume-20260930/continuation-submission.json'
        if resumed.exists():
            latest=json.loads(resumed.read_bytes())
            assert latest['run_id']==current['run_id'] and latest['source_job_id']==current['job_id']
            return latest
        return current
    return original


REMOTE = r'''
import json,sys,urllib.request
from pathlib import Path
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.development import Runtime
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.common import decode,sha
p=json.load(sys.stdin)
needed={'query','submit','upload','download','control'}
rows=[r for r in json.loads(Path('/run/secrets/t01/credentials.json').read_bytes())['credentials']
      if r['principal']!='himat-t01-test' and needed.issubset(r['scopes'])]
if p.get('owner'):rows=[r for r in rows if sha(r['principal'].encode())==p['owner']]
assert len(rows)==1,'Expected one registered operator credential'
credential=rows[0];owner=Principal(credential['principal'],frozenset(credential['scopes']),'not-a-credential')
rt=Runtime('/var/lib/t01/runtime',scope=owner.runtime_scope)
def rpc(suffix,args):
 req=urllib.request.Request('http://127.0.0.1:18083/mcp',
  headers={'Content-Type':'application/json','Authorization':'Bearer '+credential['token']},
  data=json.dumps(dict(jsonrpc='2.0',id=1,method='tools/call',params=dict(
   name='t01_phase1_real_service_v01.tool.'+suffix,arguments=args))).encode())
 with urllib.request.urlopen(req,timeout=65) as response:value=json.load(response)
 assert 'error' not in value,'MCP request rejected'
 result=value['result'];assert not result.get('isError'),'MCP tool rejected'
 return result['structuredContent']
if p['action']=='start':
 args=dict(request_json=json.dumps(p['request'],ensure_ascii=False),idempotency_key=p['key'])
 first=rpc('workflow.submit',args);second=rpc('workflow.submit',args)
 assert first['job_id']==second['job_id']
 job=rt.get(first['job_id']);request=decode(rt._request_bytes(job))
 assert request['revision_config']==p['request']['revision_config']
 assert request['protein_sequence']==p['request']['protein_sequence']
 value=dict(job_id=job['job_id'],run_id=job['run_id'],state=job['state'],
  owner=sha(owner.principal_id.encode()),idempotency_verified=True,request_sha256=sha(rt._request_bytes(job)),
  calculation_config_id=request['revision_config']['calculation_config_id'],
  rule_version=request['revision_config']['rule_version'],
  user_confirmation_submitted=False,new_run=True,scientific_gate='CLOSED')
else:
 status=rpc('workflow.get',dict(job_id=p['job_id']));job=rt.get(p['job_id']);ex=rt.execution(p['job_id'])
 from t01_phase1_real.service_api.progress import project
 fact=ex.get('revision_state',{})
 value=dict(status,progress=project(status.get('nodes',{})),
  revision_phase=ex.get('phase'),budget=ex.get('revision_ledger',{}),
  revision_summary={k:fact.get(k) for k in ('coverage_complete','run_execution_status','acceptance_status',
   'provisional_acceptance_status','stop_reason_codes','design_outcomes','run_audit')},
  report_ready=job['state']=='succeeded',public_report_api_called=False)
print(json.dumps(value))
'''


def prepare():
    from t01_phase1_real.development.netmhc.host_panel import options
    from t01_phase1_real.service_api.himat import TARGET_IEDB_MANIFEST_SHA256, TARGET_SWISSPROT_MANIFEST_SHA256
    from t01_phase1_real.development.workflow.policy import request as validate
    cfg = json.loads((TESTED / 'config-v2.json').read_bytes())
    cfg.update(calculation_config_id=KEY, structure_eval_max=3, l4_eval_max=3, foldx_variant_max=3)
    body = dict(protein_sequence=SEQUENCE, user_sequence_id='v2_native_' + sha(SEQUENCE.encode())[:16],
        host_species='猪', expression_host=None, organism=None, structure=None,
        prediction=dict(engine='esmfold2', seed=1, timeout_seconds=7200),
        analysis=dict(topology=dict(timeout_seconds=600),
            blast=dict(database_id='iedb-20260924-r01', database_manifest_sha256=TARGET_IEDB_MANIFEST_SHA256,
                thresholds=dict(identity_percent_min=70, query_coverage_percent_min=80), timeout_seconds=7200),
            bepipred=dict(timeout_seconds=900), netmhc=options('猪'), homology=None,
            domains=dict(database_id='swissprot-2026_03-r01', database_manifest_sha256=TARGET_SWISSPROT_MANIFEST_SHA256,
                organism_name=None, entry_id=None, parent=None, user_annotations=[], timeout_seconds=60),
            developability=dict(dimension_weights=None, target_ph=None, target_ph_range=[4.0, 8.0], timeout_seconds=60)),
        reuse_jobs={}, timeout_seconds=28800, engineering_design='BACKEND_EVIDENCE_V1', revision_config=cfg)
    validate(encode(body))
    OUT.mkdir(parents=True, exist_ok=True)
    values = {
        'request.json': body,
        'config.json': cfg,
        'input.json': dict(sequence_length=len(SEQUENCE), sequence_sha256=sha(SEQUENCE.encode()), host_species='猪',
            user_authorization='2026-09-30：现在先部署，然后进行真实测试；沿用该输入，新建 v2 测试',
            run_key=KEY, new_independent_run=True, cancelled_pcv2_resumed=False,
            configuration_rationale='Initial native verification: preserve policy, thresholds, presampling and formal rounds; bound costly structure/L4/FoldX to three candidates each. Partial coverage is explicitly disclosed.',
            request_sha256=sha(encode(body)), source_sha256=sha(encode(build(common.ROOT / 'src')[1])),
            t4_r57_policy='Preserve explicit backend confirmation; no consent inferred from test authorization.',
            scientific_gate='CLOSED', production_status='NOT_DEPLOYED'),
    }
    for name, value in values.items():
        path = OUT / name
        raw = encode(value) + b'\n'
        if path.exists():
            if path.read_bytes() != raw:
                raise RuntimeError('Prepared native test input changed')
        else:
            with path.open('xb') as stream:
                stream.write(raw)
    return dict(status='PREPARED_NOT_SUBMITTED', sequence_length=len(SEQUENCE), host_species='猪',
        config_id=KEY, structure_eval_max=3, l4_eval_max=3, foldx_variant_max=3, source_sha256=values['input.json']['source_sha256'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'start', 'status'))
    action = parser.parse_args().action
    if action == 'prepare':
        value = prepare()
    elif action == 'start':
        receipt = OUT / 'submission.json'
        if receipt.exists():
            print(receipt.read_text(encoding='utf8'))
            return
        prepared = json.loads((OUT / 'input.json').read_bytes())
        deployed = json.loads((DEPLOY / 'deployment-verification.json').read_bytes())
        contract = json.loads((DEPLOY / 'deployed-contract-check.json').read_bytes())
        manifest = build(common.ROOT / 'src')[1]
        if not (deployed['status'] == contract['status'] == 'PASS'
                and deployed['source_sha256'] == prepared['source_sha256'] == sha(encode(manifest))):
            raise RuntimeError('Native test requires the verified v2 deployment')
        state = common.idle()
        if state['active_jobs'] or not state['gpu_state'] or state['gpu_state']['phase'] != 'idle':
            raise RuntimeError('Existing active tasks must finish')
        body = json.loads((OUT / 'request.json').read_bytes())
        if sha(encode(body)) != prepared['request_sha256']:
            raise RuntimeError('Prepared request hash changed')
        (OUT / 'start-preflight.json').write_bytes(encode(state) + b'\n')
        value = common.remote(REMOTE, dict(action='start', request=body, key=KEY))
        with receipt.open('xb') as stream:
            stream.write(encode(value) + b'\n')
    else:
        submitted = active_submission()
        value = common.remote(REMOTE, dict(action='status', job_id=submitted['job_id'], owner=submitted['owner']))
        (OUT / 'latest-status.json').write_bytes(encode(value) + b'\n')
    if action == 'status':
        summary = {k: value.get(k) for k in ('job_id', 'run_id', 'state', 'terminal', 'error_code', 'pending_confirmation', 'revision_summary')}
        summary['current_nodes'] = value['progress']['current_nodes']
        summary['active_steps'] = {k: r for k, r in value.get('nodes', {}).items()
                                   if r['state'] in ('running', 'reconciling', 'awaiting_confirmation', 'queued')}
        summary['node_states'] = {k: r['state'] for k, r in value.get('nodes', {}).items()}
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(json.dumps(value, ensure_ascii=False))


if __name__ == '__main__':
    main()
