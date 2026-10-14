"""Verify test-service mounted route code and the loaded business order."""
import json
import subprocess

import prepare_m1_p1_deploy as common
import prepare_m1_route_deploy as route
from t01_phase1_real.development.workflow import policy

OUT=common.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/route-deployment-verification-r01.json'


def main():
    preflight=json.loads((route.OUT/'preflight.json').read_bytes())
    expected=route.hashes()
    assert expected==preflight['source_hashes']
    live=json.loads(subprocess.check_output(common.K+['get','deployment','antigen-design','-o','json']))
    assert live['spec']['replicas']==1 and live['spec']['strategy']=={'type':'Recreate'}
    assert live['status'].get('observedGeneration')==live['metadata']['generation']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    spec=live['spec']['template']['spec']
    assert next(v for v in spec['volumes'] if v['name']==route.VOLUME)['configMap']['name']==route.NAME
    service=next(c for c in spec['containers'] if c['name']=='service')
    for i,name in enumerate(route.FILES):
        path='/app/src/t01_phase1_real/'+name
        mounts=[m for m in service['volumeMounts'] if m['mountPath']==path]
        assert mounts==[dict(name=route.VOLUME,mountPath=path,subPath='p'+str(i),readOnly=True)]
    code="""import hashlib,json,sys
from pathlib import Path
from t01_phase1_real.development.workflow import m1,policy
names=json.load(sys.stdin)
hashes={n:hashlib.sha256(Path('/app/src/t01_phase1_real',n).read_bytes()).hexdigest() for n in names}
print(json.dumps(dict(hashes=hashes,tail=m1.TAIL,nodes={n:policy.NODES[n] for n in m1.TAIL},
    rule_profile=policy.registered_rules(),execution_profile=policy.registered_profile())))
"""
    mounted=common.remote(code,list(route.FILES))
    assert mounted['hashes']==expected
    tail=mounted['tail'];nodes=mounted['nodes']
    assert not {'selection_report','base_report'} & set(tail)
    assert tail.index('preselection')<tail.index('protection')<tail.index('stability')<tail.index('variant_report')
    assert [(name,nodes[name]) for name in tail if nodes[name]=='N15']==[('variant_report','N15')]
    assert tail.index('variant_report')<tail.index('codon')<tail.index('wt_foldx')<tail.index('local_delivery')
    assert mounted['rule_profile']['sha256']==policy.registered_rules()['sha256']
    result=dict(status='PH1_REAL_ROUTE_DEPLOYED_HASH_PASS',deployment_generation=live['metadata']['generation'],
        mounted_code_sha256=expected,rule_profile=mounted['rule_profile'],execution_profile=mounted['execution_profile'],
        order=list(tail),nodes=nodes,read_only=True,scientific_release_gate='CLOSED',
        usable_for_pipeline=False,production_status='NOT_DEPLOYED')
    assert not OUT.exists()
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['status'])


if __name__=='__main__':main()
