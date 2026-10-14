"""Read-only deployed N13 verification with native archived structures and QCP."""
import json
import subprocess
import prepare_m1_p1_deploy as c
import prepare_n13_local_rmsd as deploy

REMOTE=r'''
import json,sys,copy
from pathlib import Path
import numpy as np
from Bio.PDB.qcprot import QCPSuperimposer
from t01_phase1_real.linux_service import install_platform_modules
install_platform_modules()
from t01_phase1_real.common import sha,decode
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.epitope_protection import compute,source,policy
from t01_phase1_real.development.design_backend.source import sources as registered
from t01_phase1_real.development.workflow import m1
p=json.load(sys.stdin)
hashes={n:sha((Path('/app/src/t01_phase1_real')/n).read_bytes()) for n in p['files']}
assert hashes==p['hashes']
rt=Runtime('/var/lib/t01/runtime',scope='svc-'+p['owner'][:24],blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
parent=rt.get(p['job_id']);nodes=rt.execution(parent['job_id'])['nodes'];old=rt.get(nodes['protection']['job_id'])
request=decode(rt._request_bytes(old));checks=[]
for pair in request['pairs']:
    sides={};receipts={}
    variant=next(r for r in rt.result(old['job_id'])['protection']['records'] if r['variant_id']==pair['variant_id'])['sequence']
    for label,seq in [('wt',request['protein_sequence']),('variant',variant)]:
        body=dict(protein_sequence=seq,upstream=pair[label])
        with rt._db() as db:
            files,values,sr=registered(rt,db,body,producers=policy.SIDE_PRODUCERS,enricher=source.side_enrich)
        source.same_run_receipts(sr,parent['run_id'])
        sides[label]=source.facts(body,files,values,sr);receipts[label]=sr
    w,v=sides['wt']['geometry'],sides['variant']['geometry']
    covered=sorted(int(k) for k in w if k in v and 'CA' in w[k]['atoms'] and 'CA' in v[k]['atoms'])
    # This is an explicitly labelled numerical test window, never a hotspot or
    # scientific acceptance interval. Actual unavailable hotspots stay null.
    ps=covered[:12];assert len(ps)==12
    a=np.array([w[str(i)]['atoms']['CA'] for i in ps]);b=np.array([v[str(i)]['atoms']['CA'] for i in ps])
    ref=QCPSuperimposer();ref.set(a,b);ref.run()
    observed=compute.geometry(w,v,ps)
    assert abs(observed['rmsd']-ref.get_rms())<1e-8
    moved=copy.deepcopy(v)
    for r in moved.values():
        if 'CA' in r['atoms']:
            x,y,z=r['atoms']['CA'];r['atoms']['CA']=[-y+10,x-5,z+3]
    invariant=compute.geometry(w,moved,ps)['rmsd'];assert abs(invariant-observed['rmsd'])<1e-10
    business=compute.compare(request['protein_sequence'],variant,sides)
    assert business['scientific_pass'] is None
    checks.append(dict(variant_id=pair['variant_id'],variant_sequence_sha256=sha(variant.encode()),
        test_window_purpose='NUMERICAL_REFERENCE_ONLY_NOT_A_BIOLOGICAL_VALIDATION_REGION',
        numerical_test=observed,independent_qcp_rmsd=ref.get_rms(),rigid_transformed_rmsd=invariant,
        business_observation=business,source_receipts=receipts))
assert rt.get(parent['job_id'])==parent and rt.get(old['job_id'])==old
# Replay the already published IEDB -> N06 chain through the actual N13 source
# resolver. This is a different archived run, never spliced into the pairs above.
iedb_rt=Runtime('/var/lib/t01/runtime',scope='iedb-n03-engineering-r01',blast_database_root='/var/lib/t01/m1-p1-test-data/blast')
map_job=iedb_rt.get(p['iedb_n06_job_id']);map_request=decode(iedb_rt._request_bytes(map_job))
map_ref=next(r for r in map_job['artifacts'] if r['role']=='result')
body=dict(protein_sequence=map_request['protein_sequence'],upstream=dict(structure=None,domains=None,
    epitope_map=dict(job_id=map_job['job_id'],artifact=map_ref)))
with iedb_rt._db() as db:
    files,values,receipts=registered(iedb_rt,db,body,producers=policy.SIDE_PRODUCERS,enricher=source.side_enrich)
source.same_run_receipts(receipts,map_job['run_id'])
facts=source.facts(body,files,values,receipts)
assert len(facts['iedb_prior']['epitope_regions'])==61 and facts['hotspots'] is None
assert facts['iedb_prior']['e4_status']=='unavailable' and facts['e4_positions']==[]
iedb_check=dict(run_id=map_job['run_id'],sequence_sha256=facts['sequence_sha256'],source_receipts=receipts,
    prior=facts['iedb_prior'],hotspots=facts['hotspots'],e4_positions=facts['e4_positions'])
assert iedb_rt.get(map_job['job_id'])==map_job
# The real HiMat entry binds the same database snapshot for each exact variant.
from t01_phase1_real.service_api.himat import HiMatIntegration
from t01_phase1_real.service_api.app import Principal
from t01_phase1_real.development.workflow import service
class Capture:
    def submit(self,principal,value):self.body=value['request'];return dict(job_id='not-submitted',state='queued')
capture=Capture();adapter=HiMatIntegration(capture,'https://example.invalid',b'x'*32)
adapter.submit_sequence(Principal('himat-t01-test',frozenset(['submit']),'not-a-credential'),'ACDEFGHIKLMNPQRSTVWY','Sus scrofa')
configured=capture.body['analysis']['blast'];assert configured['database_id']=='iedb-20260924-r01'
assert m1.TAIL.index('rep1_blast')<m1.TAIL.index('rep1_epitope_map')
print(json.dumps(dict(status='N13_LOCAL_RMSD_DEPLOYED_REFERENCE_PASS',source_hashes=hashes,
    rule_profile=policy.registered_rules(),numpy_version=np.__version__,
    authority={f.relative_to(policy.REPO).as_posix():sha(f.read_bytes()) for f in policy.AUTHORITY},
    authority_sections=['一期图 节点13 L1-L4','SOP v10.5 T-01 step19'],
    archive_run_id=parent['run_id'],real_structure_pairs=checks,configured_iedb=configured,iedb_n06_n13_source_replay=iedb_check,
    archived_jobs_unchanged=True,new_scientific_tasks_started=False,
    scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED')))
'''


def main():
    batch=json.loads((c.ROOT/'discovery/t01-phase1-real/m1-p4-20260922/r16/batch.json').read_bytes())
    from verify_iedb_n03_native import OUT as iedb_out
    iedb=json.loads((iedb_out/'n06-chain.json').read_bytes())
    result=c.remote(REMOTE,dict(owner=batch['owner'],job_id=batch['job_id'],iedb_n06_job_id=iedb['job']['job_id'],
        files=list(deploy.FILES),hashes=deploy.hashes()))
    live=json.loads(subprocess.check_output(c.K+['get','deployment','antigen-design','-o','json']))
    assert live['status']['observedGeneration']==live['metadata']['generation']
    assert live['status'].get('readyReplicas')==live['status'].get('updatedReplicas')==1
    result['generation']=live['metadata']['generation'];result['idle']=c.idle()
    out=deploy.EVIDENCE/'deployment-reference-r01.json';assert not out.exists()
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status=result['status'],generation=result['generation'],pairs=len(result['real_structure_pairs']))))


if __name__=='__main__':main()
