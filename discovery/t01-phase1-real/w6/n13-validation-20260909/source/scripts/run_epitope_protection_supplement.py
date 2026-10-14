"""Additional N13 source-state, domain and wrong-chain probes on the new acceptance root."""
import argparse
import copy
from pathlib import Path
import sys
REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'src'))
from t01_phase1_real.common import decode,encode,sha,RuntimeFault
from t01_phase1_real.development import Runtime
from t01_phase1_real.development.epitope_protection import policy,service
from run_variant_report_acceptance import write,source

def main():
    p=argparse.ArgumentParser();p.add_argument('--batch',required=True);p.add_argument('--output',required=True);args=p.parse_args()
    parent=Path(args.batch).absolute();batch=Path(args.output).absolute();assert not batch.exists();batch.mkdir(parents=True)
    original=decode((parent/'index.json').read_bytes());root=Path(original['runtime_root']);dr=Runtime(root/'design');fr=Runtime(root/'foldx')
    guards=[];cases=[]
    def src(rt,j):
        j=rt.get(j['job_id']);ref=next((r for r in j['artifacts'] if r['role'] in ('result','diagnostic')),None)
        return dict(job_id=j['job_id'],artifact=ref)
    def finish(rt,name,j,state='succeeded',code=None):
        j=rt.wait(j['job_id'],180);v=rt.result(j['job_id']) if j['artifacts'] else None
        assert (j['state'],j['error_code'])==(state,code),(j,v)
        write(batch/'cases'/name/'job.json',j)
        if v:write(batch/'cases'/name/'result.json',v)
        for ref in j['artifacts']:write(batch/'cases'/name/'artifacts'/ref['artifact_id'],rt.artifact_bytes(j['job_id'],ref['artifact_id']))
        cases.append(dict(case=name,job_id=j['job_id'],state=state,error_code=code));print(name,state,flush=True);return j,v
    def run(rt,name,b,tool=policy.TOOL,state='succeeded',code=None):
        write(batch/'requests'/(name+'.json'),b);j=rt.submit_sequence(encode(b),'n13-supp-'+name,tool);rt.dispatch(j['job_id']);return finish(rt,name,j,state,code)
    b=decode((parent/'requests/real-paired-n06-hotspots-unavailable.json').read_bytes())
    seq=b['protein_sequence'];variant_seq=decode((parent/'cases/real-paired-n06-hotspots-unavailable/result.json').read_bytes())['protection']['records'][0]['sequence']
    missing=dict(state='not_provided',artifact=None,reason_code=None)
    fail=dict(protein_sequence=variant_seq,user_sequence_id='N13 actual unavailable predictors',timeout_seconds=30,
        bepipred_input=missing,netmhc_input=missing,blast_input=dict(state='not_executed',artifact=None,reason_code='NOT_EXECUTED'))
    nj,_=run(dr,'n06-no-predictors',fail,'t01.real.epitope_map','failed','TOOL_FAILED')
    fb=copy.deepcopy(b);fb['pairs'][0]['variant']['epitope_map']=src(dr,nj)
    _,v=run(dr,'failed-n06-side',fb);r=v['protection']['records'][0]
    assert r['source_states']['variant']['source_receipts']['epitope_map']['state']=='failed' and r['observation']['scientific_pass'] is None
    legacy=REPO/'discovery/t01-phase1-real/w5/design-backend-integration-20260908/acceptance-r02'
    domain=source(dr,legacy,'real-n09');nb=copy.deepcopy(b);nb['pairs'][0]['wt']['domains']=domain
    _,v=run(dr,'real-n09-domain-source',nb);assert v['protection']['records'][0]['source_states']['wt']['domains']
    # Explicit chain-renamed derivative is a separate unknown-source engineering input.
    fb=decode((parent/'requests/real-paired-structure-n06.json').read_bytes());sj=fr.get(fb['pairs'][0]['variant']['structure']['job_id']);sv=fr.result(sj['job_id'])
    ref=next(r['artifact'] for r in sv['raw_artifacts'] if r['path']=='input.structure');raw=fr.artifact_bytes(sj['job_id'],ref['artifact_id'])
    changed='\n'.join(line[:21]+'B'+line[22:] if line.startswith('ATOM  ') else line for line in raw.decode().splitlines()).encode()
    from structure_integration_cases import metadata
    seq=decode(fr._request_bytes(sj))['protein_sequence'];meta=metadata(sequence=seq,fmt='PDB',source='unknown',context=['B'])
    meta['source_declaration']['note']='Explicit engineering chain-renamed derivative for wrong-chain rejection'
    j=fr.submit_structure(encode(meta),'n13-supp-chain-b',changed);fr.dispatch(j['job_id']);j,_=finish(fr,'chain-b-local-analysis',j)
    wrong=copy.deepcopy(fb);wrong['pairs'][0]['variant']['structure']=src(fr,j)
    try:fr.submit_sequence(encode(wrong),'n13-supp-wrong-chain',policy.TOOL)
    except RuntimeFault as exc:guards.append(dict(case='wrong-chain',code=exc.code,reason=str(exc)))
    else:raise AssertionError('Wrong chain accepted')
    # Late upstream source replacement and final report tampering must be fenced.
    s=fb['pairs'][0]['variant']['structure'];j=fr.get(s['job_id']);ref=next(r for r in j['artifacts'] if r['role']=='raw')
    with fr._db() as db:path=fr.root/db.execute('SELECT relative_path FROM artifacts WHERE id=?',(ref['artifact_id'],)).fetchone()[0]
    saved=path.read_bytes();original_eval=service.evaluate;task=fr.submit_sequence(encode(fb),'n13-supp-late-source',policy.TOOL)
    def late(*args):
        value=original_eval(*args);path.write_bytes(b'{}');return value
    try:service.evaluate=late;fr.dispatch(task['job_id'])
    finally:service.evaluate=original_eval;path.write_bytes(saved)
    _,v=finish(fr,'late-structure-tamper',task,'failed','HASH_MISMATCH');assert v['protection'] is None
    index=dict(status='PASS',parent_index=str(parent/'index.json'),parent_index_sha256=sha((parent/'index.json').read_bytes()),cases=cases,guards=guards,
        scientific_protection_pass=None,files=[dict(path=p.relative_to(batch).as_posix(),bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(batch.rglob('*')) if p.is_file()])
    write(batch/'index.json',index)

if __name__=='__main__':main()
