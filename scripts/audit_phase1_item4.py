"""Item 4 evidence audit; partial branches are not scientific completion."""
import json
import xml.etree.ElementTree as ET
import prepare_phase1_item4 as deploy
from t01_phase1_real.common import REPO,encode,sha
from t01_phase1_mock.dify.campaign import verify_freeze_manifest


def collect():
    latest={}
    for p in sorted(deploy.EVIDENCE.glob('*junit.xml')):
        for case in ET.parse(p).getroot().iter('testcase'):
            key=(case.get('classname'),case.get('name'))
            if case.find('skipped') is not None and key in latest:continue
            latest[key]=case
    assert len(latest)>2400 and all(c.find('failure') is None and c.find('error') is None for c in latest.values())
    live=json.loads((deploy.EVIDENCE/'deployment-r01.json').read_bytes())
    assert all(sha((REPO/'src/t01_phase1_real'/n).read_bytes())==h for n,h in live['source_hashes'].items())
    source=json.loads((REPO/'legacy/project-history/expert/EXPERT_V10_5_REVISION_MANIFEST_20260902.json').read_bytes())
    for row in source['files']:
        raw=(REPO/source['revised_root']/row['Name']).read_bytes()
        assert sha(raw)==row['NewSHA256'].lower() and len(raw)==row['NewBytes']
    return dict(status='ITEM4_DEFINED_BRANCHES_PARTIAL_ENGINEERING_VERIFIED',generation=live['generation'],
        tests=dict(passed=sum(c.find('skipped') is None for c in latest.values()),skipped=sum(c.find('skipped') is not None for c in latest.values())),
        source_hashes=live['source_hashes'],frozen=verify_freeze_manifest(),expert_originals_verified=len(source['files']),
        completed=['E4 individual contacts HARD/FIXED, E3 RESTRICTED and E2 RESTRICTED with provenance',
            'SOP regeneration pairs 24/0.1,48/0.3,64/0.5 on complete R35 rejection; 136 exhaustion guard',
            'Durable child insertion, cancellation, restart idempotency, same-run baseline reuse and retained T4 consent',
            'Explicit confirmed R57 context forwarded to backend masks'],
        remaining=['Full S28 structure validation and formal recheck pool (existing three representatives are diagnostic only)',
            'Regeneration after all candidates fail structural validation is not connected',
            'OI-001/002/006/008/021/022 scientific and schema branches remain pending',
            'Native 48/64 generation and real regenerated-round chain not executed in this run'],
        scientific_gate='CLOSED',usable_for_pipeline=False,production_status='NOT_DEPLOYED',
        new_design_workflow_started=False,new_candidates_generated=False,
        evidence_sha256={p.name:sha(p.read_bytes()) for p in deploy.EVIDENCE.iterdir() if p.is_file()})


if __name__=='__main__':
    value=collect()
    with (deploy.EVIDENCE/'closeout-r01.json').open('xb') as stream:stream.write(encode(value))
    print(json.dumps({k:value[k] for k in ('status','generation','tests','frozen')}))
