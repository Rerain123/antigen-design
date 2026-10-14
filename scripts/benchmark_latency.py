"""Read-only source replay of the paused live checkpoint; no dispatch/recover."""
import json
import sys
import latency_maintenance as m
from prepare_latency_repair import POD

mode=sys.argv[1]
assert mode in ('baseline','optimized')
code='''
import time
from t01_phase1_real.development.workflow import revision_controller as rc
from t01_phase1_real.development.workflow.service import configuration
from contextlib import nullcontext
if p['mode']=='optimized':
 from t01_phase1_real.service_api.replay_cache import scope
else:scope=nullcontext
ex=rt.execution(jid);body=decode(rt._request_bytes(rt.get(jid)))
assert body['configuration']==configuration(rt)
ticks=[];t=time.monotonic()
with scope() as cache:
 data,reason=rc.inputs(rt,jid,body);ticks.append(time.monotonic()-t)
 for i in range(3):
  t=time.monotonic()
  fact=rc.assemble(rt,jid,body,data,**({'sampling_only':True} if p['mode']=='optimized' and i<2 else {}))
  ticks.append(time.monotonic()-t)
 stats=dict(hits=cache.hits,misses=cache.misses,bytes=cache.size,entries=len(cache.entries)) if cache else None
assert sha(encode(ex))==sha(encode(rt.execution(jid)))
from t01_phase1_real.development.esm_if1.policy import registered_profile as esm
from t01_phase1_real.development.bepipred.policy import registered_profile as bp
print(json.dumps(dict(time=now(),phase_seconds=ticks,total_seconds=sum(ticks),fact=fact,cache=stats,
                     esm_profile=esm(),bepipred_profile=bp(),execution_sha256=sha(encode(ex)))))
'''
r=m.remote(code,dict(mode=mode),timeout=900,pod=POD if mode=='optimized' else 'antigen-controller-maintenance-20261010')
(m.EV/(mode+'-comparison.json')).write_bytes(m.encode(r))
print(json.dumps({k:v for k,v in r.items() if k!='fact'}))
old=json.loads((m.EV/'baseline-stable.json').read_bytes())
assert old['fact']==r['fact'],'Final fact differs from original stable checkpoint'
print('ALL_FACTS_EQUAL; NO_MODEL_CALLS')
