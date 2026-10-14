"""Deploy the tested latency-only source bundle and resume the same paused run."""
import copy
import json
import subprocess
import concurrent.futures
import xml.etree.ElementTree as ET
import latency_maintenance as m
from prepare_latency_repair import OUT,POD
from deploy_terminal_sync import run,NAMES
from version_bundle import build,encode,sha
from verify_gpu_resident import check_template
import verify_version_unification as verification


def prepared():
    manifest=json.loads((OUT/'source-manifest.json').read_bytes())
    assert build(m.common.ROOT/'src')[1]==manifest,'Source differs from tested bundle'
    return manifest,json.loads((OUT/'templates.json').read_bytes())


def gate():
    manifest,templates=prepared()
    baseline=json.loads((m.EV/'baseline-comparison.json').read_bytes())
    candidate=json.loads((m.EV/'optimized-comparison.json').read_bytes())
    assert baseline['fact']==candidate['fact'] and baseline['execution_sha256']==candidate['execution_sha256']
    assert baseline['esm_profile']==candidate['esm_profile']
    assert candidate['total_seconds'] < .75*baseline['total_seconds']
    # The final full rerun was interrupted by the chat. Keep that fact explicit;
    # merge the completed initial suite with final affected/failure modules.
    latest={};receipts=[]
    for filename in ('full-r01.xml','final-affected.xml','docker-final.xml'):
        raw=(m.EV/filename).read_bytes();cases=list(ET.fromstring(raw).iter('testcase'))
        if filename=='final-affected.xml':
            assert len(cases)>250
        if filename=='docker-final.xml':
            assert len(cases)>=6 and not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
        for c in cases:latest[(c.get('classname'),c.get('name'))]=c
        receipts.append(dict(path=filename,sha256=sha(raw),tests=len(cases)))
    cases=list(latest.values())
    assert len(cases)>3300 and not any(c.find('failure') is not None or c.find('error') is not None for c in cases)
    (m.EV/'regression.json').write_bytes(encode(dict(receipts=receipts,tests=len(cases),
        passed=sum(c.find('skipped') is None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases),
        single_final_full_run=False,final_full_rerun_interrupted=True)))
    assert json.loads((m.EV/'frozen.json').read_bytes())['status']=='PASS'
    return manifest,templates


def rollout():
    manifest,templates=gate()
    state=m.status()
    assert [j['job_id'] for j in state['active']]==[m.JID] and state['dispatcher'] is None
    assert state['gpu']['phase']=='idle'
    paused=json.loads((m.EV/'deployments-paused.json').read_bytes())
    for name in NAMES:
        current=run(['get','deployment',name,'-o','json'])
        assert current['metadata']['uid']==paused[name]['metadata']['uid'] and current['spec']==paused[name]['spec']
    (m.EV/'pre-rollout-state.json').write_bytes(encode(state))
    for name in NAMES:
        current=run(['get','deployment',name,'-o','json'])
        patch=json.loads((OUT/(name+'.patch.json')).read_bytes())
        next(p for p in patch if p['path']=='/metadata/resourceVersion')['value']=current['metadata']['resourceVersion']
        path=OUT/(name+'.applied.patch.json');path.write_bytes(encode(patch))
        run(['patch','deployment',name,'--type=json','--patch-file',str(path),'-o','name'])
    print('Worker rollout submitted; API remains paused')


def ready():
    _,templates=prepared();pods=run(['get','pods','-o','json'])['items'];found=[]
    for name in NAMES[1:]:
        d=run(['get','deployment',name,'-o','json']);check_template(d['spec']['template'],templates[name])
        assert d['status'].get('observedGeneration')==d['metadata']['generation']
        assert d['spec']['replicas']==d['status'].get('readyReplicas')==d['status'].get('updatedReplicas')==1
        matches=[p for p in pods if not p['metadata'].get('deletionTimestamp') and all(
            p['metadata']['labels'].get(k)==v for k,v in d['spec']['selector']['matchLabels'].items())]
        assert len(matches)==1 and all(c['ready'] and c['restartCount']==0 for c in matches[0]['status']['containerStatuses'])
        found.append(matches[0])
    return found


def check_files(pods):
    manifest,_=prepared()
    boot="import json,sys;p=json.load(sys.stdin);exec(compile(p.pop('code'),'source-verification','exec'))"
    code=verification.REMOTE.replace('p=json.load(sys.stdin)','')
    def check(pod):
        c=pod['spec']['containers'][0]['name'];python='python' if c=='service' else '/opt/t01/supervisor/bin/python3.11'
        p=subprocess.run(m.common.K+['exec','-i',pod['metadata']['name'],'-c',c,'--',python,'-B','-c',boot],
            input=encode(dict(code=code,container=c,manifest=manifest)),capture_output=True,timeout=150)
        assert p.returncode==0,(c,p.stderr.decode(errors='replace')[-1500:])
        value=json.loads(next(line[7:] for line in p.stdout.decode().splitlines() if line.startswith('VERIFY=')))
        return dict(value,pod=pod['metadata']['name'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:return list(pool.map(check,pods))


def resume():
    gate();pods=ready()
    (m.EV/'worker-verification.json').write_bytes(encode(check_files(pods)))
    state=m.status();assert [j['job_id'] for j in state['active']]==[m.JID] and state['dispatcher'] is None
    old=json.loads((m.EV/'quiescent-checkpoint.json').read_bytes())
    checkpoint=json.loads((m.EV/'baseline-comparison.json').read_bytes())['execution_sha256']
    paused=json.loads((m.EV/'drain-mhc-latest.json').read_bytes())['time']
    previous=json.loads((m.common.ROOT/'deploy/terminal-sync/r01/source-manifest.json').read_bytes())
    code='''
from t01_phase1_real.service_api.controller_maintenance import authorize
from t01_phase1_real.development.workflow.service import configuration
job=rt.get(jid);ex=rt.execution(jid)
assert sha(encode(ex))==p['checkpoint']
assert decode(rt._request_bytes(job))['configuration']==configuration(rt)
receipt=authorize(rt,jid,p['checkpoint'],p['paused_at'],p['previous_manifest'],p['previous_predictor'])
assert {k:v for k,v in rt.execution(jid).items() if k!='controller_upgrade'}==ex
assert rt.get(jid)['request_artifact']==job['request_artifact']
print(json.dumps(dict(receipt=receipt,time=now())))
'''
    result=m.remote(code,dict(checkpoint=checkpoint,paused_at=paused,previous_manifest=previous,
                             previous_predictor=old['bepipred_profile']),pod=POD)
    (m.EV/'resume-receipt.json').write_bytes(encode(result))
    run(['scale','deployment','antigen-design','--current-replicas=0','--replicas=1'])
    print('Original job authorized and API activated; no replacement run submitted')


def verify():
    manifest,templates=prepared();workers=ready()
    d=run(['get','deployment','antigen-design','-o','json']);check_template(d['spec']['template'],templates['antigen-design'])
    assert d['status'].get('readyReplicas')==d['status'].get('updatedReplicas')==d['spec']['replicas']==1
    pods=run(['get','pods','-l','app.kubernetes.io/component=control-plane','-o','json'])['items']
    pods=[p for p in pods if not p['metadata'].get('deletionTimestamp') and p['metadata']['labels'].get('app.kubernetes.io/name')=='antigen-design']
    assert len(pods)==1 and all(c['ready'] and c['restartCount']==0 for c in pods[0]['status']['containerStatuses'])
    results=check_files(pods+workers)
    (m.EV/'deployment-verification.json').write_bytes(encode(dict(status='PASS',files=len(manifest),
        source_sha256=sha(encode(manifest)),api_generation=d['metadata']['generation'],containers=results)))
    print('VERIFIED',len(results),'containers; API generation',d['metadata']['generation'])


if __name__=='__main__':
    import sys
    assert sys.argv[1] in ('rollout','resume','verify')
    globals()[sys.argv[1]]()
